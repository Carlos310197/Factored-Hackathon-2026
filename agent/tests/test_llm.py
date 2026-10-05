from types import SimpleNamespace

import pytest

from bankagent.llm.client import LLMError, call_json
from bankagent.llm.compose import compose, open_questions
from bankagent.llm.config import load_models
from bankagent.llm.extract import extract
from tests.fakes import FakeLLM

M = load_models(env={})


def test_model_defaults_and_env_override():
    assert M["extract"].model == "openai.gpt-5-6-luna" and M["extract"].effort is None
    assert M["compose"].model == "openai.gpt-5-6-terra" and M["compose"].effort == "low"
    assert M["extract"].prompt_version == "extract.v1" and M["compose"].timeout_s == 20.0
    over = load_models(env={"LLM_COMPOSE_MODEL": "openai.gpt-5-5"})
    assert over["compose"].model == "openai.gpt-5-5"


def test_extract_request_shape_and_untrusted_wrapping():
    llm = FakeLLM()
    ex, call = extract(llm, M["extract"], "hola, ¿mi saldo?", "2026-06-17", [])
    kw = llm.calls[0]
    assert kw["model"] == "openai.gpt-5-6-luna"
    assert kw["response_format"]["type"] == "json_schema"
    assert kw["messages"][0]["role"] == "system"
    assert "<customer_message>\nhola, ¿mi saldo?\n</customer_message>" in kw["messages"][1]["content"]
    assert "as_of: 2026-06-17" in kw["messages"][1]["content"]
    assert ex.english_gloss == "EN: hola, ¿mi saldo?" and ex.language_detected == "es"
    assert call.usage == {"input_tokens": 100, "output_tokens": 20} and call.prompt_version == "extract.v1"


def test_compose_uses_json_schema_format_and_hides_fixed_block():
    llm = FakeLLM()
    receipts = [{"receipt_id": "RCP-1", "source": "dim_product", "as_of": "2026-06-17", "data": []}]
    out, _ = compose(llm, M["compose"], {"kind": "ask_confirmation", "fixed_block": "SUMMARY"}, receipts, "es")
    kw = llm.calls[0]
    assert kw["response_format"]["type"] == "json_schema" and kw["model"] == "openai.gpt-5-6-terra"
    assert "SUMMARY" not in kw["messages"][1]["content"] and '"has_fixed_block": true' in kw["messages"][1]["content"]
    assert out.reply_text == "[ask_confirmation]" and out.claims[0]["receipt_ids"] == ["RCP-1"]


def test_compose_passes_feedback():
    llm = FakeLLM()
    compose(llm, M["compose"], {"kind": "answer"}, [], "pt", feedback=["Unsupported claim: x"])
    assert "<feedback>" in llm.calls[0]["messages"][1]["content"]


def test_open_questions_capped_at_three():
    qs, _ = open_questions(FakeLLM(), M["compose"], "I don't recognize a charge", ["reports_unauthorized_use"], [])
    assert qs == ["Which card was used?"]


def test_connection_error_raises_llm_error():
    with pytest.raises(LLMError):
        extract(FakeLLM(fail={"extract"}), M["extract"], "hola", "2026-06-17", [])


def test_invalid_json_and_truncation_raise():
    def client(finish_reason, text):
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish_reason)],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1)
        )
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: resp)))

    with pytest.raises(LLMError, match="invalid JSON"):
        call_json(client("stop", "not json"), M["extract"], "s", "u", {"type": "object"})
    with pytest.raises(LLMError, match="truncated"):
        call_json(client("length", "{}"), M["extract"], "s", "u", {"type": "object"})
