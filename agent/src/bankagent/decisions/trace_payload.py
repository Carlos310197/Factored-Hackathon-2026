from bankagent.decisions.thresholds import Thresholds


def thresholds_map(t: Thresholds) -> dict[str, float]:
    out = {"intent": t.intent_min_p, "intent.margin": t.intent_min_margin, "target_transaction": t.target_min_p,
           "target_transaction.margin": t.target_min_margin, "confirmation": t.confirmation_confirm,
           "injection_attempt": t.injection_attempt}
    out.update(t.handoff_noul)
    out.update(t.offer_human_noul)
    return {k: float(v) for k, v in out.items()}


def _date(txn: dict) -> str:
    return str(txn.get("process_date") or txn.get("transaction_ts") or "")[:10]


def alias_view(aliases: dict[str, str], candidates: list[dict]) -> dict[str, dict]:
    by_id = {c["transaction_id"]: c for c in candidates}
    return {alias: {"transaction_id": tid, "merchant": by_id[tid].get("merchant_name"),
                    "amount": by_id[tid].get("amount"), "currency": by_id[tid].get("currency"),
                    "date": _date(by_id[tid])}
            for alias, tid in aliases.items() if tid in by_id}


def confirmation_payload(txn: dict, reason: str | None) -> dict:
    """Built from the same txn + reason that file_dispute files, so the card can never differ."""
    return {"merchant": txn.get("merchant_name") or "", "date": _date(txn), "amount": txn.get("amount"),
            "currency": txn.get("currency"), "reason_code": reason}
