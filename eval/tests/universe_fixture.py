"""SYNTHETIC serving universe for evalkit tests: labeled test data, NOT organizer records."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

from evalkit.splits import customer_split

AS_OF = date(2026, 6, 17)
RUN_ID = "eval-fixture-1"
COUNTRY_CODE = {"México": "MX", "Colombia": "CO", "Argentina": "AR"}
# (days_ago, type, amount, merchant, status, response_code, is_fraud, fraud_score)
PROFILES = {
    0: [(3, "Purchase", 100.00, "Oxxo", "Approved", "00", False, 10.0),      # hard pair: same merchant, amounts within 10%
        (10, "Purchase", 104.00, "Oxxo", "Approved", "00", False, 12.0),
        (2, "Purchase", 55.50, "Amazon", "Declined", "51", False, 9.0),
        (1, "Purchase", 20.00, "Rappi", "Pending", "00", False, 5.0)],
    1: [(5, "Purchase", 15.99, "Netflix", "Approved", "00", False, 8.0),
        (8, "Purchase", 900.00, "Liverpool", "Approved", "00", False, 14.0),  # amount_over_limit
        (4, "Withdrawal", 200.00, None, "Declined", "05", False, 6.0)],
    2: [(6, "Purchase", 60.00, "Steam", "Approved", "00", True, 55.0),        # fraud_flag + fraud_score_high
        (2, "Purchase", 12.50, "Uber", "Approved", "00", False, 8.0)],
    3: [],                                                                       # products, no transactions
}
DDL = {
    "dim_customer": "customer_id varchar, country varchar, segment varchar",
    "dim_product": "product_id varchar, customer_id varchar, product_type varchar, product_last4 varchar, "
                   "currency varchar, product_status varchar",
    "fct_transaction": "transaction_id varchar, transaction_ts timestamp, process_date date, product_id varchar, "
                       "customer_id varchar, transaction_type varchar, amount decimal(15,2), currency varchar, "
                       "amount_usd decimal(15,2), channel varchar, merchant_name varchar, transaction_city varchar, "
                       "transaction_status varchar, response_code varchar, is_fraud boolean, fraud_score double",
}


def ids_in_bucket(split: str, n: int, prefix: str) -> list[str]:
    out, k = [], 0
    while len(out) < n:
        cid = f"{prefix}{k:08d}"
        k += 1
        if customer_split(cid) == split:
            out.append(cid)
    return out


def _write(con, root: Path, name: str, rows: list[tuple]) -> None:
    con.execute(f"create or replace table {name} ({DDL[name]})")
    if rows:
        con.executemany(f"insert into {name} values ({', '.join('?' * len(rows[0]))})", rows)
    out = root / RUN_ID / name
    out.mkdir(parents=True, exist_ok=True)
    con.execute(f"copy {name} to '{(out / 'data_0.parquet').as_posix()}' (format parquet)")


def build_universe(root: Path, per_country: int = 60, dev_per_country: int = 12) -> Path:
    customers, products, txns, n = [], [], [], 0
    for split, count in (("test", per_country), ("dev", dev_per_country)):
        for country, code in COUNTRY_CODE.items():
            for cid in ids_in_bucket(split, count, prefix=f"CLI-{code}{split[0].upper()}"):
                profile = n % 4
                n += 1
                customers.append((cid, country, "Premium" if n % 3 == 0 else "Retail"))
                pid = f"PRD-{cid[4:]}"
                products.append((pid, cid, "Tarjeta de Crédito", f"{n % 10000:04d}", "USD", "Active"))
                for k, (days, ttype, amount, merchant, status, code_, fraud, score) in enumerate(PROFILES[profile]):
                    d = AS_OF - timedelta(days=days)
                    txns.append((f"TRX-{cid[4:]}T{k}", datetime(d.year, d.month, d.day, 12), d, pid, cid, ttype,
                                 amount, "USD", amount, "POS", merchant, "Ciudad", status, code_, fraud, score))
    con = duckdb.connect()
    _write(con, root, "dim_customer", customers)
    _write(con, root, "dim_product", products)
    _write(con, root, "fct_transaction", txns)
    (root / "latest.json").write_text(json.dumps({"run_id": RUN_ID, "max_process_date": AS_OF.isoformat()}))
    return root
