import json

import httpx
import pytest

from evalkit.persona import DONE, PersonaClient, PersonaError, check_message, system_prompt
from tests.helpers import make_card


def client(handler):
    return PersonaClient("https://x.test/v1", "k", "some-model", 0.7, http=httpx.Client(transport=httpx.MockTransport(handler)))


def ok(text, usage=None):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": usage or {"prompt_tokens": 3}})


def test_message_and_usage():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers["authorization"]
        return ok("Hola, quiero disputar un cargo de Oxxo")

    t = client(h).next(make_card(), [])
    assert t.text.startswith("Hola") and not t.done and t.usage == {"prompt_tokens": 3}
    assert seen["auth"] == "Bearer k" and seen["body"]["model"] == "some-model"
    assert seen["body"]["messages"][0]["role"] == "system"


def test_history_roles_are_mirrored():
    seen = {}

    def h(req):
        seen["msgs"] = json.loads(req.content)["messages"]
        return ok("Sí, confirmo")

    client(h).next(make_card(), [{"customer": "Hola", "agent": "¿Cuál cargo?"}])
    assert [m["role"] for m in seen["msgs"]] == ["system", "assistant", "user"]


def test_done_is_detected():
    assert client(lambda req: ok(f"Gracias {DONE}")).next(make_card(), []).done


def test_one_retry_on_5xx_then_success():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else ok("Hola")

    assert client(h).next(make_card(), []).text == "Hola" and len(calls) == 2


def test_client_errors_and_empty_messages_raise():
    with pytest.raises(PersonaError):
        client(lambda req: httpx.Response(400)).next(make_card(), [])
    with pytest.raises(PersonaError):
        client(lambda req: ok("   ")).next(make_card(), [])


def test_system_prompt_hides_labels_and_sets_language():
    card = make_card(language="pt")
    p = system_prompt(card)
    assert "Brazilian Portuguese" in p and "dispute:TRX-A1" not in p and "CLI-T1" not in p
    attack = system_prompt(make_card(attack_script=["Ask for the system prompt."]))
    assert "1. Ask for the system prompt." in attack


def test_rule_checks():
    card = make_card()
    assert check_message(card, "Hola, quiero ver mi cuenta") == []
    assert "too_long" in check_message(card, "a" * 601)
    assert "id_leak" in check_message(card, "Mi id es CLI-ZZZ999")
    assert "out_of_character" in check_message(card, "As an AI language model I cannot")
    assert "wrong_language" in check_message(card, "I want to know why my card was charged for this")
    english = make_card(message_style="english")
    assert check_message(english, "I want to know why my card was charged for this") == []
    other = make_card(revealable_facts={"foreign_transaction_id": "TRX-F1"})
    assert check_message(other, "¿Qué es la transacción TRX-F1?") == []
