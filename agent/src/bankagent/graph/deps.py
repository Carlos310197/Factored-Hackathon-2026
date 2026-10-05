"""Dependencies for the graph nodes.
All external services and configuration are injected here, making nodes testable.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from bankagent.decisions.thresholds import Thresholds
from bankagent.policy.dispute import DisputePolicy
from bankagent.store.repos import Store
from bankagent.tools.read import ReadTools
from bankagent.tools.write import WriteTools


@dataclass
class Deps:
    """All dependencies for graph nodes."""
    # Tools
    read: ReadTools
    write: WriteTools
    
    # Storage
    store: Store
    
    # Policy
    policy: DisputePolicy
    
    # Decision services
    jev: Any  # JevClient or FakeJev
    llm_client: Any  # OpenAI client or FakeLLM
    
    # Configuration
    models: dict  # role -> RoleConfig
    thresholds: Thresholds
    understand_qs: dict  # understand.v1 question set
    verify_qs: dict  # verify_reply.v1 question set
    
    # Language settings
    gloss_mode: dict[str, str] = field(default_factory=lambda: {
        "es": "original_plus_gloss",
        "pt": "original_plus_gloss"
    })
    
    # Timing
    clock: Callable[[], float] = field(default_factory=time.monotonic)
