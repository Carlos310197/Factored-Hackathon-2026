"""SYNTHETIC transactions for resolver tests: labeled test data, NOT organizer records."""


def txn(i: int, day: str = "2026-06-10", merchant: str | None = "Tienda Don José", amount: float = 343.03,
        ttype: str = "Purchase", channel: str = "POS", city: str = "Guadalajara", currency: str = "USD",
        amount_usd: float | None = None) -> dict:
    return {"transaction_id": f"TRX-R{i:019d}", "transaction_ts": f"{day}T12:00:00", "process_date": day,
            "product_id": "PRD-SYNTH0000001", "customer_id": "CLI-SYNTH0000001", "transaction_type": ttype,
            "amount": amount, "currency": currency,
            "amount_usd": amount_usd if amount_usd is not None else (amount if currency == "USD" else None),
            "channel": channel, "merchant_name": merchant, "transaction_city": city, "transaction_country": "México",
            "transaction_status": "Approved", "response_code": "00", "decline_reason_key": None, "is_fraud": False,
            "fraud_score": 10.0}


def mentions(**kw) -> dict:
    base = {"merchant": None, "amount": None, "currency": None, "date_from": None, "date_to": None,
            "type_hint": None, "channel_hint": None, "city": None}
    return base | kw


def write_logreg_artifact(path, temperature: float = 1.0, selfcheck: bool = True) -> None:
    """Hand-set logistic-regression artifact. Labeled test artifact."""
    import json

    import numpy as np

    from bankagent.resolver.features import FEATURES

    w = {"merchant_sim": 4.0, "merchant_missing_on_cand": -1.0, "amount_log_err": -3.0, "amount_rank": -1.0,
         "days_outside": -2.0, "type_match": 1.0, "channel_match": 0.5, "city_match": 0.5}
    spec = {"version": "resolver.test", "kind": "logreg", "features": list(FEATURES), "mean": [0.0] * len(FEATURES),
            "scale": [1.0] * len(FEATURES), "coef": [w.get(f, 0.0) for f in FEATURES], "intercept": -1.0,
            "temperature": temperature, "metadata": {"family": "logreg", "label": "hand-set test artifact"}}
    if selfcheck:
        X = np.eye(len(FEATURES))
        spec["selfcheck"] = {"X": X.tolist(), "logits": (X @ np.array(spec["coef"]) - 1.0).tolist()}
    path.mkdir(parents=True, exist_ok=True)
    (path / "model.json").write_text(json.dumps(spec))
