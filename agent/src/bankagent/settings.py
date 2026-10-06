"""Runtime settings from environment variables."""
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

import boto3

log = logging.getLogger(__name__)


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
    resolver_artifact: str | None = None  # a resolver artifact directory; unset = Jev alone
    thresholds_file: str | None = None  # e.g. decisions/thresholds.v2.yaml once the resolver is adopted
    git_sha: str = "dev"

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
            resolver_artifact=env.get("RESOLVER_ARTIFACT") or None,
            thresholds_file=env.get("THRESHOLDS_FILE") or None,
            git_sha=env.get("GIT_SHA", "dev"),
        )


def load_settings(env: Mapping[str, str] = os.environ, secrets_client=None) -> Settings:
    """Settings for the deployed runtime. When JEV_SECRET_ID is set and JEV_API_KEY isn't, the key is read from
    Secrets Manager once. A failure leaves it empty: Jev calls then fail and the graph clarifies or hands off.
    The container still starts, so /ping stays healthy (never a crash loop)."""
    # A failed secret read is not retried until the container restarts (the runtime is built once).
    merged = dict(env)
    secret_id = merged.get("JEV_SECRET_ID")
    if secret_id and not merged.get("JEV_API_KEY"):
        try:
            client = secrets_client or boto3.client("secretsmanager", region_name=merged.get("AWS_REGION", "us-east-1"))
            merged["JEV_API_KEY"] = client.get_secret_value(SecretId=secret_id)["SecretString"].strip()
        except Exception:
            log.exception("could not read the Jev secret %s; Jev calls will fail", secret_id)
    return Settings.from_env(merged)
