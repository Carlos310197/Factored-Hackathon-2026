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
