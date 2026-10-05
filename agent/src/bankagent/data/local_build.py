"""DEV ONLY: approximate the pipeline's serving export from the organizer CSVs on disk, so the agent can run before
the Snowflake pipeline is live. Follows the serving contract (data/contract.py), sorted by customer_id like the real
export, and drops every PII column. The authoritative export is the pipeline's (pipeline spec §5.4)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from bankagent.data.contract import contract_hash

# Team-authored, labeled synthetic seed (same meaning as the pipeline's seed_decline_reason).
SEED_ROWS = [
    ("00", "approved", "La transacción fue aprobada.", "A transação foi aprovada.", "none"),
    ("05", "do_not_honor", "El banco emisor no autorizó la transacción.", "O banco emissor não autorizou a transação.",
     "contact_bank"),
    ("14", "invalid_card", "El número de tarjeta no es válido.", "O número do cartão não é válido.",
     "check_card_details"),
    ("51", "insufficient_funds", "No había saldo o cupo suficiente al momento de la compra.",
     "Não havia saldo ou limite suficiente no momento da compra.", "add_funds_or_retry"),
    ("54", "expired_card", "La tarjeta estaba vencida al momento de la compra.",
     "O cartão estava vencido no momento da compra.", "request_replacement_card"),
]


def _csv(con, pattern: str) -> str:
    rel = f"read_csv('{pattern}', header=true, all_varchar=true, union_by_name=true)"
    cols = [r[0] for r in con.execute(f"describe select * from {rel}").fetchall()]
    sel = ", ".join(f'"{c}" as "{c.lstrip(chr(0xFEFF))}"' for c in cols)  # strip a BOM kept on the first header
    return f"(select {sel} from {rel})"


def _v(col: str, typ: str) -> str:
    return f"try_cast(nullif(trim({col}), '') as {typ})"


def _int(col: str) -> str:
    return f"try_cast({_v(col, 'double')} as integer)"


def _b(col: str) -> str:
    return f"(lower(trim({col})) = 'true')"


def _customers(src: str) -> str:
    return f"""select customer_id, country, city, state, segment, nullif(detected_accent, '') as detected_accent,
        customer_status, {_v('registration_date', 'date')} as registration_date,
        {_b('accepts_marketing')} as accepts_marketing, {_v('last_updated', 'timestamp')} as last_updated
        from {src} order by customer_id"""


def _products(src: str) -> str:
    return f"""select product_id, customer_id, product_type, right(product_number, 4) as product_last4, currency,
        {_v('current_balance', 'decimal(15,2)')} as current_balance, {_v('credit_limit', 'decimal(15,2)')} as credit_limit,
        {_v('interest_rate', 'double')} as interest_rate, {_v('opening_date', 'date')} as opening_date,
        {_v('expiration_date', 'date')} as expiration_date, product_status, {_b('has_linked_app')} as has_linked_app,
        {_int('days_past_due')} as days_past_due, {_v('last_transaction_date', 'date')} as last_transaction_date,
        {_v('last_updated', 'timestamp')} as last_updated from {src} order by customer_id"""


def _transactions(src: str, since: str) -> str:
    amount = _v("t.amount", "decimal(15,2)")
    return f"""select t.transaction_id, {_v('t.transaction_date', 'timestamp')} as transaction_ts,
        {_v('t.process_date', 'date')} as process_date, t.product_id, t.customer_id, t.transaction_type,
        nullif(t.transaction_category, '') as transaction_category, {amount} as amount, t.currency,
        coalesce({_v('t.amount_usd', 'decimal(15,2)')}, case when t.currency = 'USD' then {amount} end) as amount_usd,
        t.channel, nullif(t.merchant_name, '') as merchant_name, nullif(t.merchant_category, '') as merchant_category,
        t.transaction_country, nullif(t.transaction_city, '') as transaction_city, t.transaction_status,
        nullif(t.response_code, '') as response_code,
        case when t.transaction_status = 'Declined' then s.reason_key end as decline_reason_key,
        {_b('t.is_fraud')} as is_fraud, {_v('t.fraud_score', 'double')} as fraud_score
        from {src} t left join seed_decline_reason s on s.response_code = t.response_code
        where {_v('t.process_date', 'date')} >= DATE '{since}' order by t.customer_id, transaction_ts"""


def _complaints(src: str) -> str:
    return f"""select complaint_id, {_v('creation_date', 'timestamp')} as creation_ts,
        {_v('process_date', 'date')} as process_date, customer_id, case_type, category,
        nullif(subcategory, '') as subcategory, reception_channel, nullif(affected_product_id, '') as affected_product_id,
        {_v('claimed_amount', 'decimal(15,2)')} as claimed_amount, nullif(currency, '') as currency, priority, status,
        {_b('sla_breached')} as sla_breached, {_int('resolution_days')} as resolution_days,
        {_int('resolution_satisfaction')} as resolution_satisfaction, {_b('is_repeat_complainer')} as is_repeat_complainer,
        {_v('first_response_date', 'timestamp')} as first_response_ts, {_v('resolution_date', 'timestamp')} as resolution_ts,
        {_v('closing_date', 'timestamp')} as closing_ts from {src} order by customer_id"""


def build_local_serving(data_dir: Path, out_dir: Path, since: str = "2026-02-01", run_id: str | None = None) -> dict:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    run_id = run_id or "local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    con = duckdb.connect()
    con.execute("create table seed_decline_reason (response_code varchar, reason_key varchar, "
                "customer_text_es varchar, customer_text_pt varchar, next_step varchar)")
    con.executemany("insert into seed_decline_reason values (?, ?, ?, ?, ?)", SEED_ROWS)
    sources = {
        "dim_customer": _customers(_csv(con, f"{data_dir}/customers.csv")),
        "dim_product": _products(_csv(con, f"{data_dir}/products.csv")),
        "fct_transaction": _transactions(_csv(con, f"{data_dir}/transactions/*/*/*/*.csv"), since),
        "fct_complaint": _complaints(_csv(con, f"{data_dir}/complaints/*/*/*/*.csv")),
        "seed_decline_reason": "select * from seed_decline_reason order by response_code",
    }
    counts = {}
    for table, sql in sources.items():
        d = out_dir / run_id / table
        d.mkdir(parents=True, exist_ok=True)
        con.execute(f"copy ({sql}) to '{d / 'data_0.parquet'}' (format parquet, row_group_size 100000)")
        counts[table] = con.execute(f"select count(*) from read_parquet('{d}/*.parquet')").fetchone()[0]
    max_pd = con.execute(
        f"select max(process_date) from read_parquet('{out_dir / run_id}/fct_transaction/*.parquet')").fetchone()[0]
    columns = {t: [r[0] for r in con.execute(f"describe select * from read_parquet('{out_dir / run_id}/{t}/*.parquet')").fetchall()]
               for t in sources}
    pointer = {"run_id": run_id, "exported_at": datetime.now(timezone.utc).isoformat(),
               "max_process_date": max_pd.isoformat(), "tables": counts, "contract_hash": contract_hash(columns),
               "source": "local_build (DEV ONLY, not the pipeline export)"}
    (out_dir / "latest.json").write_text(json.dumps(pointer, indent=2))
    con.close()
    return pointer
