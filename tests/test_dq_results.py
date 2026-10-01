from pipeline.dq_results import parse_dbt_results

RUN = {"results": [
    {"unique_id": "test.latam_bank.unique_stg_transactions_transaction_id.abc", "status": "pass", "failures": 0},
    {"unique_id": "test.latam_bank.warn_unexpected_columns", "status": "warn", "failures": 2},
    {"unique_id": "model.latam_bank.dim_customer", "status": "success", "failures": None},
]}
MANIFEST = {"nodes": {
    "test.latam_bank.unique_stg_transactions_transaction_id.abc": {"name": "unique_stg_transactions_transaction_id", "config": {"severity": "ERROR"}, "depends_on": {"nodes": ["model.latam_bank.stg_transactions"]}},
    "test.latam_bank.warn_unexpected_columns": {"name": "warn_unexpected_columns", "config": {"severity": "warn"}, "depends_on": {"nodes": []}},
}}

def test_parse_only_tests_with_model_and_severity():
    rows = parse_dbt_results(RUN, MANIFEST)
    assert rows == [
        {"test_name": "unique_stg_transactions_transaction_id", "model": "stg_transactions", "severity": "error", "status": "pass", "failures": 0},
        {"test_name": "warn_unexpected_columns", "model": None, "severity": "warn", "status": "warn", "failures": 2},
    ]
