"""Serving contract consumed by the agent (pipeline spec §5.3–5.4): lowercase column names, in order."""
CONTRACT: dict[str, list[str]] = {
    "dim_customer": ["customer_id", "country", "city", "state", "segment", "detected_accent", "customer_status",
                     "registration_date", "accepts_marketing", "last_updated"],
    "dim_product": ["product_id", "customer_id", "product_type", "product_last4", "currency", "current_balance",
                    "credit_limit", "interest_rate", "opening_date", "expiration_date", "product_status",
                    "has_linked_app", "days_past_due", "last_transaction_date", "last_updated"],
    "fct_transaction": ["transaction_id", "transaction_ts", "process_date", "product_id", "customer_id",
                        "transaction_type", "transaction_category", "amount", "currency", "amount_usd", "channel",
                        "merchant_name", "merchant_category", "transaction_country", "transaction_city",
                        "transaction_status", "response_code", "decline_reason_key", "is_fraud", "fraud_score"],
    "fct_complaint": ["complaint_id", "creation_ts", "process_date", "customer_id", "case_type", "category",
                      "subcategory", "reception_channel", "affected_product_id", "claimed_amount", "currency",
                      "priority", "status", "sla_breached", "resolution_days", "resolution_satisfaction",
                      "is_repeat_complainer", "first_response_ts", "resolution_ts", "closing_ts"],
    "seed_decline_reason": ["response_code", "reason_key", "customer_text_es", "customer_text_pt", "next_step"],
}
