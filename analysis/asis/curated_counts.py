"""Runs reconcile.sql read-only against LATAM_BANK (live Snowflake)."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))  # repo root, for pipeline.connect
from pipeline.connect import get_connection  # noqa: E402

sql = (HERE / "reconcile.sql").read_text(encoding="utf-8")
body = re.sub(r"--[^\n]*", "", sql).strip().rstrip(";")
if not body.lower().startswith("select") or ";" in body or re.search(
        r"\b(insert|update|delete|merge|create|alter|drop|truncate|copy|put|remove|grant)\b", body, re.I):
    raise SystemExit("reconcile.sql must be a single read-only SELECT")
with get_connection("LATAM_BANK") as conn:
    counts = json.loads(conn.cursor().execute(sql).fetchone()[0])
(HERE / "out" / "curated_counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(counts, indent=2, sort_keys=True))
