from types import SimpleNamespace

import bankagent.app as entry
from bankagent.auth.tokens import generate_keypair, issue_token, jwks_from_public
from bankagent.context import SCOPE_DISPUTE, SCOPE_READ
from tests.ui_fakes import FakeService

ISS, AUD = "http://idp.test", "bankagent"
PRIV, PUB = generate_keypair()
JWKS = jwks_from_public(PUB, "k1")
HDR = "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Message-Id"


def rt(service=None):
    return SimpleNamespace(settings=SimpleNamespace(issuer=ISS, audience=AUD), jwks=SimpleNamespace(get=lambda: JWKS),
                           service=service or FakeService())


def auth(msg_id=None, sid="S-1"):
    tok = issue_token(PRIV, "k1", ISS, AUD, "CLI-A", sid, {SCOPE_READ, SCOPE_DISPUTE}, "es")
    h = {"Authorization": f"Bearer {tok}"}
    if msg_id:
        h[HDR] = msg_id
    return h


def test_turn_logs_both_messages_turn_end_and_returns_turn_id():
    r = rt()
    out = entry.handle({"message": "  saldo  "}, auth("msg-00000001"), r)
    store = r.service.deps.store
    assert out["turn_id"].startswith("TRN") and r.service.calls[0][2] == out["turn_id"]
    customer, assistant = store.messages.rows
    assert (customer["role"], customer["text"], customer["message_id"], customer["turn_id"]) == \
        ("customer", "saldo", "msg-00000001", out["turn_id"])
    assert assistant["role"] == "assistant" and assistant["meta"]["awaiting"] == "none"
    end = store.log.records[-1]
    assert end["kind"] == "turn_end" and end["node"] == "turn" and end["turn_id"] == out["turn_id"]
    assert end["payload"]["awaiting"] == "none" and end["payload"]["duration_ms"] >= 0


def test_same_message_id_returns_stored_reply_without_second_turn():
    r = rt()
    first = entry.handle({"message": "saldo"}, auth("msg-00000002"), r)
    second = entry.handle({"message": "saldo"}, auth("msg-00000002"), r)
    assert second == first and len(r.service.calls) == 1
    assert [m["role"] for m in r.service.deps.store.messages.rows] == ["customer", "assistant"]


def test_duplicate_while_running_reports_in_progress():
    r = rt()
    r.service.deps.store.messages.claim("S-1", "msg-00000003")
    out = entry.handle({"message": "saldo"}, auth("msg-00000003"), r)
    assert out["error"] == "duplicate_in_progress" and r.service.calls == []


def test_human_control_skips_the_graph_and_logs_the_message():
    r = rt()
    store = r.service.deps.store
    store.sessions.ensure("S-1", "CLI-A", "es")
    store.sessions.items["S-1"]["control"] = "human:agent.ana"
    out = entry.handle({"message": "sí, la tengo"}, auth("msg-00000004"), r)
    assert out["awaiting"] == "human" and out["turn_id"] is None and r.service.calls == []
    assert store.messages.rows[-1]["role"] == "customer" and store.messages.rows[-1]["turn_id"] is None


def test_payload_token_is_no_longer_accepted():
    tok = auth()["Authorization"][7:]
    out = entry.handle({"message": "hola", "session_token": tok}, {}, rt())
    assert out["error"] == "auth_required"


def test_invalid_message_id_is_replaced_not_trusted():
    r = rt()
    entry.handle({"message": "saldo"}, auth("bad id with spaces"), r)
    assert r.service.deps.store.messages.rows[0]["message_id"].startswith("MSG")


def test_session_is_created_with_token_identity():
    r = rt()
    entry.handle({"message": "saldo", "customer_id": "CLI-EVIL"}, auth("msg-00000005", sid="S-9"), r)
    assert r.service.deps.store.sessions.items["S-9"]["customer_id"] == "CLI-A"
