"""Runtime settings from environment variables."""
import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    aws_region: str
    serving_uri: str
    table_prefix: str
    dynamodb_endpoint: str | None
    jev_api_key: str
    jev_url: str
    jev_model: str
    issuer: str
    audience: str
    jwks_url: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        return cls(
            aws_region=env.get("AWS_REGION", "us-east-1"),
            serving_uri=env["SERVING_URI"],
            table_prefix=env.get("TABLE_PREFIX", "bankagent-dev"),
            dynamodb_endpoint=env.get("DYNAMODB_ENDPOINT") or None,
            jev_api_key=env.get("JEV_API_KEY", ""),
            jev_url=env.get("JEV_URL", "https://api.typesafe.ai/v1/systemone"),
            jev_model=env.get("JEV_MODEL", "jev-1.13.0"),
            issuer=env.get("IDP_ISSUER", "http://localhost:8081"),
            audience=env.get("IDP_AUDIENCE", "bankagent"),
            jwks_url=env.get("IDP_JWKS_URL", "http://localhost:8081/jwks.json"),
        )
