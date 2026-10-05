"""Wires the real graph with fake Claude/Jev, the labeled synthetic serving fixture and a moto DynamoDB store."""
import time
from dataclasses import dataclass

from langgraph.checkpoint.memory import InMemorySaver

from bankagent.context import SCOPE_DISPUTE, SCOPE_READ, SessionContext
from bankagent.data.serving import ServingData
from bankagent.decisions.questions import load_question_set
from bankagent.decisions.thresholds import load_thresholds
from bankagent.graph.deps import Deps
from bankagent.llm.config import load_models
from bankagent.policy.dispute import DisputePolicy
from bankagent.service import AgentService
from bankagent.store.repos import Store
from bankagent.tools.read import ReadTools
from bankagent.tools.write import WriteTools
from tests.fakes import FakeJev, FakeLLM
from tests.fixtures.serving_fixture import C1

EXP = 2_000_000_000
CTX_ES = SessionContext(C1, "S-es", frozenset({SCOPE_READ, SCOPE_DISPUTE}), "es", EXP)
CTX_ES2 = SessionContext(C1, "S-es-2", frozenset({SCOPE_READ, SCOPE_DISPUTE}), "es", EXP)
CTX_PT = SessionContext(C1, "S-pt", frozenset({SCOPE_READ, SCOPE_DISPUTE}), "pt", EXP)
CTX_READ_ONLY = SessionContext(C1, "S-ro", frozenset({SCOPE_READ}), "es", EXP)


@dataclass
class Harness:
    service: AgentService
    store: Store
    jev: FakeJev
    llm: FakeLLM

    def turn(self, message: str, ctx: SessionContext = CTX_ES) -> dict:
        return self.service.handle_turn(ctx, message)

    def state(self, ctx: SessionContext = CTX_ES) -> dict:
        return self.service.state(ctx)

    def log_kinds(self, ctx: SessionContext = CTX_ES) -> list[str]:
        return [r["kind"] for r in self.store.log.list(ctx.session_id)]


def make_harness(store, serving_uri, specs, llm=None, verify=True, clock=None, recursion_limit=25,
                 turn_budget_s=20.0) -> Harness:
    serving, policy = ServingData(str(serving_uri)), DisputePolicy.load()
    llm, jev = llm or FakeLLM(), FakeJev(specs, verify)
    deps = Deps(read=ReadTools(serving), write=WriteTools(store, policy), store=store, policy=policy, jev=jev,
                llm_client=llm, models=load_models(env={}), thresholds=load_thresholds(),
                understand_qs=load_question_set("understand.v1"), verify_qs=load_question_set("verify_reply.v1"),
                clock=clock or time.monotonic)
    service = AgentService(deps, InMemorySaver(), turn_budget_s=turn_budget_s, recursion_limit=recursion_limit)
    return Harness(service, store, jev, llm)
