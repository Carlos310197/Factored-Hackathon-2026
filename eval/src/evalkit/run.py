import argparse
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from evalkit.agent_runtime import build_eval_runtime, ensure_tables, table_prefix
from evalkit.config import ConfigError, load_config, require_live
from evalkit.conversation import TokenIssuer, run_conversation
from evalkit.faults import FAULTS
from evalkit.goals import GoalCard, read_goals, sha256_file
from evalkit.persona import PersonaClient

RUNS = Path(__file__).resolve().parents[2] / "runs"
_STATE: dict = {}
_LOCK = threading.Lock()


def pending(cards: list[GoalCard], reps: int, done: set[tuple[str, int]]) -> list[tuple[GoalCard, int]]:
    return [(c, r) for r in range(1, reps + 1) for c in cards if (c.goal_id, r) not in done]


def load_done(path: Path) -> set[tuple[str, int]]:
    if not Path(path).exists():
        return set()
    return {(d["goal_id"], d["rep"]) for d in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines()) if d}


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def manifest(run_id: str, goals_path: Path, reps: int, cfg: dict) -> dict:
    from bankagent.llm.config import load_models
    models = load_models()
    return {"run_id": run_id, "goals": str(goals_path), "goals_sha256": sha256_file(goals_path), "git_sha": _git_sha(),
            "reps": reps, "persona_model": cfg["persona"]["model"], "judge_model": cfg["judge"]["model"],
            "agent_models": {k: v.model for k, v in models.items()},
            "prompt_versions": {k: v.prompt_version for k, v in models.items()},
            "jev_model": os.environ.get("JEV_MODEL", "jev-1.13.0"),
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _init(cfg: dict, run_id: str, rep: int, tokens: dict) -> None:
    _STATE.update(cfg=cfg, prefix=table_prefix(run_id, rep), rep=rep, tokens=TokenIssuer(**tokens), runtimes={})


def _work(card_dict: dict) -> dict:
    card = GoalCard.from_dict(card_dict)
    st = _STATE
    try:
        key = card.fault if card.fault in FAULTS else None
        if key not in st["runtimes"]:
            st["runtimes"][key] = build_eval_runtime(st["cfg"], st["prefix"], key, st["tokens"])
        rt, store = st["runtimes"][key]
        from bankagent.app import handle
        return run_conversation(card, st["rep"], handle_fn=handle, rt=rt, store=store,
                                persona=PersonaClient.from_config(st["cfg"]["persona"]), tokens=st["tokens"])
    except Exception as e:
        return {"goal_id": card.goal_id, "rep": st["rep"], "turns": [], "end_reason": "harness_error",
                "error": f"{type(e).__name__}: {e}", "violations": [], "persona_usage": []}


def _append(path: Path, rec: dict) -> None:
    with _LOCK, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--goals", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--reps", type=int)
    p.add_argument("--workers", type=int)
    p.add_argument("--config", type=Path)
    p.add_argument("--live", action="store_true")
    a = p.parse_args(argv)
    if not a.live:
        print("refusing: this run calls the persona, Bedrock and Jev; rerun with --live after the owner approves")
        return 2
    cfg = load_config(a.config) if a.config else load_config()
    try:
        require_live(cfg)
    except ConfigError as e:
        print(f"config error: {e}")
        return 2
    reps, workers = a.reps or cfg["run"]["reps"], a.workers or cfg["run"]["workers"]
    out_dir = RUNS / a.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    conv = out_dir / "conversations.jsonl"
    if not (out_dir / "run.json").exists():
        (out_dir / "run.json").write_text(json.dumps(manifest(a.run_id, a.goals, reps, cfg), indent=2) + "\n")
    cards = read_goals(a.goals)
    tokens = TokenIssuer.generate(issuer="eval-idp", audience=cfg["agent"]["audience"])
    todo = pending(cards, reps, load_done(conv))
    print(f"{len(todo)} conversations to run")
    for rep in range(1, reps + 1):
        batch = [c for c, r in todo if r == rep]
        if not batch:
            continue
        ensure_tables(cfg, table_prefix(a.run_id, rep))
        with ProcessPoolExecutor(max_workers=workers, initializer=_init,
                                 initargs=(cfg, a.run_id, rep, asdict(tokens))) as ex:
            futures = [ex.submit(_work, asdict(c)) for c in batch]
            for k, f in enumerate(as_completed(futures), 1):
                rec = f.result()
                _append(conv, rec)
                print(f"rep {rep}: {k}/{len(batch)} {rec['goal_id']} {rec['end_reason']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
