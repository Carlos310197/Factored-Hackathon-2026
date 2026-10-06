from pipeline.connect import build_connect_kwargs

BASE = {
    "SNOWFLAKE_ACCOUNT": "acme-xy12345",
    "SNOWFLAKE_USER": "PIPELINE_SVC",
    "SNOWFLAKE_ROLE": "PIPELINE_ROLE",
    "SNOWFLAKE_WAREHOUSE": "WH_PIPELINE",
    "SNOWFLAKE_DATABASE": "LATAM_BANK",
}

def test_aws_workload_identity_wins():
    kw = build_connect_kwargs({**BASE, "SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER": "AWS", "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"})
    assert kw["authenticator"] == "WORKLOAD_IDENTITY"
    assert kw["workload_identity_provider"] == "AWS"
    assert "token" not in kw and "private_key_file" not in kw
    assert kw["account"] == "acme-xy12345" and kw["user"] == "PIPELINE_SVC"

def test_key_pair_when_no_token():
    kw = build_connect_kwargs({**BASE, "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"})
    assert kw["private_key_file"] == "/k.p8"
    assert "authenticator" not in kw

def test_common_fields_and_database_override():
    kw = build_connect_kwargs({**BASE, "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"}, database="LATAM_FIXTURE")
    assert kw["account"] == "acme-xy12345" and kw["user"] == "PIPELINE_SVC"
    assert kw["role"] == "PIPELINE_ROLE" and kw["warehouse"] == "WH_PIPELINE"
    assert kw["database"] == "LATAM_FIXTURE"

def test_named_connection_for_local_dev():
    env = {k: v for k, v in BASE.items() if k not in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER")}
    kw = build_connect_kwargs({**env, "SNOWFLAKE_CONNECTION_NAME": "sbx"})
    assert kw["connection_name"] == "sbx"
    assert kw["role"] == "PIPELINE_ROLE" and kw["database"] == "LATAM_BANK"
    assert "account" not in kw and "private_key_file" not in kw

def test_missing_auth_raises():
    import pytest
    with pytest.raises(ValueError, match="SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER"):
        build_connect_kwargs(BASE)
