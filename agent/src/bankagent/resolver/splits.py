"""Customers and anchor dates are disjoint across train / dev / test."""
import hashlib
from datetime import date

from bankagent.resolver.features import fold

WINDOW_DAYS = 60
ANCHORS = {"train": (date(2023, 9, 1), date(2025, 9, 30)),
           "dev": (date(2025, 10, 1), date(2026, 1, 31)),
           "test": (date(2026, 2, 1), date(2026, 6, 17))}
HARD_AMOUNT_PCT = 0.10


def customer_split(customer_id: str) -> str:
    bucket = hashlib.sha256(customer_id.encode("utf-8")).digest()[0] % 10
    return "train" if bucket <= 7 else ("dev" if bucket == 8 else "test")


def _comparable_amounts(a: dict, b: dict) -> tuple[float, float] | None:
    if a.get("currency") == b.get("currency") and a.get("amount") and b.get("amount"):
        return float(a["amount"]), float(b["amount"])
    if a.get("amount_usd") and b.get("amount_usd"):
        return float(a["amount_usd"]), float(b["amount_usd"])
    return None


def case_slice(candidates: list[dict], target_id: str | None) -> str:
    target = next((t for t in candidates if t["transaction_id"] == target_id), None)
    if target is None:
        return "nil"
    for other in candidates:
        if other is target:
            continue
        same_type_no_merchant = (other.get("transaction_type") == target.get("transaction_type")
                                 and not other.get("merchant_name") and not target.get("merchant_name"))
        same_merchant = bool(other.get("merchant_name") and target.get("merchant_name")
                             and fold(other["merchant_name"]) == fold(target["merchant_name"]))
        pair = _comparable_amounts(target, other)
        close_amount = pair is not None and pair[0] > 0 and abs(pair[0] - pair[1]) <= HARD_AMOUNT_PCT * pair[0]
        if same_type_no_merchant or same_merchant or close_amount:
            return "hard"
    return "easy"
