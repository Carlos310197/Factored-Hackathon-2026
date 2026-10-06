from pathlib import Path

import duckdb

WINDOW = ("2025-06-17", "2026-06-17")  # inclusive
MONTHS_IN_WINDOW = 12
SENTIMENT = {"Muy Positivo": "Very Positive", "Positivo": "Positive", "Neutral": "Neutral",
             "Negativo": "Negative", "Muy Negativo": "Very Negative"}
FACTS = {"interactions_all": "call_center_interactions", "surveys_all": "satisfaction_surveys",
         "complaints_all": "complaints", "digital_all": "digital_events", "transcripts_all": "call_transcripts"}
CUSTOMER_COLS = "customer_id, country, segment, detected_accent"  # PII columns are never selected
AGENT_COLS = "agent_id, agent_type, specialty, languages, work_shift, avg_csat, total_monthly_interactions"


def _csv(path: Path) -> str:
    return f"read_csv('{path.as_posix()}', all_varchar=true, union_by_name=true, hive_partitioning=false, header=true)"


def connect(data_dir: Path, window: tuple[str, str] = WINDOW) -> duckdb.DuckDBPyConnection:
    data_dir = Path(data_dir)
    if "data_backup" in str(data_dir):
        raise ValueError("the backup prefix is a different synthetic generation and is never read")
    lo, hi = window
    c = duckdb.connect()
    for view, table in FACTS.items():
        c.sql(f"create view {view} as select * from {_csv(data_dir / table / '**' / '*.csv')}")
    sentiment = " ".join(f"when '{k}' then '{v}'" for k, v in SENTIMENT.items())
    c.sql(f"""create view interactions_hist as select * replace (
                case detected_sentiment {sentiment} else nullif(trim(detected_sentiment), '') end as detected_sentiment,
                nullif(trim(customer_detected_accent), '') as customer_detected_accent)
              from interactions_all""")
    c.sql(f"create view interactions as select * from interactions_hist where process_date between '{lo}' and '{hi}'")
    for view in ("surveys", "complaints", "digital", "transcripts"):
        c.sql(f"create view {view} as select * from {view}_all where process_date between '{lo}' and '{hi}'")
    c.sql(f"create view customers as select {CUSTOMER_COLS} from {_csv(data_dir / 'customers.csv')}")
    c.sql(f"create view agents as select {AGENT_COLS} from {_csv(data_dir / 'service_agents.csv')}")
    return c
