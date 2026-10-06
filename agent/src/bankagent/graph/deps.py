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
    read: ReadTools
    write: WriteTools
    
    store: Store
    
    policy: DisputePolicy
    
    jev: Any
    llm_client: Any
    
    models: dict
    thresholds: Thresholds
    understand_qs: dict
    verify_qs: dict
    
    gloss_mode: dict[str, str] = field(default_factory=lambda: {
        "es": "original_plus_gloss",
        "pt": "original_plus_gloss"
    })
    
    clock: Callable[[], float] = field(default_factory=lambda: time.monotonic)

    resolver: Any = None
    understand_qs_scored: dict | None = None
