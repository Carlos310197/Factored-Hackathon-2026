"""State schema for the LangGraph workflow.
Everything in state must be JSON-serializable for checkpointing.
Identity (customer_id, session_id) is NOT in state—it comes from config['configurable']['ctx'],
verified on every turn. A session keeps the serving run_id it started with.
"""
from typing import Any
from dataclasses import dataclass, field
from langgraph.graph import MessagesState


@dataclass
class AgentState(MessagesState):
    """State for the agent workflow graph."""
    # Identity (from config, not stored in state)
    # customer_id: str  # from config['configurable']['ctx']
    # session_id: str   # from config['configurable']['ctx']
    
    # Current turn
    turn_id: str = ""
    message: str = ""
    language: str = "es"
    
    # Data access
    run_id: str = ""
    as_of: str = ""
    candidates: list[dict] = field(default_factory=list)
    allowed_ids: list[str] = field(default_factory=list)
    
    # Extraction and understanding
    extraction: dict | None = None
    route: dict = field(default_factory=dict)
    counters: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    
    # Goal and flow control
    goal: dict = field(default_factory=dict)
    awaiting: str = "none"  # "none", "clarification", "confirmation"
    clarification: dict | None = None
    
    # Pending intent (when clarification needed)
    pending: dict = field(default_factory=dict)
    intent: str | None = None
    target_txn_id: str | None = None
    dispute_reason: str | None = None
    escalated: bool = False
    
    # Transaction under dispute
    txn: dict = field(default_factory=dict)
    statement: dict = field(default_factory=dict)
    confirmation_summary: str = ""
    policy_checks: list[dict] = field(default_factory=list)
    
    # Filed dispute
    filed: dict = field(default_factory=dict)
    
    # Receipts and actions (audit trail)
    receipts: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    
    # Multi-intent queue
    queue: list[str] = field(default_factory=list)
    queued_offer: str | None = None
    
    # Conversation history (last 2 exchanges)
    recent: list[dict] = field(default_factory=list)
    
    # Final reply
    reply: dict = field(default_factory=dict)
