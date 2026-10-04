"""Customer-scoped read tools. Every tool takes a verified SessionContext; none accepts a customer_id argument."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from bankagent.context import SCOPE_READ, SessionContext
from bankagent.data.serving import ServingData
from bankagent.ids import new_id

ACCOUNT_FIELDS = ("product_id", "product_type", "product_last4", "currency", "current_balance", "credit_limit",
                  "product_status", "days_past_due", "last_transaction_date")
TXN_FIELDS = ("transaction_id", "transaction_ts", "process_date", "product_id", "customer_id", "transaction_type",
              "amount", "currency", "amount_usd", "channel", "merchant_name", "transaction_city",
              "transaction_country", "transaction_status", "response_code", "decline_reason_key", "is_fraud",
              "fraud_score")
COMPLAINT_FIELDS = ("complaint_id", "creation_ts", "case_type", "category", "subcategory", "status", "priority",
                    "claimed_amount", "currency")


class NotFound(Exception):
    """Same response whether the record is missing or belongs to someone else."""

    def __init__(self):
        super().__init__("not_found")


class NotDeclined(Exception):
    pass


@dataclass(frozen=True)
class ToolResult:
    source: str
    data: Any
    as_of: str
    receipt_id: str = field(default_factory=lambda: new_id("RCP"))

    def receipt(self) -> dict:
        return {"receipt_id": self.receipt_id, "source": self.source, "as_of": self.as_of, "data": self.data}


def _pick(row: dict, fields) -> dict:
    return {k: row.get(k) for k in fields}


class ReadTools:
    def __init__(self, serving: ServingData):
        self.serving = serving

    def get_accounts(self, ctx: SessionContext, run_id: str, as_of: date) -> ToolResult:
        ctx.require(SCOPE_READ)
        rows = self.serving.query(run_id, "dim_product", "customer_id = ?", [ctx.customer_id], "product_id")
        return ToolResult("dim_product", [_pick(r, ACCOUNT_FIELDS) for r in rows], as_of.isoformat())

    def list_transactions(self, ctx: SessionContext, run_id: str, as_of: date, window_days: int = 60) -> ToolResult:
        ctx.require(SCOPE_READ)
        rows = self.serving.query(run_id, "fct_transaction", "customer_id = ? and process_date between ? and ?",
                                  [ctx.customer_id, as_of - timedelta(days=window_days), as_of], "transaction_ts desc")
        return ToolResult("fct_transaction", [_pick(r, TXN_FIELDS) for r in rows], as_of.isoformat())

    def get_transaction(self, ctx: SessionContext, run_id: str, as_of: date, transaction_id: str) -> ToolResult:
        ctx.require(SCOPE_READ)
        rows = self.serving.query(run_id, "fct_transaction", "customer_id = ? and transaction_id = ?",
                                  [ctx.customer_id, transaction_id])
        if not rows:
            raise NotFound()
        return ToolResult("fct_transaction", _pick(rows[0], TXN_FIELDS), as_of.isoformat())

    def explain_decline(self, ctx: SessionContext, run_id: str, as_of: date, transaction_id: str) -> ToolResult:
        txn = self.get_transaction(ctx, run_id, as_of, transaction_id).data
        if txn["transaction_status"] != "Declined":
            raise NotDeclined(txn["transaction_status"])
        seed = self.serving.query(run_id, "seed_decline_reason", "response_code = ?", [txn["response_code"]])
        reason = seed[0] if seed else {"reason_key": "unknown", "customer_text_es": None, "customer_text_pt": None,
                                       "next_step": "contact_bank"}
        return ToolResult("seed_decline_reason", {"transaction": txn, "reason_key": reason["reason_key"],
                                                  "customer_text_es": reason["customer_text_es"],
                                                  "customer_text_pt": reason["customer_text_pt"],
                                                  "next_step": reason["next_step"]}, as_of.isoformat())

    def list_complaints(self, ctx: SessionContext, run_id: str, as_of: date) -> ToolResult:
        ctx.require(SCOPE_READ)
        rows = self.serving.query(run_id, "fct_complaint", "customer_id = ?", [ctx.customer_id], "creation_ts desc")
        return ToolResult("fct_complaint", [_pick(r, COMPLAINT_FIELDS) for r in rows], as_of.isoformat())
