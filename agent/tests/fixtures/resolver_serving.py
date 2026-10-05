"""SYNTHETIC long-history serving run for resolver tests: labeled test data, NOT organizer records.
200 customers, one transaction roughly every 9 days from 2023-07-01 to 2026-06-17."""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

import duckdb

from tests.fixtures.serving_fixture import DDL

RUN_ID = "resolver-fixture-1"
MERCHANTS = ["Tienda Don José", "Super Ahorro", "Internet Plus", "Cable TV", "Taxi Seguro", "Mercado Central"]
TYPES = ["Purchase", "Purchase", "Withdrawal", "Transfer", "Payment", "Deposit"]
CHANNELS = ["POS", "App", "ATM", "Web", "Branch"]
RATES = {"COP": 4000.0, "ARS": 900.0}
CITIES = ["Guadalajara", "Monterrey", "Bogotá", "Medellín", "Córdoba"]


def rows() -> list[tuple]:
    rng, out, n = random.Random(7), [], 0
    for c in range(200):
        cust, prod = f"CLI-HIST{c:08d}", f"PRD-HIST{c:08d}"
        currency = ["USD", "COP", "ARS"][c % 3]
        d = date(2023, 7, 1) + timedelta(days=rng.randrange(9))
        while d <= date(2026, 6, 17):
            ttype = rng.choice(TYPES)
            usd = round(rng.uniform(5, 900), 2)
            amount = usd if currency == "USD" else round(usd * RATES[currency], 2)
            out.append((f"TRX-HIST{n:016d}", f"{d.isoformat()} {rng.randrange(24):02d}:00:00", d.isoformat(), prod, cust,
                        ttype, None, amount, currency, usd, rng.choice(CHANNELS),
                        rng.choice(MERCHANTS) if ttype == "Purchase" else None, None, "México", rng.choice(CITIES),
                        "Approved", "00", None, False, 10.0))
            n += 1
            d += timedelta(days=rng.randrange(3, 16))
    return out


def build_history_serving(root: Path) -> Path:
    d = root / RUN_ID / "fct_transaction"
    d.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"create table fct_transaction ({DDL['fct_transaction']})")
    staged = root / "fct_transaction.csv"
    with staged.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows())
    con.execute(f"copy fct_transaction from '{staged}' (header false, nullstr '')")
    con.execute(f"copy fct_transaction to '{d / 'data_0.parquet'}' (format parquet)")
    (root / "latest.json").write_text(json.dumps({"run_id": RUN_ID, "exported_at": "2026-06-18T06:00:00Z",
                                                  "max_process_date": "2026-06-17", "tables": {}}))
    return root
