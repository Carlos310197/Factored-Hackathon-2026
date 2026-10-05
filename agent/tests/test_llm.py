from types import SimpleNamespace

import pytest

from bankagent.llm.client import LLMError, call_json
from bankagent.llm.compose import compose, open_questions
from bankagent.llm.config import load_models
from bankagent.llm.extract import extract
from tests.fakes import FakeLLM

M = load_models(env={})


def _client(finish_reason, text):
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: resp)))


def test_model_defaults_and_env_override():
    assert M["extract"].model == "mistral.ministral-3-14b-instruct" and M["extract"].effort is None
    assert M["compose"].model == "openai.gpt-oss-120b" and M["compose"].effort == "low"
    assert M["extract"].prompt_version == "extract.v2" and M["compose"].timeout_s == 20.0
    over = load_models(env={"LLM_COMPOSE_MODEL": "openai.gpt-5-5"})
    assert over["compose"].model == "openai.gpt-5-5"


def test_extract_request_shape_and_untrusted_wrapping():
    llm = FakeLLM()
    ex, call = extract(llm, M["extract"], "hola, ¿mi saldo?", "2026-06-17", [])
    kw = llm.calls[0]
    assert kw["model"] == "mistral.ministral-3-14b-instruct"
    assert kw["response_format"]["type"] == "json_schema"
    assert kw["messages"][0]["role"] == "system"
    assert "<customer_message>\nhola, ¿mi saldo?\n</customer_message>" in kw["messages"][1]["content"]
    assert "as_of: 2026-06-17" in kw["messages"][1]["content"]
    assert ex.english_gloss == "EN: hola, ¿mi saldo?" and ex.language_detected == "es"
    assert call.usage == {"input_tokens": 100, "output_tokens": 20} and call.prompt_version == "extract.v2"


def test_compose_uses_json_schema_format_and_hides_fixed_block():
    llm = FakeLLM()
    receipts = [{"receipt_id": "RCP-1", "source": "dim_product", "as_of": "2026-06-17", "data": []}]
    out, _ = compose(llm, M["compose"], {"kind": "ask_confirmation", "fixed_block": "SUMMARY"}, receipts, "es")
    kw = llm.calls[0]
    assert kw["response_format"]["type"] == "json_schema" and kw["model"] == "openai.gpt-oss-120b"
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
    with pytest.raises(LLMError, match="invalid JSON"):
        call_json(_client("stop", "not json"), M["extract"], "s", "u", {"type": "object"})
    with pytest.raises(LLMError, match="truncated"):
        call_json(_client("length", "{}"), M["extract"], "s", "u", {"type": "object"})


def test_restarted_json_object_is_rejected_not_salvaged():
    """Regression (unit 25): a decoder restart mid-string leaves the first object unparseable; the extractor used to
    silently salvage the restarted fragment, so compose returned a reply missing its first clause (seen live on
    Bedrock: reply_text " 15.99 USD en StreamCo fue aprobada el 10 de junio de 2026.")."""
    raw = ('{"reply_text":"La transacción de{"reply_text":'
           '" 15.99 USD en StreamCo fue aprobada el 10 de junio de 2026.","claims":[]}')
    with pytest.raises(LLMError, match="ambiguous"):
        call_json(_client("stop", raw), M["compose"], "s", "u", {"type": "object"})


def test_duplicate_keys_in_json_object_are_rejected():
    """Regression (unit 25): a split value emitted as two members of the same key silently dropped the first half
    (json.loads keeps the last). Malformed model output is an error, never a reply."""
    raw = ('{"reply_text":"La transacción de","reply_text":'
           '" 15.99 USD en StreamCo fue aprobada el 10 de junio de 2026.","claims":[]}')
    with pytest.raises(LLMError, match="invalid JSON"):
        call_json(_client("stop", raw), M["compose"], "s", "u", {"type": "object"})


def test_json_with_text_preamble_still_parses():
    call = call_json(_client("stop", 'Sure! {"reply_text": "hola", "claims": []} — hope that helps'),
                     M["compose"], "s", "u", {"type": "object"})
    assert call.data["reply_text"] == "hola"


def test_extract_schema_has_nullable_hints():
    from bankagent.llm.extract import EXTRACT_SCHEMA
    m = EXTRACT_SCHEMA["properties"]["mentions"]
    assert {"type_hint", "channel_hint", "city"} <= set(m["required"])
    assert m["properties"]["type_hint"]["anyOf"][0]["enum"] == ["purchase", "withdrawal", "transfer", "payment", "deposit"]
    assert m["properties"]["channel_hint"]["anyOf"][1] == {"type": "null"}
    ex, _ = extract(FakeLLM(mentions={"type_hint": "withdrawal"}), M["extract"], "el retiro del cajero", "2026-06-17", [])
    assert ex.mentions["type_hint"] == "withdrawal" and ex.mentions["city"] is None


def test_dev_writer_role_is_configured():
    assert M["dev_writer"].prompt_version == "devwriter.v1" and M["dev_writer"].effort == "low"


def test_bedrock_client_remints_its_token_on_a_timer_and_on_auth_errors():
    import httpx
    import openai

    from bankagent.llm.client import RefreshingClient
    now = [0.0]
    minted = []
    calls = {"n": 0}
    ok = _client("stop", '{"a": 1}')

    def factory():
        minted.append(now[0])
        def create(**kw):
            calls["n"] += 1
            if calls["n"] == 1:  # the first token is already stale at the endpoint
                raise openai.AuthenticationError("expired", response=httpx.Response(401, request=httpx.Request("POST", "https://x")), body=None)
            return ok.chat.completions.create(**kw)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    c = RefreshingClient(factory, max_age_s=100, clock=lambda: now[0])
    schema = {"type": "object"}
    assert call_json(c, M["extract"], "s", "u", schema).data == {"a": 1}  # 401 → re-mint → retried once
    assert len(minted) == 2
    now[0] = 150
    call_json(c, M["extract"], "s", "u", schema)
    assert len(minted) == 3  # older than max_age → fresh token before the call


def test_auth_error_without_refresh_still_raises_llm_error():
    import httpx
    import openai

    def create(**kw):
        raise openai.AuthenticationError("no", response=httpx.Response(401, request=httpx.Request("POST", "https://x")), body=None)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(LLMError):
        call_json(client, M["extract"], "s", "u", {"type": "object"})
def test_doubled_opening_brace_is_accepted_but_a_restart_after_content_is_not():
    """gpt-oss on Bedrock often emits '{ {"a": 1}': a stray opener with nothing inside it. No content is dropped, so
    the complete object that follows is the answer. A restart after content (unit 25's regression) stays rejected."""
    out = call_json(_client("stop", '{\n  {"language_detected": "es"}'), M["extract"], "s", "u", {"type": "object"})
    assert out.data == {"language_detected": "es"}
    with pytest.raises(LLMError, match="ambiguous"):
        call_json(_client("stop", '{"a": "tex{"a": "x"}'), M["extract"], "s", "u", {"type": "object"})
