"""Unload curated tables as parquet to <stage>/<run_id>/<table>/ and flip <stage>/latest.json. Usage: uv run python -m pipeline.export --run-id <id>"""
import argparse
import json
import sys
from datetime import datetime, timezone

EXPORT_TABLES = ["dim_customer", "dim_product", "fct_transaction", "fct_complaint", "seed_decline_reason"]


def table_columns(cur, schema: str, table: str) -> list[str]:
    rows = cur.execute(
        "select column_name from information_schema.columns where table_schema = %s and table_name = %s order by ordinal_position",
        (schema.upper(), table.upper())).fetchall()
    return [r[0] for r in rows]


def export_select(table: str, columns: list[str]) -> str:
    cols = ", ".join(f'{c} as "{c.lower()}"' for c in columns)
    # Sorted by customer so the agent's DuckDB reads can skip row groups per customer (agent spec §7.1).
    order = " order by CUSTOMER_ID" if "CUSTOMER_ID" in (c.upper() for c in columns) else ""
    return f"select {cols} from CURATED.{table.upper()}{order}"


def unload_table(cur, table: str, run_id: str, stage: str) -> int:
    cols = table_columns(cur, "CURATED", table)
    res = cur.execute(
        f"copy into @{stage}/{run_id}/{table}/data_ from ({export_select(table, cols)}) "
        f"file_format = (type = parquet) header = true overwrite = true max_file_size = 268435456").fetchall()
    return sum(int(r[0]) for r in res)  # rows_unloaded per file


def build_pointer(run_id: str, exported_at: str, max_process_date: str, tables: dict[str, int]) -> dict:
    return {"run_id": run_id, "exported_at": exported_at, "max_process_date": max_process_date, "tables": tables}


def write_pointer(cur, pointer: dict, stage: str) -> None:
    payload = json.dumps(pointer).replace("'", "''")
    cur.execute(
        f"copy into @{stage}/latest.json from (select parse_json('{payload}')) "
        "file_format = (type = json compression = none) single = true overwrite = true")


def list_runs(cur, stage: str) -> list[str]:
    rows = cur.execute(f"list @{stage}/").fetchall()
    runs = set()
    for r in rows:
        rel = r[0].split("/serving/", 1)[-1] if "/serving/" in r[0] else r[0].split("/", 1)[-1]
        parts = rel.split("/")
        if len(parts) >= 3:
            runs.add(parts[0])
    return sorted(runs)


def runs_to_prune(runs: list[str], keep: int = 3) -> list[str]:
    return sorted(runs)[:-keep] if len(runs) > keep else []


def prune_runs(cur, stage: str, keep: int = 3) -> list[str]:
    old = runs_to_prune(list_runs(cur, stage), keep)
    for r in old:
        cur.execute(f"remove @{stage}/{r}/")
    return old


def run_export(conn, run_id: str, stage: str = "RAW.SERVING_STAGE") -> dict:
    cur = conn.cursor()
    counts = {}
    for t in EXPORT_TABLES:
        counts[t] = unload_table(cur, t, run_id, stage)   # any failure raises before the pointer moves
        print(f"unloaded {t}: {counts[t]} rows", file=sys.stderr)
    max_pd = cur.execute("select to_varchar(max(process_date), 'YYYY-MM-DD') from CURATED.FCT_TRANSACTION").fetchone()[0]
    pointer = build_pointer(run_id, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), max_pd, counts)
    write_pointer(cur, pointer, stage)
    conn.commit()
    prune_runs(cur, stage, keep=3)
    return pointer


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pipeline.connect import get_connection

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--database", default=None)
    ap.add_argument("--stage", default="RAW.SERVING_STAGE")
    a = ap.parse_args()
    with get_connection(a.database) as conn:
        print(json.dumps(run_export(conn, a.run_id, a.stage)))
