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
MAX_TURNS = 30
SLOW_TURN_S = 20.0


class AgentService:
    """Agent service: one instance per process, holds the compiled graph."""

    def __init__(self, deps: Deps, checkpointer=None, turn_budget_s: float = 15.0, recursion_limit: int = 25,
                 max_turns: int = MAX_TURNS):
        self.deps = deps
        self.checkpointer = checkpointer or MemorySaver()
        self.turn_budget_s = turn_budget_s
        self.recursion_limit = recursion_limit
        self.max_turns = max_turns
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

        # Spend cap: the demo identities are public, so a session gets a fixed number of turns, counted atomically in
        # the sessions table before the model runs. A capped turn makes no Bedrock or Jev call.
        # per session only; a per-customer cap would count on the customer id the same way.
        if self.deps.store.sessions and not self.deps.store.sessions.take_turn(ctx.session_id, self.max_turns):
            from bankagent.llm.templates import fallback_reply
            logger.warning("session turn cap reached", extra={"session_id": ctx.session_id})
            return {"reply_text": fallback_reply({"kind": "turn_limit"}, [], ctx.lang), "language": ctx.lang,
                    "awaiting": "none", "options": [], "refs": [], "data_as_of": None, "turn_id": turn_id}

        initial_state: AgentState = {"message": message, "turn_id": turn_id}
        start = self.deps.clock()

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

        if self.deps.clock() - start > SLOW_TURN_S:  # CloudWatch alarm TurnSlow; the BFF gives up at 25 s
            logger.warning("slow turn", extra={"session_id": ctx.session_id, "turn_id": turn_id})
        return {**result["reply"], "turn_id": turn_id}

    def state(self, ctx: SessionContext) -> dict[str, Any]:
        """Get the current graph state for a session."""
        config: RunnableConfig = {"configurable": {"thread_id": ctx.session_id}}
        snapshot = self.graph.get_state(config)
        return snapshot.values if snapshot else {}
