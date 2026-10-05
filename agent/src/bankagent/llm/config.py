"""Per-role model configuration. The model id and prompt version of every call go into the decision record."""
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).with_name("models.yaml")


@dataclass(frozen=True)
class RoleConfig:
    model: str
    max_tokens: int
    prompt_version: str
    timeout_s: float
    effort: str | None = None


def load_models(path: Path = DEFAULT_PATH, env=None) -> dict[str, RoleConfig]:
    env = os.environ if env is None else env
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {role: RoleConfig(model=env.get(f"LLM_{role.upper()}_MODEL") or c["model"], max_tokens=c["max_tokens"],
                             prompt_version=c["prompt_version"], timeout_s=float(c["timeout_s"]), effort=c.get("effort"))
            for role, c in raw.items()}
