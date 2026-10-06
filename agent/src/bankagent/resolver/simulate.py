"""Simulated training cases: a real history, a target transaction, and the structured mentions a
customer (plus extract) might produce for it. No text and no LLM. Deterministic for a given seed."""
import hashlib
import math
import random
from datetime import date, timedelta
from pathlib import Path

import yaml

from bankagent.resolver.features import CHANNEL_HINTS, TYPE_HINTS, fold
from bankagent.resolver.histories import History
from bankagent.resolver.splits import case_slice

DEFAULT_CONFIG = Path(__file__).with_name("simulate.yaml")
DISTRIBUTIONS = ("merchant", "amount", "date")
MENTION_KEYS = ("merchant", "amount", "currency", "date_from", "date_to", "type_hint", "channel_hint", "city")
OTHER_CITIES = ("Lima", "Quito", "Santiago", "Rosario", "Cali")


def load_sim_config(path: Path = DEFAULT_CONFIG) -> dict:
    raw = Path(path).read_bytes()
    cfg = yaml.safe_load(raw)
    for name in DISTRIBUTIONS:
        if not math.isclose(sum(cfg[name].values()), 1.0, abs_tol=1e-9):
            raise ValueError(f"simulate config: {name} rates must sum to 1")
    cfg["sha256"] = hashlib.sha256(raw).hexdigest()
    return cfg


def _pick(rng: random.Random, dist: dict) -> str:
    r, acc = rng.random(), 0.0
    for k, p in dist.items():
        acc += p
        if r < acc:
            return k
    return list(dist)[-1]


def round_significant(a: float) -> float:
    """Two significant figures: 343.03 -> 340, 1372120 -> 1400000, 15.99 -> 16."""
    q = 10 ** (math.floor(math.log10(a)) - 1)
    return float(round(a / q) * q)


def relative_ranges(anchor: date) -> dict[str, tuple[date, date]]:
    """The phrases customers use, tightest first, as date ranges relative to the anchor."""
    monday = anchor - timedelta(days=anchor.weekday())
    first = anchor.replace(day=1)
    prev_first = (first - timedelta(days=1)).replace(day=1)
    return {"this week": (monday, anchor), "last week": (monday - timedelta(days=7), monday - timedelta(days=1)),
            "this month": (first, anchor), "last month": (prev_first, first - timedelta(days=1))}


def relative_range(d: date, anchor: date) -> tuple[str, date, date] | None:
    """The tightest relative range containing d, with its label."""
    for label, (lo, hi) in relative_ranges(anchor).items():
        if lo <= d <= hi:
            return label, lo, hi
    return None


def _typo(rng: random.Random, name: str) -> str:
    folded = fold(name)
    if folded != name.lower():
        return folded
    i = rng.randrange(1, max(2, len(name) - 1))
    return name[:i] + name[i + 1:]


def _hint(rng: random.Random, cfg: dict, key: str, true_value: str | None, choices: list[str]) -> tuple[str | None, str]:
    if true_value is None:
        return None, "n/a"
    if rng.random() >= cfg["hints"][key]:
        return None, "absent"
    if rng.random() < cfg["hint_wrong"]:
        return rng.choice([c for c in choices if c != true_value]), "wrong"
    return true_value, "present"


def describe(rng: random.Random, cfg: dict, t: dict, anchor: date, others: list[dict]) -> tuple[dict, dict]:
    """Mentions and the style that produced them for target t."""
    m = {k: None for k in MENTION_KEYS}
    style: dict = {"no_detail": False, "extract_error": False}
    if rng.random() < cfg["no_detail"]:
        style["no_detail"] = True
        return m, style
    if t.get("merchant_name"):
        style["merchant"] = _pick(rng, cfg["merchant"])
        m["merchant"] = {"exact": t["merchant_name"], "noisy": _typo(rng, t["merchant_name"]), "absent": None}[style["merchant"]]
    else:
        style["merchant"] = "n/a"
    a = float(t["amount"])
    s = _pick(rng, cfg["amount"])
    if s == "usd" and not (t.get("currency") != "USD" and t.get("amount_usd")):
        s = "exact"
    style["amount"] = s
    if s != "absent":
        m["amount"] = {"exact": a, "rounded": round_significant(a),
                       "approx": round(a * rng.uniform(1 - cfg["amount_approx_pct"], 1 + cfg["amount_approx_pct"]), 2),
                       "usd": float(t.get("amount_usd") or a)}[s]
        if rng.random() < cfg["currency_mentioned"]:
            m["currency"] = "USD" if s == "usd" else t.get("currency")
    d = date.fromisoformat(str(t["process_date"])[:10])
    s = _pick(rng, cfg["date"])
    if s == "relative":
        rr = relative_range(d, anchor)
        if rr is None:
            s = "absent"
        else:
            style["date_label"] = rr[0]
            m["date_from"], m["date_to"] = rr[1].isoformat(), rr[2].isoformat()
    if s == "exact":
        m["date_from"] = m["date_to"] = d.isoformat()
    elif s == "off_by_one":
        off = (d + timedelta(days=rng.choice((-1, 1)))).isoformat()
        m["date_from"] = m["date_to"] = off
    style["date"] = s
    inv_type = {v: k for k, v in TYPE_HINTS.items()}
    inv_channel = {v: k for k, v in CHANNEL_HINTS.items()}
    m["type_hint"], style["type_hint"] = _hint(rng, cfg, "type_hint", inv_type.get(t.get("transaction_type")),
                                               list(TYPE_HINTS))
    m["channel_hint"], style["channel_hint"] = _hint(rng, cfg, "channel_hint", inv_channel.get(t.get("channel")),
                                                     list(CHANNEL_HINTS))
    m["city"], style["city"] = _hint(rng, cfg, "city", t.get("transaction_city"),
                                     [c for c in OTHER_CITIES] + [t.get("transaction_city") or ""])
    if others and rng.random() < cfg["extract_error"]:
        fields = [f for f in ("merchant", "amount", "date") if m.get(f if f != "date" else "date_from") is not None]
        if fields:
            o, f = rng.choice(others), rng.choice(fields)
            if f == "merchant" and o.get("merchant_name"):
                m["merchant"] = o["merchant_name"]
            elif f == "amount":
                m["amount"] = float(o["amount"])
            elif f == "date":
                m["date_from"] = m["date_to"] = str(o["process_date"])[:10]
            style["extract_error"] = True
    return m, style


def simulate(histories: list[History], cfg: dict, seed: int) -> list[dict]:
    """One case per history. Cases with no candidates left are skipped."""
    rng = random.Random(seed)
    cases = []
    for k, h in enumerate(histories):
        cands = h.candidates
        slices = {t["transaction_id"]: case_slice(cands, t["transaction_id"]) for t in cands}
        hard = [t for t in cands if slices[t["transaction_id"]] == "hard"]
        easy = [t for t in cands if slices[t["transaction_id"]] == "easy"]
        want_hard = rng.random() < cfg["hard_share"]
        target = rng.choice(hard if (want_hard and hard) or not easy else easy)
        others = [t for t in cands if t is not target]
        mentions, style = describe(rng, cfg, target, date.fromisoformat(h.anchor), others)
        nil = rng.random() < cfg["not_in_list"]
        shown = others if nil else cands
        if not shown:
            continue
        style["nil"] = nil
        cases.append({"case_id": f"{h.split}-{seed}-{k:06d}", "split": h.split, "anchor": h.anchor,
                      "slice": "nil" if nil else slices[target["transaction_id"]],
                      "target_id": None if nil else target["transaction_id"], "target": target,
                      "candidates": shown, "mentions": mentions, "style": style})
    return cases
