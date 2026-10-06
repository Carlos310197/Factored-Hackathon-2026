import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from langgraph_checkpoint_aws import DynamoDBSaver

from bankagent.auth.tokens import JwksCache
from bankagent.data.serving import ServingData
from bankagent.decisions.jev import JevClient
from bankagent.decisions.questions import load_question_set
from bankagent.decisions.thresholds import load_thresholds
from bankagent.graph.deps import Deps
from bankagent.llm.client import make_bedrock_client, warm_up
from bankagent.llm.config import load_models
from bankagent.policy.dispute import DisputePolicy
from bankagent.resolver.model import Resolver, ResolverUnavailable
from bankagent.service import AgentService
from bankagent.settings import Settings
from bankagent.store.repos import Store
from bankagent.store.tables import table_name
from bankagent.tools.read import ReadTools
from bankagent.tools.write import WriteTools

CHECKPOINT_TTL_S = 30 * 86400
log = logging.getLogger(__name__)


def load_resolver(path: str | None) -> Resolver | None:
    """A missing or broken resolver artifact means no scores, never a failed start."""
    if not path:
        return None
    try:
        return Resolver.load(Path(path))
    except ResolverUnavailable:
        log.exception("resolver artifact unavailable; running without resolver scores")
        return None


@dataclass
class Runtime:
    settings: Settings
    service: AgentService
    jwks: JwksCache


def build_runtime(settings: Settings) -> Runtime:
    serving = ServingData(settings.serving_uri, settings.aws_region)
    store = Store.connect(settings.table_prefix, settings.aws_region, settings.dynamodb_endpoint)
    policy = DisputePolicy.load()
    resolver = load_resolver(settings.resolver_artifact)
    thresholds = load_thresholds(Path(settings.thresholds_file)) if settings.thresholds_file else load_thresholds()
    deps = Deps(read=ReadTools(serving), write=WriteTools(store, policy), store=store, policy=policy,
                jev=JevClient(settings.jev_api_key, settings.jev_url, settings.jev_model),
                llm_client=make_bedrock_client(settings.aws_region), models=load_models(),
                thresholds=thresholds, understand_qs=load_question_set("understand.v1"),
                verify_qs=load_question_set("verify_reply.v1"), resolver=resolver,
                understand_qs_scored=load_question_set("understand.v2") if resolver else None)
    checkpointer = DynamoDBSaver(table_name=table_name(settings.table_prefix, "checkpoints"),
                                 region_name=settings.aws_region, endpoint_url=settings.dynamodb_endpoint,
                                 ttl_seconds=CHECKPOINT_TTL_S)
    threading.Thread(target=warm_up, args=(deps.llm_client, deps.models), daemon=True).start()
    return Runtime(settings, AgentService(deps, checkpointer), JwksCache(settings.jwks_url))
