import pytest
from pipeline.export import EXPORT_TABLES, export_select, build_pointer, runs_to_prune, run_export

def test_export_tables():
    assert EXPORT_TABLES == ["dim_customer", "dim_product", "fct_transaction", "fct_complaint", "seed_decline_reason"]

def test_export_select_quotes_lowercase_and_sorts_by_customer():
    sql = export_select("DIM_CUSTOMER", ["CUSTOMER_ID", "COUNTRY"])
    assert sql == 'select CUSTOMER_ID as "customer_id", COUNTRY as "country" from CURATED.DIM_CUSTOMER order by CUSTOMER_ID'

def test_export_select_without_customer_column_is_unsorted():
    sql = export_select("SEED_DECLINE_REASON", ["RESPONSE_CODE", "REASON_KEY"])
    assert sql == 'select RESPONSE_CODE as "response_code", REASON_KEY as "reason_key" from CURATED.SEED_DECLINE_REASON'

def test_build_pointer_shape():
    p = build_pointer("r1", "2026-09-27T06:00:00Z", "2026-06-17", {"dim_customer": 150000})
    assert p == {"run_id": "r1", "exported_at": "2026-09-27T06:00:00Z", "max_process_date": "2026-06-17", "tables": {"dim_customer": 150000}}


def test_pointer_describes_its_build():
    from pipeline.export import contract_hash
    cols = {"dim_customer": ["customer_id", "country"]}
    p = build_pointer("r1", "t", "2026-06-17", {"dim_customer": 1}, git_sha="abc123",
                      contract_hash=contract_hash(cols), dq_summary={"pass": 40, "warn": 1})
    assert p["git_sha"] == "abc123" and p["dq_summary"] == {"pass": 40, "warn": 1}
    assert p["contract_hash"] == contract_hash({"dim_customer": ["customer_id", "country"]})  # deterministic
    assert contract_hash(cols) != contract_hash({"dim_customer": ["country", "customer_id"]})  # order matters

def test_runs_to_prune_keeps_newest_three_by_write_time():
    from datetime import datetime
    t = lambda h: datetime(2026, 10, 1, h)
    assert runs_to_prune({"a": t(1), "b": t(2), "c": t(3), "d": t(4)}) == ["a"]


def test_runs_to_prune_never_removes_the_live_run():
    # run ids don't sort ("-10" < "-9"), so write time decides; the live run always stays
    from datetime import datetime
    t = lambda h: datetime(2026, 10, 1, h)
    runs = {"zzz-old": t(1), "readme-check": t(2), "20261001-initial": t(3), "18000000000-1": t(4), "18000000000-10": t(5)}
    assert runs_to_prune(runs, keep=3, live="18000000000-10") == ["zzz-old", "readme-check"]
    assert "18000000000-1" not in runs_to_prune(runs, keep=1, live="18000000000-1")


def test_list_runs_uses_last_modified():
    from pipeline.export import list_runs
    class Cur:
        def execute(self, sql): return self
        def fetchall(self):
            return [("s3://b/serving/r1/fct_transaction/data_0.parquet", 1, "x", "Wed, 1 Oct 2026 10:00:00 GMT"),
                    ("s3://b/serving/r1/dim_customer/data_0.parquet", 1, "x", "Wed, 1 Oct 2026 10:05:00 GMT"),
                    ("s3://b/serving/latest.json", 1, "x", "Wed, 1 Oct 2026 10:06:00 GMT")]
    runs = list_runs(Cur(), "RAW.SERVING_STAGE")
    assert list(runs) == ["r1"] and runs["r1"].minute == 5

class FailingCursor:
    def __init__(self): self.executed = []
    def execute(self, sql, *a):
        self.executed.append(sql)
        if "copy into" in sql.lower() and "fct_transaction" in sql.lower():
            raise RuntimeError("boom")
        return self
    def fetchall(self):
        # COPY INTO returns rows_unloaded per file; column lookups return names
        return [(5,)] if "copy into" in self.executed[-1].lower() else [("CUSTOMER_ID",)]
    def fetchone(self): return (1,)

class Conn:
    def __init__(self, cur): self._cur = cur
    def cursor(self): return self._cur
    def commit(self): pass

def test_run_export_does_not_write_pointer_on_failure():
    cur = FailingCursor()
    with pytest.raises(RuntimeError):
        run_export(Conn(cur), "r1", stage="RAW.SERVING_STAGE")
    assert not any("latest.json" in s for s in cur.executed)
