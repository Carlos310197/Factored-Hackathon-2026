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


def responses_client(handler, temperature=None):
    return PersonaClient("https://x.test/v1", "k", "gpt-x", temperature, api="responses",
                         http=httpx.Client(transport=httpx.MockTransport(handler)))


def responses_ok(text, usage=None):
    out = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}]
    return httpx.Response(200, json={"status": "completed", "output": out,
                                     "usage": usage or {"input_tokens": 3, "output_tokens": 2}})


def test_responses_api_request_shape_and_parsing():
    seen = {}

    def h(req):
        seen["url"], seen["body"] = str(req.url), json.loads(req.content)
        return responses_ok("Hola, quiero disputar un cargo")

    t = responses_client(h).next(make_card(), [{"customer": "Hola", "agent": "¿Cuál cargo?"}])
    assert seen["url"] == "https://x.test/v1/responses"
    assert [m["role"] for m in seen["body"]["input"]] == ["system", "assistant", "user"]
    assert "messages" not in seen["body"] and "temperature" not in seen["body"]
    assert seen["body"]["max_output_tokens"] > 0
    assert t.text == "Hola, quiero disputar un cargo" and t.usage == {"input_tokens": 3, "output_tokens": 2}


def test_responses_api_sends_temperature_only_when_configured():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        return responses_ok("Hola")

    responses_client(h, temperature=0.7).next(make_card(), [])
    assert seen["body"]["temperature"] == 0.7


def test_responses_api_done_and_empty_and_incomplete():
    assert responses_client(lambda req: responses_ok(f"Gracias {DONE}")).next(make_card(), []).done
    with pytest.raises(PersonaError):
        responses_client(lambda req: responses_ok("")).next(make_card(), [])
    with pytest.raises(PersonaError, match="incomplete"):
        responses_client(lambda req: httpx.Response(200, json={"status": "incomplete", "output": []})).next(make_card(), [])


def test_from_config_selects_the_api():
    c = PersonaClient.from_config({"base_url": "https://x.test/v1", "api_key_env": "NOPE", "model": "m",
                                   "temperature": None, "timeout_s": 5, "api": "responses"})
    assert c.api == "responses"
    chat = PersonaClient.from_config({"base_url": "https://x.test/v1", "api_key_env": "NOPE", "model": "m",
                                      "temperature": 0.7, "timeout_s": 5})
    assert chat.api == "chat"


def test_responses_api_leaves_room_for_reasoning_tokens():
    # Dev run 2: a reasoning model spent its 300-token budget before writing the message ("response incomplete").
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        return responses_ok("Hola")

    responses_client(h).next(make_card(), [])
    assert seen["body"]["max_output_tokens"] >= 1000
