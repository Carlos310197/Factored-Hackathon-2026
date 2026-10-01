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

def test_runs_to_prune_keeps_newest_three():
    assert runs_to_prune(["20260925-a", "20260926-b", "20260927-c", "20260928-d"], keep=3) == ["20260925-a"]

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
