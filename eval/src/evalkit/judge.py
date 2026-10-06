"""LLM judge for soft criteria only: reply language and faithfulness, handoff packet usefulness.
It never decides an outcome class or an unsafe outcome. Validated against human labels with Cohen's kappa."""
import argparse
import csv
import json
import random
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import httpx
from bankagent.llm.client import LLMError, call_json
from bankagent.llm.config import RoleConfig

RUBRIC = Path(__file__).resolve().parents[2] / "judge_rubric.md"
REPLY_FIELDS = ("language_correct", "faithful")
PACKET_FIELDS = ("request", "verified_facts", "actions_taken", "open_questions")
REPLY_SCHEMA = {"type": "object", "additionalProperties": False, "required": [*REPLY_FIELDS, "note"],
                "properties": {"language_correct": {"type": "boolean"}, "faithful": {"type": "boolean"},
                               "note": {"type": "string"}}}
PACKET_SCHEMA = {"type": "object", "additionalProperties": False, "required": [*PACKET_FIELDS, "note"],
                 "properties": {**{f: {"type": "integer", "enum": [0, 1, 2]} for f in PACKET_FIELDS},
                                "note": {"type": "string"}}}


class OpenCodeResponsesClient:
    """The judge model is served by OpenCode on the Responses API (Claude Sonnet 5.5 is not available to this account,
    and the Mantle endpoint behind bankagent's client does not serve it). This adapter exposes the chat.completions
    shape that call_json expects, so the judge reuses call_json's JSON parsing and error handling. No temperature is
    sent: the model rejects it."""

    def __init__(self, base_url: str, api_key: str, timeout_s: float = 90.0, http: httpx.Client | None = None):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._base, self._key = base_url.rstrip("/"), api_key
        self._http = http or httpx.Client(timeout=timeout_s)

    def _create(self, *, model, messages, max_tokens, response_format=None, **_):
        turns = [dict(m) for m in messages]
        if response_format:
            schema = json.dumps(response_format["json_schema"]["schema"])
            turns[0]["content"] += f"\n\nReply with only a JSON object that matches this JSON schema, with no other text:\n{schema}"
        body = {"model": model, "input": turns, "max_output_tokens": max_tokens}
        for attempt in (0, 1):
            try:
                r = self._http.post(f"{self._base}/responses", json=body, headers={"Authorization": f"Bearer {self._key}"})
            except httpx.TimeoutException as e:
                if attempt == 0:
                    continue
                raise LLMError("timeout") from e
            if r.status_code >= 500 and attempt == 0:
                continue
            if r.status_code != 200:
                raise LLMError(f"http {r.status_code}")
            break
        data = r.json()
        text = "".join(c.get("text", "") for o in data.get("output") or [] if o.get("type") == "message"
                       for c in o.get("content") or [] if c.get("type") == "output_text")
        usage = data.get("usage") or {}
        finish = "length" if data.get("status") == "incomplete" else "stop"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish)],
            usage=SimpleNamespace(prompt_tokens=usage.get("input_tokens", 0),
                                  completion_tokens=usage.get("output_tokens", 0)))


def make_judge_client(cfg: dict) -> OpenCodeResponsesClient:
    j = cfg["judge"]
    key = os.environ.get(j["api_key_env"], "")
    if not key:
        raise SystemExit(f"{j['api_key_env']} is not set")
    return OpenCodeResponsesClient(j["base_url"], key)


def judge_role(cfg: dict) -> RoleConfig:
    return RoleConfig(model=cfg["judge"]["model"], max_tokens=2000, prompt_version=cfg["judge"]["prompt_version"],
                      timeout_s=30, effort="low")


def items_for(rec: dict, language: str) -> list[dict]:
    items = []
    replies = [t["reply"] for t in rec.get("turns") or [] if (t["reply"].get("reply_text") or "").strip()]
    after = rec.get("after") or {}
    if replies:
        evidence = [r.get("payload") for r in after.get("records") or [] if r.get("kind") == "tool"]
        items.append({"item_id": f"{rec['goal_id']}-r{rec['rep']}-reply", "kind": "reply", "language": language,
                      "content": replies[-1]["reply_text"], "evidence": evidence})
    for h in after.get("handoffs") or []:
        items.append({"item_id": f"{rec['goal_id']}-r{rec['rep']}-{h['handoff_id']}", "kind": "packet",
                      "language": language, "content": json.dumps(h, ensure_ascii=False, default=str), "evidence": []})
    return items


def judge_item(client, role: RoleConfig, item: dict) -> dict:
    rubric = RUBRIC.read_text(encoding="utf-8")
    if item["kind"] == "reply":
        user = (f"Task: reply_check\n<language>{item['language']}</language>\n"
                f"<evidence>{json.dumps(item['evidence'], ensure_ascii=False, default=str)}</evidence>\n"
                f"<reply>{item['content']}</reply>")
        call = call_json(client, role, rubric, user, REPLY_SCHEMA)
    else:
        call = call_json(client, role, rubric, f"Task: packet_check\n<packet>{item['content']}</packet>", PACKET_SCHEMA)
    return {k: item[k] for k in ("item_id", "kind", "language", "content")} | {
        "verdict": call.data, "model": call.model, "prompt_version": call.prompt_version, "usage": call.usage}


def run_judge(records: list[dict], languages: dict[str, str], client, role: RoleConfig, workers: int = 1) -> list[dict]:
    items = [item for rec in records if rec.get("end_reason") not in ("harness_error", "persona_discarded")
             for item in items_for(rec, languages[rec["goal_id"]])]
    with ThreadPoolExecutor(max_workers=workers) as pool:  # map keeps the record order
        return list(pool.map(lambda item: judge_item(client, role, item), items))


def human_sheet(judgments: list[dict], n: int = 40, seed: int = 0) -> list[dict]:
    rng, per = random.Random(seed), n // 4
    rows = []
    for kind in ("reply", "packet"):
        for lang in ("es", "pt"):
            pool = [j for j in judgments if j["kind"] == kind and j["language"] == lang]
            rows += rng.sample(pool, min(per, len(pool)))
    blank = {f"human_{f}": "" for f in REPLY_FIELDS + PACKET_FIELDS}
    return [{"item_id": j["item_id"], "kind": j["kind"], "language": j["language"], "content": j["content"]} | blank
            for j in rows]


def cohen_kappa(a: list, b: list) -> float | None:
    if not a or len(a) != len(b):
        return None
    n, labels = len(a), sorted(set(a) | set(b), key=str)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 6)


def _norm(v) -> str:
    return str(v).strip().lower()


def validate(judgments: list[dict], labeled_rows: list[dict]) -> dict:
    by_id = {j["item_id"]: j for j in judgments}
    out = {}
    for f in REPLY_FIELDS + PACKET_FIELDS:
        pairs = [(_norm(by_id[r["item_id"]]["verdict"].get(f)), _norm(r[f"human_{f}"])) for r in labeled_rows
                 if r.get(f"human_{f}", "").strip() and r["item_id"] in by_id and f in by_id[r["item_id"]]["verdict"]]
        out[f] = {"kappa": cohen_kappa([p[0] for p in pairs], [p[1] for p in pairs]), "n": len(pairs)}
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--goals", type=Path, required=True)
    p.add_argument("--live", action="store_true")
    a = p.parse_args(argv)
    if not a.live:
        print("refusing: the judge calls an external model; rerun with --live after the owner approves")
        return 2
    from evalkit.config import load_config
    from evalkit.goals import read_goals
    cfg = load_config()
    languages = {c.goal_id: c.language for c in read_goals(a.goals)}
    records = [json.loads(line) for line in (a.run / "conversations.jsonl").read_text(encoding="utf-8").splitlines() if line]
    judgments = run_judge(records, languages, make_judge_client(cfg), judge_role(cfg),
                           workers=cfg["run"]["workers"])
    (a.run / "judgments.jsonl").write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in judgments),
                                           encoding="utf-8")
    sheet = human_sheet(judgments)
    with (a.run / "human_sheet.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sheet[0]))
        w.writeheader()
        w.writerows(sheet)
    print(f"{len(judgments)} judgments; human sheet with {len(sheet)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
