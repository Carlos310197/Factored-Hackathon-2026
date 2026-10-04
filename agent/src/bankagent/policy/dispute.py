"""Team-authored, labeled synthetic dispute policy (spec §5). Pure code: no model can override it."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml

DEFAULT_PATH = Path(__file__).with_name("dispute_policy.yaml")
REDIRECT_BY_STATUS = {"Declined": "explain_decline", "Pending": "wait_pending", "Reversed": "already_reversed"}


@dataclass(frozen=True)
class Rule:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class PolicyResult:
    outcome: Literal["automated", "human_review", "not_disputable"]
    rules: tuple[Rule, ...]
    redirect: str | None
    version: str

    def triggers(self) -> list[str]:
        rule = next((r for r in self.rules if r.name == "automated_eligible"), None)
        return [t for t in rule.detail.split(",") if t] if rule else []


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _truthy(v) -> bool:
    return v is True or str(v).lower() == "true"


def _usd(txn: dict) -> float | None:
    if txn.get("amount_usd") is not None:
        return float(txn["amount_usd"])
    if txn.get("currency") == "USD" and txn.get("amount") is not None:
        return float(txn["amount"])
    return None


class DisputePolicy:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.version = cfg["version"]

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "DisputePolicy":
        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def _stop(self, rules: list[Rule], redirect: str) -> PolicyResult:
        return PolicyResult("not_disputable", tuple(rules), redirect, self.version)

    def evaluate(self, txn: dict, reason: str, as_of: date, already_disputed: bool,
                 escalation: bool = False) -> PolicyResult:
        c = self.cfg
        if reason not in c["reasons"]:
            raise ValueError(f"unknown dispute reason: {reason}")
        rules: list[Rule] = []
        status = txn["transaction_status"]
        rules.append(Rule("status_disputable", status in c["disputable_status"], status))
        if status not in c["disputable_status"]:
            return self._stop(rules, REDIRECT_BY_STATUS.get(status, "not_disputable"))
        ttype = txn["transaction_type"]
        rules.append(Rule("type_disputable", ttype in c["disputable_types"], ttype))
        if ttype not in c["disputable_types"]:
            return self._stop(rules, "not_disputable_type")
        age = (as_of - _as_date(txn["process_date"])).days
        in_window = 0 <= age <= c["window_days"]
        rules.append(Rule("within_window", in_window, f"{age} days"))
        if not in_window:
            return self._stop(rules, "out_of_window")
        rules.append(Rule("not_already_disputed", not already_disputed))
        if already_disputed:
            return self._stop(rules, "already_disputed")
        triggers = []
        if reason in c["human_review_reasons"]:
            triggers.append("unauthorized_reason")
        if _truthy(txn.get("is_fraud")):
            triggers.append("fraud_flag")
        if float(txn.get("fraud_score") or 0) > c["fraud_score_human_review_above"]:
            triggers.append("fraud_score_high")
        usd = _usd(txn)
        if usd is None:
            triggers.append("amount_unknown")
        elif usd > c["automated_max_amount_usd"]:
            triggers.append("amount_over_limit")
        if escalation:
            triggers.append("escalation_signal")
        rules.append(Rule("automated_eligible", not triggers, ",".join(triggers)))
        return PolicyResult("human_review" if triggers else "automated", tuple(rules), None, self.version)
