from datetime import date

import duckdb
import pytest

from bankagent.data.contract import CONTRACT
from bankagent.data.serving import ServingData, ServingError
from tests.fixtures.serving_fixture import RUN_ID, t


def test_pointer_reads_run_and_as_of(serving_root):
    p = ServingData(str(serving_root)).pointer()
    assert p.run_id == RUN_ID and p.max_process_date == date(2026, 6, 17)


def test_missing_pointer_is_serving_error(tmp_path):
    with pytest.raises(ServingError):
        ServingData(str(tmp_path)).pointer()


def test_fixture_matches_serving_contract(serving_root):
    for table, cols in CONTRACT.items():
        got = duckdb.sql(f"describe select * from read_parquet('{serving_root}/{RUN_ID}/{table}/*.parquet')").fetchall()
        assert [r[0] for r in got] == cols, table


def test_query_returns_json_safe_values(serving_root):
    row = ServingData(str(serving_root)).query(RUN_ID, "fct_transaction", "transaction_id = ?", [t(100)])[0]
    assert isinstance(row["amount"], float) and row["amount"] == 15.99
    assert row["process_date"] == "2026-06-10" and row["transaction_ts"].startswith("2026-06-10T20:01")


def test_rejects_unknown_table_and_unsafe_run_id(serving_root):
    sd = ServingData(str(serving_root))
    with pytest.raises(ValueError):
        sd.query(RUN_ID, "dim_secret", "1=1", [])
    with pytest.raises(ValueError):
        sd.query("x'; drop table y; --", "fct_transaction", "1=1", [])


def test_missing_run_folder_is_serving_error(serving_root):
    with pytest.raises(ServingError):
        ServingData(str(serving_root)).query("no-such-run", "fct_transaction", "1=1", [])


def test_pointer_with_a_different_contract_is_refused(serving_root):
    import json

    from bankagent.data.contract import contract_hash
    p = serving_root / "latest.json"
    good = json.loads(p.read_text())
    p.write_text(json.dumps(good | {"contract_hash": contract_hash()}))
    assert ServingData(str(serving_root)).pointer().run_id == RUN_ID  # matching hash: served
    p.write_text(json.dumps(good | {"contract_hash": "0" * 64}))
    with pytest.raises(ServingError, match="contract"):  # columns drifted: refuse rather than misread
        ServingData(str(serving_root)).pointer()
    p.write_text(json.dumps({k: v for k, v in good.items() if k != "contract_hash"}))
    with pytest.raises(ServingError, match="contract"):  # a pointer that doesn't name its columns is refused too
        ServingData(str(serving_root)).pointer()
    p.write_text(json.dumps(good))  # serving_root is shared by the session: leave it as found


def test_stale_pointer_is_logged_for_the_alarm(serving_root, caplog):
    """The daily pipeline moves latest.json; an export older than 2 days means it stopped (alarm: StalePointer)."""
    import json
    from datetime import datetime, timedelta, timezone

    p = serving_root / "latest.json"
    good = json.loads(p.read_text())
    fresh = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    p.write_text(json.dumps(good | {"exported_at": fresh}))
    with caplog.at_level("WARNING"):
        ServingData(str(serving_root)).pointer()
    assert not any("stale" in r.getMessage() for r in caplog.records)
    p.write_text(json.dumps(good | {"exported_at": "2026-06-18T06:00:00Z"}))
    with caplog.at_level("WARNING"):
        ServingData(str(serving_root)).pointer()
    assert any(r.getMessage() == "serving pointer is stale" for r in caplog.records)
    p.write_text(json.dumps(good))
