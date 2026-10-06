"""Every write is read back; an unknown write outcome is resolved by reading, never by blind retry."""
import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime, timezone

from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError

from bankagent.context import SCOPE_DISPUTE, SessionContext
from bankagent.ids import new_id
from bankagent.policy.dispute import DisputePolicy, PolicyResult
from bankagent.store.repos import AlreadyExists, Store
from bankagent.tools.read import NotFound, ToolResult

UNKNOWN_OUTCOME = (ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError)
VERIFIED_FIELDS = ("dispute_id", "transaction_id", "customer_id", "reason", "amount", "currency", "route", "status",
                   "policy_version")


class AlreadyDisputed(Exception):
    def __init__(self, existing: dict):
        super().__init__(existing.get("dispute_id", "unknown"))
        self.existing = existing


class PolicyRejected(Exception):
    def __init__(self, result: PolicyResult):
        super().__init__(result.redirect)
        self.result = result


class WriteFailed(Exception):
    pass


class HandoffFailed(Exception):
    pass


def record_hash(record: dict) -> str:
    subset = {k: record.get(k) for k in VERIFIED_FIELDS}
    return hashlib.sha256(json.dumps(subset, sort_keys=True, default=str).encode()).hexdigest()


class WriteTools:
    def __init__(self, store: Store, policy: DisputePolicy, now=lambda: datetime.now(timezone.utc)):
        self.store, self.policy, self.now = store, policy, now

    def create_dispute(self, ctx: SessionContext, txn: dict, reason: str, statement: dict, as_of: date,
                       escalation: bool, session_id: str, turn_id: str, language: str) -> ToolResult:
        ctx.require(SCOPE_DISPUTE)
        if txn.get("customer_id") != ctx.customer_id:
            raise NotFound()
        existing = self.store.disputes.get(txn["transaction_id"])
        if existing:
            raise AlreadyDisputed(existing)
        result = self.policy.evaluate(txn, reason, as_of, already_disputed=False, escalation=escalation)
        if result.outcome == "not_disputable":
            raise PolicyRejected(result)
        human = result.outcome == "human_review"
        item = {"dispute_id": new_id("DSP"), "transaction_id": txn["transaction_id"], "customer_id": ctx.customer_id,
                "product_id": txn.get("product_id"), "reason": reason, "amount": txn["amount"],
                "currency": txn["currency"], "amount_usd": txn.get("amount_usd"), "customer_statement": statement,
                "route": "human_review" if human else "automated", "status": "pending_review" if human else "submitted",
                "policy_version": result.version, "session_id": session_id, "turn_id": turn_id, "language": language,
                "created_at": self.now().isoformat()}
        self._put_with_read_back(item)
        data = {k: item[k] for k in VERIFIED_FIELDS} | {"created_at": item["created_at"],
                                                        "policy_rules": [asdict(r) for r in result.rules]}
        return ToolResult("disputes", data, as_of.isoformat())

    def _put_with_read_back(self, item: dict) -> None:
        for _ in range(2):
            try:
                self.store.disputes.put_new(item)
                return
            except AlreadyExists:
                found = self.store.disputes.get(item["transaction_id"])
                if found and found.get("dispute_id") == item["dispute_id"]:
                    return
                raise AlreadyDisputed(found or {})
            except UNKNOWN_OUTCOME:
                found = self.store.disputes.get(item["transaction_id"])
                if found and found.get("dispute_id") == item["dispute_id"]:
                    return
                if found:
                    raise AlreadyDisputed(found)
        raise WriteFailed(item["transaction_id"])

    def verify_dispute(self, ctx: SessionContext, expected: dict, as_of: date) -> ToolResult:
        record = self.store.disputes.get(expected["transaction_id"])
        if record is None or record.get("customer_id") != ctx.customer_id:
            data = {"verified": False, "mismatches": ["missing"], "dispute_id": expected.get("dispute_id"),
                    "status": None, "created_at": None, "record_hash": None}
        else:
            mismatches = [f for f in VERIFIED_FIELDS if record.get(f) != expected.get(f)]
            data = {"verified": not mismatches, "mismatches": mismatches, "dispute_id": record["dispute_id"],
                    "status": record["status"], "created_at": record["created_at"], "record_hash": record_hash(record)}
        return ToolResult("disputes.verify", data, as_of.isoformat())

    def list_disputes(self, ctx: SessionContext, as_of: date) -> ToolResult:
        rows = self.store.disputes.list_for_customer(ctx.customer_id)
        data = [{k: r.get(k) for k in ("dispute_id", "transaction_id", "status", "route", "reason", "created_at")}
                for r in rows]
        return ToolResult("disputes", data, as_of.isoformat())

    def create_handoff(self, ctx: SessionContext, packet: dict, as_of: str) -> ToolResult:
        if packet.get("customer_id") != ctx.customer_id:
            raise HandoffFailed("packet customer mismatch")
        try:
            self.store.handoffs.put(packet)
        except UNKNOWN_OUTCOME:
            pass  # resolved by the read-back below
        except Exception as e:
            raise HandoffFailed(str(e)) from e
        found = self.store.handoffs.get(packet["handoff_id"])
        if not found:
            raise HandoffFailed(packet["handoff_id"])
        return ToolResult("handoffs", {"handoff_id": found["handoff_id"], "priority": found["priority"],
                                       "status": found["status"]}, as_of)
