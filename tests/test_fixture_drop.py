"""Proof of update correctness on a labeled synthetic drop. Needs Snowflake env vars; runs in CI."""
import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from fixtures.make_fixture import write_phase
from pipeline.connect import get_connection
from pipeline.export import run_export
from pipeline.load import TABLES as ALL_RAW, run_load

pytestmark = pytest.mark.snowflake
DB, STAGE, SERVING = "LATAM_FIXTURE", "RAW.FIXTURE_STAGE", "RAW.SERVING_STAGE"
TABLES = {"TRANSACTIONS": "transactions/"}


def dbt(*args):
    env = {**os.environ, "DBT_PROFILES_DIR": "dbt"}
    r = subprocess.run(["uv", "run", "dbt", *args, "--target", os.environ.get("DBT_FIXTURE_TARGET", "fixture"), "--project-dir", "dbt",
                        "--vars", "{quarantine_max_ratio: 0.05}"], env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def upload(cur, files):
    for p in files:
        rel = p.relative_to(p.parents[4])  # transactions/year=.../file.csv
        cur.execute(f"put file://{p} @{STAGE}/{rel.parent.as_posix()}/ auto_compress=false overwrite=true")


@pytest.fixture(scope="module")
def conn():
    with get_connection(DB) as c:
        yield c


def reset(cur):
    cur.execute(f"remove @{STAGE}/")
    cur.execute(f"remove @{SERVING}/")
    for t in ALL_RAW:  # every RAW table: other live tests (e.g. test_load_live) leave rows behind
        cur.execute(f"truncate table RAW.{t}")
    cur.execute("delete from META.RUN_MANIFEST")
    cur.execute("delete from META.DQ_RESULTS")


def test_fixture_drop_end_to_end(conn, tmp_path):
    cur = conn.cursor()
    reset(cur)
    # phase 1: original day 17
    upload(cur, write_phase(tmp_path / "p1", 1))
    s1 = run_load(conn, "fix-1", STAGE, "", TABLES)
    assert s1["TRANSACTIONS"] == {"new": 1, "restated": 0, "skipped": 0}
    rc, out = dbt("build", "--select", "staging", "curated", "seed_decline_reason", "--exclude", "test_name:relationships")
    assert rc == 0, out
    p1 = run_export(conn, "fix-1", SERVING)
    assert p1["tables"]["fct_transaction"] == 20

    # phase 2: restated day 17 (+3 changed, +5 dups), new day 18, extra column day 19, bad amount day 20, header-only day 21
    upload(cur, write_phase(tmp_path / "p2", 2))
    s2 = run_load(conn, "fix-2", STAGE, "", TABLES)
    assert s2["TRANSACTIONS"] == {"new": 4, "restated": 1, "skipped": 0}
    rc, out = dbt("build", "--select", "staging", "curated", "seed_decline_reason", "warn_unexpected_columns", "assert_quarantine_rate", "--exclude", "test_name:relationships")
    assert rc == 0, out
    subprocess.run(["uv", "run", "python", "-m", "pipeline.dq_results", "--run-id", "fix-2", "--database", DB], check=True)
    # quarantine gate is per run: 1 bad row of 44 loaded in fix-2 is 2.3% (> 2%), though only 1.5% of everything ever loaded
    env = {**os.environ, "DBT_PROFILES_DIR": "dbt"}
    gate = subprocess.run(["uv", "run", "dbt", "test", "--select", "assert_quarantine_rate", "--target", os.environ.get("DBT_FIXTURE_TARGET", "fixture"),
                           "--project-dir", "dbt", "--vars", "{quarantine_max_ratio: 0.02}"], env=env, capture_output=True, text=True)
    assert gate.returncode != 0, gate.stdout

    q = lambda sql: cur.execute(sql).fetchall()
    # new partition loaded
    assert q("select count(*) from STAGING.STG_TRANSACTIONS where process_date = '2026-06-18'")[0][0] == 10
    # duplicates collapsed, and the key the restated file dropped is gone: 19 unique keys for day 17
    assert q("select count(*), count(distinct transaction_id) from STAGING.STG_TRANSACTIONS where process_date = '2026-06-17'")[0] == (19, 19)
    # restated rows updated
    assert q("select count(*) from STAGING.STG_TRANSACTIONS where process_date = '2026-06-17' and transaction_status = 'Reversed'")[0][0] == 3
    # extra column landed in RAW, absent from staging, recorded as warn
    assert q("select count(*) from information_schema.columns where table_schema='RAW' and table_name='TRANSACTIONS' and column_name='MERCHANT_COUNTRY'")[0][0] == 1
    assert q("select count(*) from information_schema.columns where table_schema='STAGING' and table_name='STG_TRANSACTIONS' and column_name='MERCHANT_COUNTRY'")[0][0] == 0
    assert q("select status from META.DQ_RESULTS where run_id='fix-2' and test_name='warn_unexpected_columns'")[0][0] == "warn"
    # bad amount quarantined with reason
    assert q("select reason from STAGING.QUARANTINE where pk_value = 'FIX-20-0000'")[0][0] == "cast_failed:amount"
    # manifest records modes; header-only file loaded 0 rows as new
    modes = dict(q("select mode, count(*) from META.RUN_MANIFEST where run_id='fix-2' group by 1"))
    assert modes == {"new": 4, "restated": 1}
    assert q("select rows_loaded from META.RUN_MANIFEST where run_id='fix-2' and file_path like '%20260621%'")[0][0] == 0
    # pointer advanced and parquet columns are lowercase
    p2 = run_export(conn, "fix-2", SERVING)
    assert p2["run_id"] == "fix-2" and p2["tables"]["fct_transaction"] == 19 + 10 + 5 + 4
    local = tmp_path / "dl"; local.mkdir()
    cur.execute(f"get @{SERVING}/fix-2/fct_transaction/ file://{local}/")
    import pyarrow.parquet as pq
    f = next(local.glob("*.parquet"))
    assert "transaction_id" in pq.read_schema(f).names
