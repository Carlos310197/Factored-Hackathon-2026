"""The four resolution systems compared in the evaluation (resolver spec §6.1) and the per-case outcome (§6.2).
B0 heuristic filter · B1 ranker alone · B2 Jev alone (understand.v1) · P Jev + ranker scores (understand.v2)."""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bankagent.decisions.understand import SPECIAL_TARGETS, matches_mentions

if TYPE_CHECKING:
    from bankagent.resolver.model import Scores

OUTCOMES = ("act_correct", "act_wrong", "ask_hit", "ask_miss", "ask_nil", "nil_correct", "nil_wrong")
FILTER_KEYS = ("merchant", "amount", "date_from", "date_to")


@dataclass(frozen=True)
class Decision:
    action: str  # "act" | "ask" | "nil"
    pick: str | None = None
    options: tuple[str, ...] = ()


def outcome(target_id: str | None, d: Decision) -> str:
    if d.action == "act":
        return "act_correct" if d.pick == target_id else "act_wrong"
    if d.action == "nil":
        return "nil_correct" if target_id is None else "nil_wrong"
    if target_id is None:
        return "ask_nil"
    return "ask_hit" if target_id in d.options else "ask_miss"


def b0(candidates: list[dict], mentions: dict | None) -> Decision:
    """Act only when mentions are present and exactly one candidate passes the heuristic filter."""
    m = mentions or {}
    present = any(m.get(k) not in (None, "") for k in FILTER_KEYS)
    passing = [t for t in candidates if matches_mentions(t, m)] if present else []
    if present and len(passing) == 1:
        return Decision("act", passing[0]["transaction_id"])
    return Decision("ask", options=tuple(t["transaction_id"] for t in (passing or candidates)[:3]))


def b1(scores: "Scores", tau: float, phi: float) -> Decision:
    if not scores.ranked or scores.best_raw_fit < phi:
        return Decision("nil")
    top = scores.ranked[0]
    if scores.probs[top] >= tau:
        return Decision("act", top)
    return Decision("ask", options=tuple(scores.ranked[:3]))


def jev_decision(answer: dict | None, t: float, m: float) -> Decision:
    """answer: {"label", "probs"} with aliases already mapped to transaction ids; None when Jev failed (the agent
    clarifies, so this counts as an ask with no options)."""
    if answer is None:
        return Decision("ask")
    probs = answer["probs"]
    ordered = sorted(probs, key=lambda k: -probs[k])
    label = answer["label"]
    p = probs.get(label, 0.0)
    runner = max((probs[k] for k in ordered if k != label), default=0.0)
    confident = p >= t and p - runner >= m
    if label == "not_in_list" and confident:
        return Decision("nil")
    if label not in SPECIAL_TARGETS and confident:
        return Decision("act", label)
    return Decision("ask", options=tuple(k for k in ordered if k not in SPECIAL_TARGETS)[:3])
