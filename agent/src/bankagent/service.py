"""Agent service: wraps the compiled graph with turn handling, state management, and error recovery."""
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from bankagent.context import SessionContext
from bankagent.graph.build import build_graph
from bankagent.graph.deps import Deps
from bankagent.graph.state import AgentState
from bankagent.ids import new_id

logger = logging.getLogger(__name__)


class AgentService:
    """Agent service: one instance per process, holds the compiled graph."""

    def __init__(self, deps: Deps, checkpointer=None, turn_budget_s: float = 20.0, recursion_limit: int = 25):
        self.deps = deps
        self.checkpointer = checkpointer or MemorySaver()
        self.turn_budget_s = turn_budget_s
        self.recursion_limit = recursion_limit
        self.graph: CompiledStateGraph = build_graph(deps, self.checkpointer)

    def handle_turn(self, ctx: SessionContext, message: str, turn_id: str | None = None) -> dict:
        """Process one customer turn. Returns the reply dict."""
        turn_id = turn_id or new_id("TRN")
        config: RunnableConfig = {
            "configurable": {
                "thread_id": ctx.session_id,
                "ctx": ctx,
                "deadline": self.deps.clock() + self.turn_budget_s,
            },
            "recursion_limit": self.recursion_limit,
        }

        initial_state: AgentState = {"message": message, "turn_id": turn_id}
        
        try:
            result = self.graph.invoke(initial_state, config)
        except Exception as e:
            logger.exception("turn failed", extra={"session_id": ctx.session_id, "turn_id": turn_id})
            # Return safe fallback
            from bankagent.llm.templates import fallback_reply
            return {
                "reply_text": fallback_reply({"kind": "error"}, [], ctx.lang),
                "language": ctx.lang,
                "awaiting": "none",
                "options": [],
                "refs": [],
                "data_as_of": None,
                "turn_id": turn_id,
            }

        return {**result["reply"], "turn_id": turn_id}

    def state(self, ctx: SessionContext) -> dict[str, Any]:
        """Get the current graph state for a session."""
        config: RunnableConfig = {"configurable": {"thread_id": ctx.session_id}}
        snapshot = self.graph.get_state(config)
        return snapshot.values if snapshot else {}
