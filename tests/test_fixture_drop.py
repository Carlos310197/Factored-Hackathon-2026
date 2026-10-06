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


def upload(cur, files, base):
    for p in files:
        rel = p.relative_to(base)  # transactions/year=.../file.csv or customers.csv
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
    upload(cur, write_phase(tmp_path / "p1", 1), tmp_path / "p1")
    s1 = run_load(conn, "fix-1", STAGE, "", TABLES)
    assert s1["TRANSACTIONS"] == {"new": 1, "restated": 0, "skipped": 0}
    rc, out = dbt("build", "--select", "staging", "curated", "seed_decline_reason", "--exclude", "test_name:relationships")
    assert rc == 0, out
    p1 = run_export(conn, "fix-1", SERVING)
    assert p1["tables"]["fct_transaction"] == 20

    # phase 2: restated day 17 (+3 changed, +5 dups), new day 18, extra column day 19, bad amount day 20, header-only day 21
    upload(cur, write_phase(tmp_path / "p2", 2), tmp_path / "p2")
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

    # phase 3a: idempotent re-run over the same drop -> nothing reloaded, every table identical (count + content hash)
    tables = ["RAW.TRANSACTIONS", "META.RUN_MANIFEST", "STAGING.STG_TRANSACTIONS", "STAGING.QUARANTINE", "CURATED.FCT_TRANSACTION"]
    snap = lambda: {t: q(f"select count(*), hash_agg(*) from {t}")[0] for t in tables}
    before = snap()
    s3 = run_load(conn, "fix-3", STAGE, "", TABLES)
    assert s3["TRANSACTIONS"] == {"new": 0, "restated": 0, "skipped": 5}
    rc, out = dbt("build", "--select", "staging", "curated", "seed_decline_reason", "--exclude", "test_name:relationships")
    assert rc == 0, out
    assert snap() == before
    p3 = run_export(conn, "fix-3", SERVING)  # the pointer moves to the new run_id, but to identical content
    assert p3["tables"] == p2["tables"] and p3["contract_hash"] == p2["contract_hash"]
    assert p3["max_process_date"] == p2["max_process_date"]

    # phase 3b: orphan foreign key. Load the one customer and product the fixture points at, so relationships can run.
    upload(cur, write_phase(tmp_path / "p3", 3), tmp_path / "p3")
    dims = {"CUSTOMERS": "customers.csv", "PRODUCTS": "products.csv"}
    assert run_load(conn, "fix-4", STAGE, "", dims) == {t: {"new": 1, "restated": 0, "skipped": 0} for t in dims}
    full = ("build", "--select", "staging", "curated", "seed_decline_reason")  # relationships included, as in pipeline.yml
    rc, out = dbt(*full)
    assert rc == 0, out  # control: every FK resolves
    # day 22: FIX-22-0001 points at PRD-ORPHAN0001, which does not exist
    upload(cur, write_phase(tmp_path / "p4", 4), tmp_path / "p4")
    assert run_load(conn, "fix-5", STAGE, "", TABLES)["TRANSACTIONS"] == {"new": 1, "restated": 0, "skipped": 5}
    rc, out = dbt(*full)
    assert rc != 0, out  # the build fails; pipeline.yml then skips the export (tested in test_pipeline_workflows)
    results = json.loads(Path("dbt/target/run_results.json").read_text())["results"]
    failed = [r for r in results if r["status"] in ("fail", "error")]
    assert [r["unique_id"].split(".")[2] for r in failed] == ["relationships_stg_transactions_product_id__product_id__ref_stg_products_"], out
    assert failed[0]["failures"] == 1
    assert q(f"select from_field from {failed[0]['relation_name']}") == [("PRD-ORPHAN0001",)]  # store_failures keeps the evidence
    status = {r["unique_id"].split(".")[2]: r["status"] for r in results}
    assert status["fct_transaction"] == "skipped"  # the mart is not rebuilt over the orphan
    assert q("select count(*) from STAGING.STG_TRANSACTIONS where transaction_id = 'FIX-22-0001'")[0][0] == 1
    assert q("select count(*) from CURATED.FCT_TRANSACTION where transaction_id like 'FIX-22-%'")[0][0] == 0
    assert q("select count(*) from CURATED.FCT_TRANSACTION")[0][0] == p2["tables"]["fct_transaction"]
    assert q("select count(*) from STAGING.QUARANTINE where pk_value like 'FIX-22-%'")[0][0] == 0  # an FK break fails, it is not quarantined
