from types import SimpleNamespace

import pytest

from bankagent.llm.client import LLMError, LLMRefusal, call_json
from bankagent.llm.compose import compose, open_questions
from bankagent.llm.config import load_models
from bankagent.llm.extract import extract
from tests.fakes import FakeLLM

M = load_models(env={})


def test_model_defaults_and_env_override():
    assert M["extract"].model == "anthropic.claude-haiku-4-5" and M["extract"].effort is None
    assert M["compose"].model == "anthropic.claude-sonnet-5-5" and M["compose"].effort == "low"
    assert M["extract"].prompt_version == "extract.v1" and M["compose"].timeout_s == 20.0
    over = load_models(env={"LLM_COMPOSE_MODEL": "anthropic.claude-haiku-4-5"})
    assert over["compose"].model == "anthropic.claude-haiku-4-5"


def test_extract_request_shape_and_untrusted_wrapping():
    llm = FakeLLM()
    ex, call = extract(llm, M["extract"], "hola, ¿mi saldo?", "2026-06-17", [])
    kw = llm.calls[0]
    assert kw["model"] == "anthropic.claude-haiku-4-5" and "effort" not in kw["output_config"]
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and kw["timeout"] == 10.0
    assert "<customer_message>\nhola, ¿mi saldo?\n</customer_message>" in kw["messages"][0]["content"]
    assert "as_of: 2026-06-17" in kw["messages"][0]["content"]
    assert ex.english_gloss == "EN: hola, ¿mi saldo?" and ex.language_detected == "es"
    assert call.usage == {"input_tokens": 100, "output_tokens": 20} and call.prompt_version == "extract.v1"


def test_compose_uses_low_effort_and_hides_fixed_block():
    llm = FakeLLM()
    receipts = [{"receipt_id": "RCP-1", "source": "dim_product", "as_of": "2026-06-17", "data": []}]
    out, _ = compose(llm, M["compose"], {"kind": "ask_confirmation", "fixed_block": "SUMMARY"}, receipts, "es")
    kw = llm.calls[0]
    assert kw["output_config"]["effort"] == "low" and kw["model"] == "anthropic.claude-sonnet-5-5"
    assert "SUMMARY" not in kw["messages"][0]["content"] and '"has_fixed_block": true' in kw["messages"][0]["content"]
    assert out.reply_text == "[ask_confirmation]" and out.claims[0]["receipt_ids"] == ["RCP-1"]


def test_compose_passes_feedback():
    llm = FakeLLM()
    compose(llm, M["compose"], {"kind": "answer"}, [], "pt", feedback=["Unsupported claim: x"])
    assert "<feedback>" in llm.calls[0]["messages"][0]["content"]


def test_open_questions_capped_at_three():
    qs, _ = open_questions(FakeLLM(), M["compose"], "I don't recognize a charge", ["reports_unauthorized_use"], [])
    assert qs == ["Which card was used?"]


def test_refusal_raises():
    with pytest.raises(LLMRefusal):
        compose(FakeLLM(refuse={"compose"}), M["compose"], {"kind": "answer"}, [], "es")


def test_connection_error_raises_llm_error():
    with pytest.raises(LLMError):
        extract(FakeLLM(fail={"extract"}), M["extract"], "hola", "2026-06-17", [])


def test_invalid_json_and_truncation_raise():
    def client(stop, text):
        resp = SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))
        return SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: resp))

    with pytest.raises(LLMError, match="invalid JSON"):
        call_json(client("end_turn", "not json"), M["extract"], "s", "u", {"type": "object"})
    with pytest.raises(LLMError, match="truncated"):
        call_json(client("max_tokens", "{}"), M["extract"], "s", "u", {"type": "object"})
