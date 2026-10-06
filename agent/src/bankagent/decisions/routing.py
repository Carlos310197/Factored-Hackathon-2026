from dataclasses import dataclass, field

from bankagent.decisions.jev import ChoiceAnswer
from bankagent.decisions.thresholds import Thresholds
from bankagent.decisions.understand import SPECIAL_TARGETS, Understanding


@dataclass
class Counters:
    clarify: int = 0
    confirm_asks: int = 0
    injections: int = 0
    jev_failures: int = 0


@dataclass
class Route:
    next: str
    goal: dict = field(default_factory=dict)
    counters: Counters = field(default_factory=Counters)
    reasons: tuple[str, ...] = ()
    intent: str | None = None
    target_txn_id: str | None = None
    dispute_reason: str | None = None
    escalated: bool = False
    offer_human: bool = False


def _confident(answer: ChoiceAnswer, min_p: float, min_margin: float) -> bool:
    return answer.p >= min_p and answer.margin >= min_margin


def _extract_target(
    target: ChoiceAnswer,
    aliases: dict[str, str],
    th: Thresholds,
) -> str | None:
    if not _confident(target, th.target_min_p, th.target_min_margin):
        return None
    
    label = target.label
    if label in SPECIAL_TARGETS:
        return None
    
    return aliases.get(label)


def decide(
    u: Understanding | None,
    th: Thresholds,
    awaiting: str,
    counters: Counters,
    pending: dict,
) -> Route:
    if u is None:
        new_counters = Counters(
            clarify=counters.clarify,
            confirm_asks=counters.confirm_asks,
            injections=counters.injections,
            jev_failures=counters.jev_failures + 1,
        )
        
        if new_counters.jev_failures >= th.max_jev_failures:
            return Route(
                next="handoff",
                goal={"kind": "handoff_notice"},
                counters=new_counters,
                reasons=("jev_unavailable",),
            )
        
        if awaiting == "confirmation":
            new_counters = Counters(
                clarify=new_counters.clarify,
                confirm_asks=new_counters.confirm_asks + 1,
                injections=new_counters.injections,
                jev_failures=new_counters.jev_failures,
            )
            return Route(
                next="confirm",
                goal={"kind": "ask_confirmation"},
                counters=new_counters,
            )
        
        return Route(
            next="clarify",
            goal={"kind": "ask_clarification", "topic": "repeat"},
            counters=new_counters,
        )
    
    new_counters = Counters(
        clarify=counters.clarify,
        confirm_asks=counters.confirm_asks,
        injections=counters.injections,
        jev_failures=0,
    )
    
    offer_human = u.nouls.get("distress", 0) >= th.offer_human_noul.get("distress", 0.60)
    
    for noul in ["reports_unauthorized_use", "legal_or_regulator_threat", "asks_for_human"]:
        threshold = th.handoff_noul.get(noul, 0.50)
        if u.nouls.get(noul, 0) >= threshold:
            if u.intent.label == "dispute_charge":
                target = _extract_target(u.target, u.aliases, th)
                if target:
                    reason = u.reason.label if u.reason.label != "unclear" else (
                        "unauthorized" if noul == "reports_unauthorized_use" else None
                    )
                    if reason:
                        return Route(
                            next="resolve_transaction",
                            goal={},
                            counters=new_counters,
                            reasons=(noul,),
                            intent=u.intent.label,
                            target_txn_id=target,
                            dispute_reason=reason,
                            escalated=True,
                            offer_human=offer_human,
                        )
            
            return Route(
                next="handoff",
                goal={"kind": "handoff_notice"},
                counters=new_counters,
                reasons=(noul,),
                intent=u.intent.label,
                offer_human=offer_human,
            )
    
    if u.nouls.get("injection_attempt", 0) >= th.injection_attempt:
        new_counters = Counters(
            clarify=new_counters.clarify,
            confirm_asks=new_counters.confirm_asks,
            injections=new_counters.injections + 1,
            jev_failures=new_counters.jev_failures,
        )
        
        if new_counters.injections >= th.max_injections:
            return Route(
                next="handoff",
                goal={"kind": "handoff_notice"},
                counters=new_counters,
                reasons=("injection_repeated",),
                offer_human=offer_human,
            )
        
        return Route(
            next="reply",
            goal={"kind": "refuse_injection"},
            counters=new_counters,
            reasons=("injection_attempt",),
            offer_human=offer_human,
        )
    
    if awaiting == "confirmation":
        if u.confirmation is None:
            new_counters = Counters(
                clarify=new_counters.clarify,
                confirm_asks=new_counters.confirm_asks + 1,
                injections=new_counters.injections,
                jev_failures=new_counters.jev_failures,
            )
            
            if new_counters.confirm_asks > th.max_confirmation_asks:
                return Route(
                    next="handoff",
                    goal={"kind": "handoff_notice"},
                    counters=new_counters,
                    reasons=("confirmation_unclear",),
                    offer_human=offer_human,
                )
            
            return Route(
                next="confirm",
                goal={"kind": "ask_confirmation"},
                counters=new_counters,
                offer_human=offer_human,
            )
        
        conf_label = u.confirmation.label
        conf_p = u.confirmation.p
        
        if conf_label == "confirm" and conf_p >= th.confirmation_confirm:
            return Route(
                next="file_dispute",
                goal={},
                counters=new_counters,
                offer_human=offer_human,
            )
        
        if conf_label == "reject":
            return Route(
                next="reply",
                goal={"kind": "dispute_cancelled"},
                counters=new_counters,
                offer_human=offer_human,
            )
        
        if conf_label == "modify":
            return Route(
                next="clarify",
                goal={"kind": "ask_clarification", "topic": "dispute_change"},
                counters=new_counters,
                offer_human=offer_human,
            )
        
        new_counters = Counters(
            clarify=new_counters.clarify,
            confirm_asks=new_counters.confirm_asks + 1,
            injections=new_counters.injections,
            jev_failures=new_counters.jev_failures,
        )
        
        if new_counters.confirm_asks > th.max_confirmation_asks:
            return Route(
                next="handoff",
                goal={"kind": "handoff_notice"},
                counters=new_counters,
                reasons=("confirmation_unclear",),
                offer_human=offer_human,
            )
        
        return Route(
            next="confirm",
            goal={"kind": "ask_confirmation"},
            counters=new_counters,
            offer_human=offer_human,
        )
    
    intent = u.intent.label if _confident(u.intent, th.intent_min_p, th.intent_min_margin) else None
    if intent == "unclear":
        intent = None
    
    if intent is None and pending.get("intent") and u.intent.label in (pending["intent"], "unclear"):
        intent = pending["intent"]
    
    if intent is None:
        new_counters = Counters(
            clarify=new_counters.clarify + 1,
            confirm_asks=new_counters.confirm_asks,
            injections=new_counters.injections,
            jev_failures=new_counters.jev_failures,
        )
        
        if new_counters.clarify > th.max_clarifications:
            return Route(
                next="handoff",
                goal={"kind": "handoff_notice"},
                counters=new_counters,
                reasons=("clarification_limit",),
                offer_human=offer_human,
            )
        
        options = u.intent.top(2, exclude={"unclear", "greeting_or_thanks"})
        return Route(
            next="clarify",
            goal={"kind": "ask_clarification", "topic": "intent", "options": options},
            counters=new_counters,
            offer_human=offer_human,
        )
    
    new_counters = Counters(
        clarify=0,
        confirm_asks=new_counters.confirm_asks,
        injections=new_counters.injections,
        jev_failures=new_counters.jev_failures,
    )
    
    if intent == "greeting_or_thanks":
        return Route(
            next="reply",
            goal={"kind": "greeting"},
            counters=new_counters,
            intent=intent,
            offer_human=offer_human,
        )
    
    if intent == "unsupported":
        return Route(
            next="reply",
            goal={"kind": "abstain", "offer_human": True},
            counters=new_counters,
            reasons=("unsupported",),
            intent=intent,
            offer_human=True,
        )
    
    if intent == "account_info":
        return Route(
            next="answer_inquiry",
            goal={"kind": "answer"},
            counters=new_counters,
            intent=intent,
            offer_human=offer_human,
        )
    
    if intent == "transaction_status":
        target = _extract_target(u.target, u.aliases, th)
        if not target:
            target = pending.get("target_txn_id")
            
            if not target:
                new_counters = Counters(
                    clarify=new_counters.clarify + 1,
                    confirm_asks=new_counters.confirm_asks,
                    injections=new_counters.injections,
                    jev_failures=new_counters.jev_failures,
                )
                
                if new_counters.clarify > th.max_clarifications:
                    return Route(
                        next="handoff",
                        goal={"kind": "handoff_notice"},
                        counters=new_counters,
                        reasons=("clarification_limit",),
                        intent=intent,
                        offer_human=offer_human,
                    )
                
                options = u.target.top(3)
                option_ids = [u.aliases.get(opt, opt) for opt in options if opt not in SPECIAL_TARGETS]
                return Route(
                    next="clarify",
                    goal={"kind": "ask_clarification", "topic": "transaction", "options": option_ids},
                    counters=new_counters,
                    intent=intent,
                    offer_human=offer_human,
                )
        
        return Route(
            next="answer_inquiry",
            goal={"kind": "answer"},
            counters=new_counters,
            intent=intent,
            target_txn_id=target,
            offer_human=offer_human,
        )
    
    if intent == "decline_explanation":
        target = _extract_target(u.target, u.aliases, th)
        if not target:
            target = pending.get("target_txn_id")
            
            if not target:
                new_counters = Counters(
                    clarify=new_counters.clarify + 1,
                    confirm_asks=new_counters.confirm_asks,
                    injections=new_counters.injections,
                    jev_failures=new_counters.jev_failures,
                )
                
                if new_counters.clarify > th.max_clarifications:
                    return Route(
                        next="handoff",
                        goal={"kind": "handoff_notice"},
                        counters=new_counters,
                        reasons=("clarification_limit",),
                        intent=intent,
                        offer_human=offer_human,
                    )
                
                options = u.target.top(3)
                option_ids = [u.aliases.get(opt, opt) for opt in options if opt not in SPECIAL_TARGETS]
                return Route(
                    next="clarify",
                    goal={"kind": "ask_clarification", "topic": "transaction", "options": option_ids},
                    counters=new_counters,
                    intent=intent,
                    offer_human=offer_human,
                )
        
        return Route(
            next="answer_inquiry",
            goal={"kind": "answer"},
            counters=new_counters,
            intent=intent,
            target_txn_id=target,
            offer_human=offer_human,
        )
    
    if intent == "dispute_status":
        return Route(
            next="answer_inquiry",
            goal={"kind": "answer"},
            counters=new_counters,
            intent=intent,
            offer_human=offer_human,
        )
    
    if intent == "dispute_charge":
        target = _extract_target(u.target, u.aliases, th)
        if not target:
            target = pending.get("target_txn_id")
        
        reason = u.reason.label if u.reason.label != "unclear" else None
        if not reason:
            reason = pending.get("dispute_reason")
        
        if not target or not reason:
            new_counters = Counters(
                clarify=new_counters.clarify + 1,
                confirm_asks=new_counters.confirm_asks,
                injections=new_counters.injections,
                jev_failures=new_counters.jev_failures,
            )
            
            if new_counters.clarify > th.max_clarifications:
                return Route(
                    next="handoff",
                    goal={"kind": "handoff_notice"},
                    counters=new_counters,
                    reasons=("clarification_limit",),
                    intent=intent,
                    target_txn_id=target,
                    dispute_reason=reason,
                    offer_human=offer_human,
                )
            
            if not target:
                options = u.target.top(3)
                option_ids = [u.aliases.get(opt, opt) for opt in options if opt not in SPECIAL_TARGETS]
                return Route(
                    next="clarify",
                    goal={"kind": "ask_clarification", "topic": "transaction", "options": option_ids},
                    counters=new_counters,
                    intent=intent,
                    target_txn_id=target,
                    dispute_reason=reason,
                    offer_human=offer_human,
                )
            
            if not reason:
                options = u.reason.top(3)
                return Route(
                    next="clarify",
                    goal={"kind": "ask_clarification", "topic": "dispute_reason", "options": options},
                    counters=new_counters,
                    intent=intent,
                    target_txn_id=target,
                    dispute_reason=reason,
                    offer_human=offer_human,
                )
        
        return Route(
            next="resolve_transaction",
            goal={},
            counters=new_counters,
            intent=intent,
            target_txn_id=target,
            dispute_reason=reason,
            offer_human=offer_human,
        )
    
    return Route(
        next="clarify",
        goal={"kind": "ask_clarification", "topic": "intent"},
        counters=new_counters,
        intent=intent,
        offer_human=offer_human,
    )
