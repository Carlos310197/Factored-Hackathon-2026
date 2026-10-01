"""Snowflake connection from environment variables.

Auth, first match wins: AWS workload identity (CI, role gha-deploy), named snow CLI connection (local dev), key pair (dbt fallback).
"""
import os
from collections.abc import Mapping

from dotenv import load_dotenv


def build_connect_kwargs(env: Mapping[str, str], database: str | None = None) -> dict:
    kw = {
        "role": env["SNOWFLAKE_ROLE"],
        "warehouse": env["SNOWFLAKE_WAREHOUSE"],
        "database": database or env["SNOWFLAKE_DATABASE"],
        "client_session_keep_alive": False,
    }
    if env.get("SNOWFLAKE_CONNECTION_NAME") and not env.get("SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER"):
        # account/user/password come from the snow CLI config.toml, never from .env
        kw["connection_name"] = env["SNOWFLAKE_CONNECTION_NAME"]
        return kw
    kw.update(account=env["SNOWFLAKE_ACCOUNT"], user=env["SNOWFLAKE_USER"])
    if env.get("SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER"):
        # credentials come from the ambient AWS session (configure-aws-credentials in CI)
        kw.update(authenticator="WORKLOAD_IDENTITY", workload_identity_provider=env["SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER"])
    elif env.get("SNOWFLAKE_PRIVATE_KEY_PATH"):
        kw["private_key_file"] = env["SNOWFLAKE_PRIVATE_KEY_PATH"]
    else:
        raise ValueError("set SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER or SNOWFLAKE_PRIVATE_KEY_PATH (or SNOWFLAKE_CONNECTION_NAME locally)")
    return kw


def get_connection(database: str | None = None):
    import snowflake.connector

    load_dotenv()
    return snowflake.connector.connect(**build_connect_kwargs(os.environ, database))


if __name__ == "__main__":  # smoke check: uv run python -m pipeline.connect
    with get_connection() as conn:
        print(conn.cursor().execute("select current_user(), current_role(), current_warehouse(), current_database()").fetchone())
