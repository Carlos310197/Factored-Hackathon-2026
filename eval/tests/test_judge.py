import json
from types import SimpleNamespace

from evalkit.judge import (PACKET_FIELDS, REPLY_FIELDS, cohen_kappa, human_sheet, items_for, judge_item, judge_role,
                           validate)


def fake_client(data):
    """Stub with the OpenAI chat.completions shape that bankagent.llm.client.call_json uses."""
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
