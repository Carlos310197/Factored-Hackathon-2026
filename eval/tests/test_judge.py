import json
from types import SimpleNamespace

from evalkit.judge import (PACKET_FIELDS, REPLY_FIELDS, cohen_kappa, human_sheet, items_for, judge_item, judge_role,
                           validate)


def fake_client(data):
    def create(**kw):
        message = SimpleNamespace(content=json.dumps(data))
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")],
                               usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


CFG = {"judge": {"model": "anthropic.claude-sonnet-5-5", "prompt_version": "judge.v1"}}


def test_kappa():
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == 0.5
    assert cohen_kappa(["a", "a"], ["a", "a"]) == 1.0
    assert cohen_kappa([], []) is None


def test_items_for_a_conversation():
    rec = {"goal_id": "H001", "rep": 1, "language": "es",
           "turns": [{"reply": {"reply_text": "Hola", "language": "es"}}, {"reply": {"reply_text": "Listo", "language": "es"}}],
           "after": {"records": [{"kind": "tool", "payload": {"rows": 2}}],
                     "handoffs": [{"handoff_id": "HND-1", "customer_request": {"original": "x", "en": "x"}}]}}
    items = items_for(rec, language="es")
    assert [i["kind"] for i in items] == ["reply", "packet"]
    assert items[0]["content"] == "Listo" and items[0]["evidence"] == [{"rows": 2}]


def test_judge_item_parses_structured_output():
    role = judge_role(CFG)
    item = {"item_id": "H001-r1-reply", "kind": "reply", "language": "es", "content": "Listo", "evidence": []}
    out = judge_item(fake_client({"language_correct": True, "faithful": False, "note": "n"}), role, item)
    assert out["verdict"]["faithful"] is False and out["model"] == "anthropic.claude-sonnet-5-5"


def test_human_sheet_is_stratified_and_validation_computes_kappa():
    judgments = [{"item_id": f"r{i}", "kind": "reply", "language": "es" if i % 2 else "pt", "content": "x",
                  "verdict": {"language_correct": True, "faithful": i % 3 == 0}} for i in range(30)] + \
                [{"item_id": f"p{i}", "kind": "packet", "language": "es" if i % 2 else "pt", "content": "{}",
                  "verdict": {f: 2 for f in PACKET_FIELDS}} for i in range(30)]
    sheet = human_sheet(judgments, n=40)
    assert len(sheet) == 40 and sum(r["kind"] == "packet" for r in sheet) == 20
    assert {f"human_{f}" for f in REPLY_FIELDS + PACKET_FIELDS} <= set(sheet[0])
    labeled = [r | {"human_faithful": str(next(j for j in judgments if j["item_id"] == r["item_id"])["verdict"].get("faithful", "")).lower()}
               for r in sheet]
    v = validate(judgments, labeled)
    assert v["faithful"]["kappa"] == 1.0 and v["faithful"]["n"] == 20


def responses_transport(handler):
    import httpx
    return httpx.Client(transport=httpx.MockTransport(handler))


def responses_ok(text, status="completed", usage=None):
    import httpx
    out = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}]
    return httpx.Response(200, json={"status": status, "output": out,
                                     "usage": usage or {"input_tokens": 10, "output_tokens": 5}})


def test_responses_adapter_translates_an_openai_shaped_call():
    from evalkit.judge import OpenCodeResponsesClient
    seen = {}

    def h(req):
        import json as _json
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], _json.loads(req.content)
        return responses_ok('{"a": 1}')

    client = OpenCodeResponsesClient("https://x.test/v1/", "key", http=responses_transport(h))
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    resp = client.chat.completions.create(
        model="gpt-x", max_tokens=2000,
        messages=[{"role": "system", "content": "RUBRIC"}, {"role": "user", "content": "ITEM"}],
        response_format={"type": "json_schema", "json_schema": {"name": "response", "schema": schema}})
    assert seen["url"] == "https://x.test/v1/responses" and seen["auth"] == "Bearer key"
    assert seen["body"]["model"] == "gpt-x" and seen["body"]["max_output_tokens"] == 2000
    assert "temperature" not in seen["body"]
    assert [m["role"] for m in seen["body"]["input"]] == ["system", "user"]
    assert "RUBRIC" in seen["body"]["input"][0]["content"] and '"integer"' in seen["body"]["input"][0]["content"]
    assert resp.choices[0].message.content == '{"a": 1}' and resp.choices[0].finish_reason == "stop"
    assert resp.usage.prompt_tokens == 10 and resp.usage.completion_tokens == 5


def test_responses_adapter_reports_incomplete_as_length():
    from evalkit.judge import OpenCodeResponsesClient
    client = OpenCodeResponsesClient("https://x.test/v1", "k", http=responses_transport(
        lambda req: responses_ok("{", status="incomplete")))
    resp = client.chat.completions.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "x"}])
    assert resp.choices[0].finish_reason == "length"


def test_responses_adapter_retries_5xx_once_and_raises_on_client_errors():
    import httpx
    import pytest
    from bankagent.llm.client import LLMError
    from evalkit.judge import OpenCodeResponsesClient
    calls = []

    def flaky(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else responses_ok('{"ok": true}')

    ok = OpenCodeResponsesClient("https://x.test/v1", "k", http=responses_transport(flaky))
    assert ok.chat.completions.create(model="m", max_tokens=5, messages=[{"role": "user", "content": "x"}]
                                      ).choices[0].message.content == '{"ok": true}' and len(calls) == 2
    bad = OpenCodeResponsesClient("https://x.test/v1", "k", http=responses_transport(lambda req: httpx.Response(400)))
    with pytest.raises(LLMError, match="400"):
        bad.chat.completions.create(model="m", max_tokens=5, messages=[{"role": "user", "content": "x"}])


def test_judge_item_works_through_the_responses_adapter():
    from evalkit.judge import OpenCodeResponsesClient
    client = OpenCodeResponsesClient("https://x.test/v1", "k", http=responses_transport(
        lambda req: responses_ok(json.dumps({"language_correct": True, "faithful": True, "note": "ok"}))))
    item = {"item_id": "H001-r1-reply", "kind": "reply", "language": "es", "content": "Listo", "evidence": []}
    out = judge_item(client, judge_role(CFG), item)
    assert out["verdict"]["faithful"] is True and out["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_run_judge_keeps_record_order_with_several_workers():
    from evalkit.judge import run_judge
    recs = [{"goal_id": f"G{i}", "rep": 1, "end_reason": "done", "turns": [{"reply": {"reply_text": f"hola {i}"}}],
             "after": {"records": [], "handoffs": []}} for i in range(12)]
    out = run_judge(recs, {r["goal_id"]: "es" for r in recs},
                    fake_client({"language_correct": True, "faithful": True, "note": "n"}), judge_role(CFG), workers=4)
    assert [j["item_id"] for j in out] == [f"G{i}-r1-reply" for i in range(12)]
