from types import SimpleNamespace

import pytest
from bankagent.auth.tokens import AuthError, verify_token
from bankagent.decisions.jev import JevError

from evalkit.conversation import TokenIssuer, agent_text, run_conversation, snapshot
from evalkit.faults import apply_fault
from evalkit.persona import PersonaError, PersonaTurn
from tests.helpers import make_card

SID = "EVAL-TEST-SESSION"


class ScriptedPersona:
    def __init__(self, messages):
        self.messages, self.calls = list(messages), 0

    def next(self, card, history):
        m = self.messages[self.calls] if self.calls < len(self.messages) else "[DONE]"
        self.calls += 1
        if isinstance(m, Exception):
            raise m
        return PersonaTurn(None, True, {}, 1) if m == "[DONE]" else PersonaTurn(m, False, {"prompt_tokens": 5}, 1)


def fake_store(disputes=(), handoffs=(), records=()):
    return SimpleNamespace(
        disputes=SimpleNamespace(list_for_customer=lambda cid: [d for d in disputes if d["customer_id"] == cid]),
        handoffs=SimpleNamespace(list_by_status=lambda s: [h for h in handoffs if h["status"] == s]),
        log=SimpleNamespace(list=lambda sid: [r for r in records if r["session_id"] == sid]))


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.25
        return self.t


@pytest.fixture(scope="module")
def tokens():
    return TokenIssuer.generate(issuer="eval-idp", audience="bankagent")


def run(card, persona, handle, tokens, store=None):
    return run_conversation(card, 1, handle_fn=handle, rt=None, store=store or fake_store(), persona=persona,
                            tokens=tokens, session_id=SID, clock=Clock())


def test_turns_latency_and_done(tokens):
    seen = []

    def handle(payload, headers, rt):
        seen.append((payload, headers))
        return {"reply_text": "Listo", "language": "es", "awaiting": "none", "options": [], "refs": []}

    rec = run(make_card(), ScriptedPersona(["Hola", "Gracias"]), handle, tokens)
    assert rec["end_reason"] == "done" and len(rec["turns"]) == 2
    assert rec["turns"][0]["latency_ms"] == 250
    assert seen[0][0]["message"] == "Hola" and seen[0][0]["client_message_id"] == f"{SID}-0"
    assert seen[0][1]["Authorization"].startswith("Bearer ")


def test_persona_violation_discards(tokens):
    rec = run(make_card(), ScriptedPersona(["As an AI language model I cannot"]), lambda *a: {}, tokens)
    assert rec["end_reason"] == "persona_discarded" and rec["violations"] == ["out_of_character"]


def test_expired_fault_sends_an_expired_token_on_turn_two(tokens):
    tokens_seen = []

    def handle(payload, headers, rt):
        tok = headers["Authorization"][7:]
        tokens_seen.append(tok)
        try:
            verify_token(tok, tokens.jwks, tokens.issuer, tokens.audience)
        except AuthError as e:
            return {"reply_text": "Tu sesión expiró", "language": "es", "error": "session_expired" if str(e) == "expired" else "auth_required"}
        return {"reply_text": "¿Cuál cargo?", "language": "es", "awaiting": "clarification", "options": [], "refs": []}

    rec = run(make_card(fault="expire_after_turn_1"), ScriptedPersona(["Hola", "El de Oxxo", "Hola?"]), handle, tokens)
    assert rec["end_reason"] == "expired" and len(rec["turns"]) == 2
    assert rec["turns"][1]["token_expired"] is True and rec["turns"][1]["reply"]["error"] == "session_expired"


def test_max_turns(tokens):
    rec = run(make_card(max_turns=2), ScriptedPersona(["a uno", "a dos", "a tres"]),
              lambda *a: {"reply_text": "x", "language": "es"}, tokens)
    assert rec["end_reason"] == "max_turns" and len(rec["turns"]) == 2


def test_errors_become_harness_errors(tokens):
    def boom(*a):
        raise RuntimeError("agent crashed")

    assert run(make_card(), ScriptedPersona(["Hola"]), boom, tokens)["end_reason"] == "harness_error"
    rec = run(make_card(), ScriptedPersona([PersonaError("http 500")]), boom, tokens)
    assert rec["end_reason"] == "harness_error" and rec["error"].startswith("persona")


def test_snapshot_filters_by_session_but_keeps_customer_case_ids():
    store = fake_store(
        disputes=[{"dispute_id": "DSP-1", "customer_id": "CLI-T1", "session_id": SID},
                  {"dispute_id": "DSP-0", "customer_id": "CLI-T1", "session_id": "OTHER"}],
        handoffs=[{"handoff_id": "HND-1", "status": "open", "session_id": SID},
                  {"handoff_id": "HND-9", "status": "open", "session_id": "OTHER"}],
        records=[{"session_id": SID, "kind": "route"}])
    s = snapshot(store, "CLI-T1", SID)
    assert [d["dispute_id"] for d in s["disputes"]] == ["DSP-1"]
    assert [h["handoff_id"] for h in s["handoffs"]] == ["HND-1"]
    assert s["customer_case_ids"] == ["DSP-0", "DSP-1"] and len(s["records"]) == 1


def test_agent_text_includes_options():
    assert agent_text({"reply_text": "¿Cuál?", "options": ["Oxxo", "Rappi"]}) == "¿Cuál?\nOxxo | Rappi"


def test_jev_down_fault_patches_deps():
    deps = SimpleNamespace(jev=object(), read=object(), write=object(), store=SimpleNamespace(disputes=1), policy=None)
    apply_fault(deps, "jev_down")
    with pytest.raises(JevError):
        deps.jev.decide({}, {})


def test_dynamo_fault_leaves_the_real_store_untouched():
    from bankagent.tools.write import WriteTools
    real = SimpleNamespace(disputes="real", handoffs="h", log="l")
    deps = SimpleNamespace(jev=None, read=None, write=None, store=real, policy=None)
    apply_fault(deps, "dynamo_throttle")
    assert isinstance(deps.write, WriteTools) and real.disputes == "real"


def test_unknown_fault_is_refused():
    with pytest.raises(ValueError):
        apply_fault(SimpleNamespace(), "nope")
