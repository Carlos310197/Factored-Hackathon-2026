import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb

WINDOW_DAYS = 60
TXN_COLS = ("transaction_id, transaction_ts, process_date, product_id, customer_id, transaction_type, amount, currency, "
            "amount_usd, channel, merchant_name, transaction_city, transaction_status, response_code, is_fraud, "
            "fraud_score")


def _plain(v):
    return float(v) if isinstance(v, Decimal) else v


class Universe:
    def __init__(self, serving_dir: Path):
        self.root = Path(serving_dir)
        pointer = json.loads((self.root / "latest.json").read_text(encoding="utf-8"))
        self.run_id = pointer["run_id"]
        self.as_of = date.fromisoformat(str(pointer["max_process_date"])[:10])
        self.c = duckdb.connect()
        for t in ("dim_customer", "dim_product", "fct_transaction"):
            self.c.execute(f"create view {t} as select * from "
                           f"read_parquet('{(self.root / self.run_id / t).as_posix()}/*.parquet')")

    def _dicts(self, sql: str, params=()) -> list[dict]:
        cur = self.c.execute(sql, list(params))
        cols = [d[0] for d in cur.description]
        return [{k: _plain(v) for k, v in zip(cols, row)} for row in cur.fetchall()]

    def customers(self) -> list[dict]:
        return self._dicts("select customer_id, country, segment from dim_customer order by customer_id")

    def products_by_customer(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for r in self._dicts("""select product_id, customer_id, product_type, product_last4, currency, product_status
                                from dim_product order by product_id"""):
            out.setdefault(r["customer_id"], []).append(r)
        return out

    def window_txns_by_customer(self) -> dict[str, list[dict]]:
        lo = self.as_of - timedelta(days=WINDOW_DAYS)
        out: dict[str, list[dict]] = {}
        for r in self._dicts(f"""select {TXN_COLS} from fct_transaction where process_date between ? and ?
                                 order by customer_id, transaction_ts desc, transaction_id""", [lo, self.as_of]):
            out.setdefault(r["customer_id"], []).append(r)
        return out
