"""Build the LangGraph workflow.
The graph is a state machine where code decides edges via state['route']['next'].
No LLM ever chooses a graph edge.
"""
from langgraph.graph import END, StateGraph

from bankagent.graph.deps import Deps
from bankagent.graph.nodes import Nodes
from bankagent.graph.state import AgentState


def build_graph(deps: Deps, checkpointer):
    """Build the agent workflow graph."""
    nodes = Nodes(deps)
    
    builder = StateGraph(AgentState)
    
    # Add nodes
    builder.add_node("load_context", nodes.load_context)
    builder.add_node("understand", nodes.understand)
    builder.add_node("answer_inquiry", nodes.answer_inquiry)
    builder.add_node("resolve_transaction", nodes.resolve_transaction)
    builder.add_node("check_eligibility", nodes.check_eligibility)
    builder.add_node("confirm", nodes.confirm)
    builder.add_node("file_dispute", nodes.file_dispute)
    builder.add_node("verify", nodes.verify)
    builder.add_node("clarify", nodes.clarify)
    builder.add_node("handoff", nodes.handoff)
    builder.add_node("reply", nodes.reply)
    builder.add_node("await_customer", nodes.await_customer)
    
    # Entry point
    builder.set_entry_point("load_context")
    
    # Edges from load_context
    builder.add_conditional_edges(
        "load_context",
        lambda state: state["route"]["next"],
        {
            "understand": "understand",
            "reply": "reply"
        }
    )
    
    # Edges from understand
    builder.add_conditional_edges(
        "understand",
        lambda state: state["route"]["next"],
        {
            "answer_inquiry": "answer_inquiry",
            "resolve_transaction": "resolve_transaction",
            "clarify": "clarify",
            "handoff": "handoff",
            "reply": "reply",
            "file_dispute": "file_dispute",
            "confirm": "confirm"
        }
    )
    
    # Edges from answer_inquiry
    builder.add_conditional_edges(
        "answer_inquiry",
        lambda state: state["route"]["next"],
        {
            "reply": "reply",
            "clarify": "clarify"
        }
    )
    
    # Edges from resolve_transaction
    builder.add_conditional_edges(
        "resolve_transaction",
        lambda state: state["route"]["next"],
        {
            "check_eligibility": "check_eligibility",
            "clarify": "clarify"
        }
    )
    
    # Edges from check_eligibility
    builder.add_conditional_edges(
        "check_eligibility",
        lambda state: state["route"]["next"],
        {
            "confirm": "confirm",
            "file_dispute": "file_dispute",
            "answer_inquiry": "answer_inquiry",
            "reply": "reply"
        }
    )
    
    # Edges from confirm - always goes to reply
    builder.add_edge("confirm", "reply")
    
    # Edges from file_dispute
    builder.add_conditional_edges(
        "file_dispute",
        lambda state: state["route"]["next"],
        {
            "verify": "verify",
            "handoff": "handoff",
            "reply": "reply"
        }
    )
    
    # Edges from verify
    builder.add_conditional_edges(
        "verify",
        lambda state: state["route"]["next"],
        {
            "reply": "reply",
            "handoff": "handoff"
        }
    )
    
    # Edges from clarify - always goes to reply
    builder.add_edge("clarify", "reply")
    
    # Edges from handoff - always goes to reply
    builder.add_edge("handoff", "reply")
    
    # Edges from reply - check if we need to await customer
    def route_after_reply(state: AgentState) -> str:
        if state.get("awaiting") in ("clarification", "confirmation"):
            return "await"
        return "end"
    
    builder.add_conditional_edges(
        "reply",
        route_after_reply,
        {
            "await": "await_customer",
            "end": END
        }
    )
    
    # After await_customer, go back to load_context for next turn
    builder.add_edge("await_customer", "load_context")
    
    return builder.compile(checkpointer=checkpointer)
