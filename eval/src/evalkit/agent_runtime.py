import os


def table_prefix(run_id: str, rep: int) -> str:
    return f"eval-{run_id}-r{rep}"  # one prefix per repetition: a goal's reps never share a dispute table


def ensure_tables(cfg: dict, prefix: str) -> None:
    import boto3
    from bankagent.store.tables import create_tables
    a = cfg["agent"]
    create_tables(boto3.client("dynamodb", region_name=a["region"], endpoint_url=a["dynamodb_endpoint"]), prefix)


def build_eval_runtime(cfg: dict, prefix: str, fault: str | None, tokens):
    from bankagent.auth.tokens import JwksCache
    from bankagent.runtime import build_runtime
    from bankagent.settings import Settings

    from evalkit.faults import apply_fault
    a = cfg["agent"]
    env = {**os.environ, "SERVING_URI": a["serving_uri"], "TABLE_PREFIX": prefix,
           "DYNAMODB_ENDPOINT": a["dynamodb_endpoint"], "AWS_REGION": a["region"], "IDP_ISSUER": tokens.issuer,
           "IDP_AUDIENCE": tokens.audience, "IDP_JWKS_URL": "eval://jwks"}
    settings = Settings.from_env(env)
    rt = build_runtime(settings)
    jwks = tokens.jwks
    rt.jwks = JwksCache(settings.jwks_url, fetch=lambda _url: jwks)
    real_store = rt.service.deps.store
    apply_fault(rt.service.deps, fault)
    return rt, real_store
