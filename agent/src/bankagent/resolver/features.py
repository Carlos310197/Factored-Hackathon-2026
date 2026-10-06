"""Transaction-resolver features. One row per candidate, built from extract's structured
mentions. The same function serves training and the live agent, so features cannot drift between them.
Evidence features are 0 when the customer did not mention the field; the *_mentioned indicators let the model
tell 'not mentioned' apart from 'perfect match' when it scores absolute fit (best_raw_fit)."""
import math
import unicodedata
from datetime import date

import numpy as np
from rapidfuzz import fuzz

FEATURES = ("merchant_mentioned", "merchant_sim", "merchant_missing_on_cand", "amount_mentioned", "amount_log_err",
            "amount_rank", "date_mentioned", "days_outside", "type_match", "channel_match", "city_match",
            "recency_pct", "is_purchase")
TYPE_HINTS = {"purchase": "Purchase", "withdrawal": "Withdrawal", "transfer": "Transfer", "payment": "Payment",
              "deposit": "Deposit"}
CHANNEL_HINTS = {"atm": "ATM", "pos": "POS", "app": "App", "web": "Web", "branch": "Branch"}
MAX_LOG_ERR = 3.0
CITY_MATCH_RATIO = 85


def fold(s: str) -> str:
    """Lowercase, strip accents and collapse whitespace: 'Tienda Don José' -> 'tienda don jose'."""
    s = unicodedata.normalize("NFKD", s)
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).lower().split())


def _date(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def _amount(m: dict) -> float | None:
    a = m.get("amount")
    return float(a) if isinstance(a, (int, float)) and not isinstance(a, bool) and a > 0 else None


def mentions_present(m: dict | None) -> bool:
    m = m or {}
    return any(m.get(k) not in (None, "") for k in ("merchant", "amount", "date_from", "date_to", "type_hint",
                                                    "channel_hint", "city"))


def _log_err(amount: float, t: dict) -> float:
    vals = [float(v) for v in (t.get("amount"), t.get("amount_usd")) if isinstance(v, (int, float)) and v > 0]
    if not vals:
        return MAX_LOG_ERR
    return min(MAX_LOG_ERR, min(abs(math.log(amount / v)) for v in vals))


def _signed(hint, value, table: dict) -> float:
    key = str(hint).strip().lower() if hint else ""
    if key not in table:
        return 0.0
    return 1.0 if table[key] == value else -1.0


def case_features(mentions: dict | None, candidates: list[dict]) -> np.ndarray:
    """candidates arrive newest first (ReadTools.list_transactions order). Returns shape (n, len(FEATURES))."""
    m, n = mentions or {}, len(candidates)
    x = np.zeros((n, len(FEATURES)))
    if n == 0:
        return x
    col = {f: i for i, f in enumerate(FEATURES)}
    merchant = fold(m["merchant"]) if isinstance(m.get("merchant"), str) and m["merchant"].strip() else None
    amount = _amount(m)
    d_from, d_to = _date(m.get("date_from")), _date(m.get("date_to"))
    if d_from and d_to and d_from > d_to:  # a reversed range from extract means the same range
        d_from, d_to = d_to, d_from
    city = fold(m["city"]) if isinstance(m.get("city"), str) and m["city"].strip() else None
    errs = [_log_err(amount, t) for t in candidates] if amount else None
    for i, t in enumerate(candidates):
        row = x[i]
        name = t.get("merchant_name")
        if merchant:
            row[col["merchant_mentioned"]] = 1.0
            if name:
                row[col["merchant_sim"]] = fuzz.token_set_ratio(merchant, fold(name)) / 100.0
            else:
                row[col["merchant_missing_on_cand"]] = 1.0
        if amount:
            row[col["amount_mentioned"]] = 1.0
            row[col["amount_log_err"]] = errs[i]
            row[col["amount_rank"]] = sum(1 for e in errs if e < errs[i]) / n
        if d_from or d_to:
            row[col["date_mentioned"]] = 1.0
            d = _date(t.get("process_date"))
            days = 0
            if d and d_from and d < d_from:
                days = (d_from - d).days
            elif d and d_to and d > d_to:
                days = (d - d_to).days
            row[col["days_outside"]] = math.log1p(days)
        row[col["type_match"]] = _signed(m.get("type_hint"), t.get("transaction_type"), TYPE_HINTS)
        row[col["channel_match"]] = _signed(m.get("channel_hint"), t.get("channel"), CHANNEL_HINTS)
        if city and t.get("transaction_city"):
            row[col["city_match"]] = 1.0 if fuzz.ratio(city, fold(t["transaction_city"])) >= CITY_MATCH_RATIO else -1.0
        row[col["recency_pct"]] = i / n
        row[col["is_purchase"]] = 1.0 if t.get("transaction_type") == "Purchase" else 0.0
    return x
