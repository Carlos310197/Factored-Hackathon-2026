"""Results are cached one JSON line per case, so an interrupted run resumes without re-calling Jev."""
import json
from pathlib import Path

from bankagent.decisions.jev import JevError
from bankagent.decisions.understand import build_understand_request, select_candidates
from bankagent.resolver.model import Resolver

SYSTEMS = ("B2", "P")


def session_facts(lang: str) -> dict:
    return {"awaiting": "none", "clarification": None, "pending_request": None, "offered_queued_request": None,
            "recent_exchanges": [], "reply_language": lang}


def jev_request(row: dict, qset: dict, scores: dict[str, float] | None = None):
    mentions = row["extraction"]["mentions"] or {}
    return build_understand_request(qset, message=row["message"], gloss=row["extraction"].get("english_gloss"),
                                    gloss_mode="original_plus_gloss", session_facts=session_facts(row["lang"]),
                                    candidates=select_candidates(row["candidates"], mentions),
                                    awaiting_confirmation=False, scores=scores)


def to_target(result, aliases: dict[str, str]) -> dict:
    a = result.answers["target_transaction"]
    return {"label": aliases.get(a.label, a.label), "probs": {aliases.get(k, k): p for k, p in a.probabilities.items()}}


def runs_path(root: Path, set_name: str, system: str, repeat: int) -> Path:
    return root / set_name / f"{system}_r{repeat}.jsonl"


def load_runs(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {r["case_id"]: r for r in (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip())}


def run_system(rows: list[dict], system: str, jev, qsets: dict[str, dict], resolver: Resolver | None,
               path: Path) -> int:
    if system not in SYSTEMS:
        raise ValueError(system)
    done, new = load_runs(path), 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            if row["case_id"] in done:
                continue
            scores = None
            if system == "P":
                cands = select_candidates(row["candidates"], row["extraction"]["mentions"] or {})
                scores = resolver.score(cands, row["extraction"]["mentions"]).probs
            state, questions, aliases = jev_request(row, qsets[system], scores)
            try:
                res = jev.decide(state, questions)
                rec = {"answer": to_target(res, aliases), "latency_ms": res.latency_ms, "usage": res.usage,
                       "state_hash": res.state_hash, "model": res.model}
            except JevError as e:
                rec = {"answer": None, "error": str(e)}
            f.write(json.dumps({"case_id": row["case_id"], "system": system, "question_set": qsets[system]["version"],
                                **rec}, ensure_ascii=False) + "\n")
            f.flush()
            new += 1
    return new
