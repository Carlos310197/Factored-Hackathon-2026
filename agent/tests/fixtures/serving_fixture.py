"""SYNTHETIC serving fixture — labeled test data, NOT organizer records.
Mirrors the pipeline serving contract: <root>/latest.json + <root>/<run_id>/<table>/data_0.parquet."""
import json

from bankagent.data.contract import contract_hash
from pathlib import Path

import duckdb

AS_OF = "2026-06-17"
RUN_ID = "fixture-run-1"
C1, C2 = "CLI-FIXC00000001", "CLI-FIXC00000002"
P1, P2 = "PRD-FIXP00000001", "PRD-FIXP00000002"


def t(n: int) -> str:
    return f"TRX-FIX{n:017d}"


DDL = {
    "dim_customer": "customer_id varchar, country varchar, city varchar, state varchar, segment varchar, "
                    "detected_accent varchar, customer_status varchar, registration_date date, "
                    "accepts_marketing boolean, last_updated timestamp",
    "dim_product": "product_id varchar, customer_id varchar, product_type varchar, product_last4 varchar, "
                   "currency varchar, current_balance decimal(15,2), credit_limit decimal(15,2), interest_rate double, "
                   "opening_date date, expiration_date date, product_status varchar, has_linked_app boolean, "
                   "days_past_due integer, last_transaction_date date, last_updated timestamp",
    "fct_transaction": "transaction_id varchar, transaction_ts timestamp, process_date date, product_id varchar, "
                       "customer_id varchar, transaction_type varchar, transaction_category varchar, "
                       "amount decimal(15,2), currency varchar, amount_usd decimal(15,2), channel varchar, "
                       "merchant_name varchar, merchant_category varchar, transaction_country varchar, "
                       "transaction_city varchar, transaction_status varchar, response_code varchar, "
                       "decline_reason_key varchar, is_fraud boolean, fraud_score double",
    "fct_complaint": "complaint_id varchar, creation_ts timestamp, process_date date, customer_id varchar, "
                     "case_type varchar, category varchar, subcategory varchar, reception_channel varchar, "
                     "affected_product_id varchar, claimed_amount decimal(15,2), currency varchar, priority varchar, "
                     "status varchar, sla_breached boolean, resolution_days integer, resolution_satisfaction integer, "
                     "is_repeat_complainer boolean, first_response_ts timestamp, resolution_ts timestamp, "
                     "closing_ts timestamp",
    "seed_decline_reason": "response_code varchar, reason_key varchar, customer_text_es varchar, "
                           "customer_text_pt varchar, next_step varchar",
}

CUSTOMERS = [
    (C1, "México", "Ciudad de México", "CDMX", "Retail", "mexican", "Active", "2024-01-10", True, "2026-06-01 00:00:00"),
    (C2, "Colombia", "Bogotá", "Cundinamarca", "Premium", "colombian", "Active", "2023-05-02", False, "2026-06-01 00:00:00"),
]
PRODUCTS = [
    (P1, C1, "Tarjeta de Crédito", "4242", "USD", 1250.40, 5000.00, 0.42, "2024-01-10", "2029-01-31", "Active",
     True, 0, "2026-06-16", "2026-06-16 00:00:00"),
    (P2, C2, "Cuenta de Ahorros", "9911", "COP", 3500000.00, None, 0.05, "2023-05-02", None, "Active",
     True, 0, "2026-06-14", "2026-06-14 00:00:00"),
]


def _txn(n, ts, pd, prod, cust, ttype, amount, cur, usd, channel, merchant, country, city, status, code, dkey,
         fraud, score):
    return (t(n), ts, pd, prod, cust, ttype, None, amount, cur, usd, channel, merchant, None, country, city, status,
            code, dkey, fraud, score)


TRANSACTIONS = [
    _txn(100, "2026-06-10 20:01:00", "2026-06-10", P1, C1, "Purchase", 15.99, "USD", 15.99, "Web", "Netflix",
         "México", "Ciudad de México", "Approved", "00", None, False, 12.0),
    _txn(101, "2026-06-10 20:01:05", "2026-06-10", P1, C1, "Purchase", 15.99, "USD", 15.99, "Web", "Netflix",
         "México", "Ciudad de México", "Approved", "00", None, False, 12.5),
    _txn(102, "2026-06-15 13:00:00", "2026-06-15", P1, C1, "Purchase", 120.00, "USD", 120.00, "Web", "Amazon",
         "México", "Ciudad de México", "Declined", "51", "insufficient_funds", False, 8.0),
    _txn(103, "2026-06-16 09:00:00", "2026-06-16", P1, C1, "Payment", 50.00, "USD", 50.00, "App", "CFE",
         "México", "Ciudad de México", "Pending", "00", None, False, 5.0),
    _txn(104, "2026-06-01 18:00:00", "2026-06-01", P1, C1, "Purchase", 30.00, "USD", 30.00, "POS", "Cinepolis",
         "México", "Ciudad de México", "Reversed", "00", None, False, 9.0),
    _txn(105, "2026-06-12 11:00:00", "2026-06-12", P1, C1, "Purchase", 800.00, "USD", 800.00, "POS",
         "Electrónica Max", "México", "Guadalajara", "Approved", "00", None, False, 20.0),
    _txn(106, "2026-03-01 10:00:00", "2026-03-01", P1, C1, "Purchase", 25.00, "USD", 25.00, "POS", "Oxxo",
         "México", "Ciudad de México", "Approved", "00", None, False, 10.0),
    _txn(107, "2026-06-05 10:00:00", "2026-06-05", P1, C1, "Deposit", 300.00, "USD", 300.00, "Branch", None,
         "México", "Ciudad de México", "Approved", "00", None, False, 3.0),
    _txn(108, "2026-06-11 23:40:00", "2026-06-11", P1, C1, "Purchase", 60.00, "USD", 60.00, "Web", "Tienda X",
         "México", "Monterrey", "Approved", "00", None, True, 55.0),
    _txn(200, "2026-06-14 12:00:00", "2026-06-14", P2, C2, "Purchase", 45000.00, "COP", 11.25, "App", "Rappi",
         "Colombia", "Bogotá", "Approved", "00", None, False, 7.0),
]
COMPLAINTS = [
    ("CMP-FIX00000000000000001", "2026-06-12 09:00:00", "2026-06-12", C1, "Complaint", "Transactions",
     "Cobro indebido", "Call Center", P1, 20.00, "USD", "Medium", "In Process", False, None, None, False,
     "2026-06-12 12:00:00", None, None),
]
SEED = [
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
ROWS = {"dim_customer": CUSTOMERS, "dim_product": PRODUCTS, "fct_transaction": TRANSACTIONS,
        "fct_complaint": COMPLAINTS, "seed_decline_reason": SEED}


def write_run(root: Path, run_id: str = RUN_ID) -> None:
    con = duckdb.connect()
    for table, ddl in DDL.items():
        d = root / run_id / table
        d.mkdir(parents=True, exist_ok=True)
        con.execute(f"create or replace table {table} ({ddl})")
        rows = ROWS[table]
        con.executemany(f"insert into {table} values ({', '.join(['?'] * len(rows[0]))})", rows)
        con.execute(f"copy {table} to '{d / 'data_0.parquet'}' (format parquet)")
    con.close()


def write_pointer(root: Path, run_id: str = RUN_ID, max_process_date: str = AS_OF) -> None:
    (root / "latest.json").write_text(json.dumps({
        "run_id": run_id, "exported_at": "2026-06-18T06:00:00Z", "max_process_date": max_process_date,
        "tables": {k: len(v) for k, v in ROWS.items()}, "contract_hash": contract_hash()}))


def build_serving(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    write_run(root)
    write_pointer(root)
    return root
