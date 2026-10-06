"""Everything in state must be JSON-serializable. Identity is not in state: it comes from the verified config."""
from typing import Any
from dataclasses import dataclass, field
from langgraph.graph import MessagesState


@dataclass
class AgentState(MessagesState):
    
    turn_id: str = ""
    message: str = ""
    language: str = "es"
    
    run_id: str = ""
    as_of: str = ""
    candidates: list[dict] = field(default_factory=list)
    allowed_ids: list[str] = field(default_factory=list)
    
    extraction: dict | None = None
    route: dict = field(default_factory=dict)
    counters: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    
    goal: dict = field(default_factory=dict)
    awaiting: str = "none"  # "none", "clarification", "confirmation"
    clarification: dict | None = None
    
    pending: dict = field(default_factory=dict)
    intent: str | None = None
    target_txn_id: str | None = None
    dispute_reason: str | None = None
    escalated: bool = False
    
    txn: dict = field(default_factory=dict)
    statement: dict = field(default_factory=dict)
    confirmation_summary: str = ""
    card_hash: str = ""
    policy_checks: list[dict] = field(default_factory=list)
    
    filed: dict = field(default_factory=dict)
    
    receipts: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    
    queue: list[str] = field(default_factory=list)
    queued_offer: str | None = None
    
    recent: list[dict] = field(default_factory=list)
    
    reply: dict = field(default_factory=dict)
