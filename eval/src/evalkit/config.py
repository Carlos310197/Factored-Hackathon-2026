"""eval/config.yaml loader and live-run validation."""
import os
from pathlib import Path

import yaml

DEFAULT = Path(__file__).resolve().parents[2] / "config.yaml"


class ConfigError(Exception):
    """The config cannot support the requested run."""


def load_config(path: Path = DEFAULT) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def require_live(cfg: dict) -> None:
    p = cfg["persona"]
    if not p.get("model"):
        raise ConfigError("persona.model is empty: set an OpenCode-served model before a live run")
    if p["model"].lower().startswith(("anthropic.", "claude")):
        raise ConfigError("the persona must not be a Claude model")
    if not os.environ.get(p["api_key_env"]):
        raise ConfigError(f"{p['api_key_env']} is not set")
    if not cfg["agent"].get("serving_uri"):
        raise ConfigError("agent.serving_uri is empty")
