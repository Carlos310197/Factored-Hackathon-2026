"""Persist dbt test outcomes into META.DQ_RESULTS."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_dbt_results(run_results: dict, manifest: dict) -> list[dict]:
    nodes = manifest.get("nodes", {})
    rows = []
    for r in run_results.get("results", []):
        uid = r["unique_id"]
        if not uid.startswith("test."):
            continue
        node = nodes.get(uid, {})
        models = [n.split(".")[-1] for n in node.get("depends_on", {}).get("nodes", []) if n.startswith("model.")]
        rows.append({
            "test_name": node.get("name", uid.split(".")[2]),
            "model": models[0] if models else None,
            "severity": str(node.get("config", {}).get("severity", "error")).lower(),
            "status": r["status"],
            "failures": int(r.get("failures") or 0),
        })
    return rows


def write(cur, run_id: str, rows: list[dict]) -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cur.executemany(
        "insert into META.DQ_RESULTS (run_id, test_name, model, severity, status, failures, ran_at) values (%s, %s, %s, %s, %s, %s, %s)",
        [(run_id, r["test_name"], r["model"], r["severity"], r["status"], r["failures"], now) for r in rows])
    return len(rows)


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pipeline.connect import get_connection

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--database", default=None)
    ap.add_argument("--target-dir", default="dbt/target")
    a = ap.parse_args()
    t = Path(a.target_dir)
    rows = parse_dbt_results(json.loads((t / "run_results.json").read_text()), json.loads((t / "manifest.json").read_text()))
    with get_connection(a.database) as conn:
        n = write(conn.cursor(), a.run_id, rows)
        conn.commit()
    print(f"dq_results: {n} rows")
