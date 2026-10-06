import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb

from bankagent.data.serving import ServingData, _jsonable
from bankagent.resolver.splits import ANCHORS, WINDOW_DAYS, customer_split
from bankagent.tools.read import TXN_FIELDS

MAX_BATCHES = 10


@dataclass(frozen=True)
class History:
    split: str
    customer_id: str
    anchor: str
    candidates: list[dict]


class TransactionSource:

    def __init__(self, serving_dir: str | Path):
        self.base = str(serving_dir).rstrip("/")
        self.run_id = ServingData(self.base).pointer().run_id
        self.con = duckdb.connect()
        self.con.execute(f"create view fct as select * from read_parquet('{self.base}/{self.run_id}/fct_transaction/*.parquet')")
        self._customers = [r[0] for r in self.con.execute("select distinct customer_id from fct order by 1").fetchall()]

    def customers(self, split: str) -> list[str]:
        return [c for c in self._customers if customer_split(c) == split]

    def windows(self, pairs: list[tuple[str, str]]) -> list[list[dict]]:
        if not pairs:
            return []
        self.con.execute("create or replace temp table pairs (case_no integer, customer_id varchar, anchor date)")
        self.con.executemany("insert into pairs values (?, ?, ?)", [(i, c, a) for i, (c, a) in enumerate(pairs)])
        cols = ", ".join(f"f.{c}" for c in TXN_FIELDS)
        cur = self.con.execute(
            f"select p.case_no, {cols} from pairs p join fct f on f.customer_id = p.customer_id "
            f"and f.process_date between p.anchor - interval {WINDOW_DAYS} day and p.anchor "
            "order by p.case_no, f.transaction_ts desc, f.transaction_id")
        out: list[list[dict]] = [[] for _ in pairs]
        for row in cur.fetchall():
            out[row[0]].append({c: _jsonable(v) for c, v in zip(TXN_FIELDS, row[1:])})
        return out


def _random_day(rng: random.Random, lo: date, hi: date) -> date:
    return lo + timedelta(days=rng.randrange((hi - lo).days + 1))


def sample_histories(source: TransactionSource, split: str, n: int, seed: int, min_candidates: int = 2) -> list[History]:
    rng = random.Random(f"{seed}:{split}")
    customers, (lo, hi) = source.customers(split), ANCHORS[split]
    if not customers:
        return []
    seen: set[tuple[str, str]] = set()
    out: list[History] = []
    for _ in range(MAX_BATCHES):
        need = n - len(out)
        if need <= 0:
            break
        pairs = []
        for _ in range(need * 3):
            pair = (rng.choice(customers), _random_day(rng, lo, hi).isoformat())
            if pair not in seen:
                seen.add(pair)
                pairs.append(pair)
        for (cust, anchor), cands in zip(pairs, source.windows(pairs)):
            if len(cands) >= min_candidates and len(out) < n:
                out.append(History(split, cust, anchor, cands))
    return out
