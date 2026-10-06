"""Code decides every edge via state['route']['next']; no LLM ever chooses a graph edge."""
from langgraph.graph import END, StateGraph

from bankagent.graph.deps import Deps
from bankagent.graph.nodes import Nodes
from bankagent.graph.state import AgentState


def build_graph(deps: Deps, checkpointer):
    nodes = Nodes(deps)
    
    builder = StateGraph(AgentState)
    
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
    
    builder.set_entry_point("load_context")
    
    builder.add_conditional_edges(
        "load_context",
        lambda state: state["route"]["next"],
        {
            "understand": "understand",
            "reply": "reply"
        }
    )
    
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
    
    builder.add_conditional_edges(
        "answer_inquiry",
        lambda state: state["route"]["next"],
        {
            "reply": "reply",
            "clarify": "clarify"
        }
    )
    
    builder.add_conditional_edges(
        "resolve_transaction",
        lambda state: state["route"]["next"],
        {
            "check_eligibility": "check_eligibility",
            "clarify": "clarify"
        }
    )
    
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
    
    builder.add_edge("confirm", "reply")
    
    builder.add_conditional_edges(
        "file_dispute",
        lambda state: state["route"]["next"],
        {
            "confirm": "confirm",  # the card changed since the customer confirmed it: ask again
            "verify": "verify",
            "handoff": "handoff",
            "reply": "reply"
        }
    )
    
    builder.add_conditional_edges(
        "verify",
        lambda state: state["route"]["next"],
        {
            "reply": "reply",
            "handoff": "handoff"
        }
    )
    
    builder.add_edge("clarify", "reply")
    
    builder.add_edge("handoff", "reply")
    
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
    
    builder.add_edge("await_customer", "load_context")
    
    return builder.compile(checkpointer=checkpointer)
