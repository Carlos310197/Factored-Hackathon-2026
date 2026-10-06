"""Demo logins for the mock identity service. These are labeled TEST identities, not customer credentials."""
import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DemoUser:
    username: str
    password_sha256: str
    otp: str = ""
    customer_id: str = ""
    lang: str = "es"
    role: str = "customer"            # customer | agent
    display_name: str = ""
    demo_password: str = ""           # served only by /auth/demo-users in demo mode
    scenarios: tuple[str, ...] = ()
    short_ttl_allowed: bool = False   # may request a 30 s token (the "expired token" scenario)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def load_users(path) -> dict[str, DemoUser]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {u["username"]: DemoUser(**{**u, "scenarios": tuple(u.get("scenarios") or ())}) for u in raw["users"]}
