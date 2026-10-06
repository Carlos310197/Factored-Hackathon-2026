from pathlib import Path

import yaml

AGENT = Path(__file__).resolve().parents[1]


def test_compose_enables_the_adopted_resolver():
    env = yaml.safe_load((AGENT / "docker-compose.yml").read_text())["services"]["agent"]["environment"]
    for key in ("RESOLVER_ARTIFACT", "THRESHOLDS_FILE"):
        assert env[key].startswith("/app/"), key
        assert (AGENT / env[key].removeprefix("/app/")).exists(), f"{key} points at a file that is not in the image"
