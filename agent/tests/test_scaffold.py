import pytest

from bankagent.context import SCOPE_DISPUTE, SCOPE_READ, PermissionDenied, SessionContext
from bankagent.ids import new_id
from bankagent.settings import Settings


def test_settings_defaults():
    s = Settings.from_env({"SERVING_URI": "/tmp/serving"})
    assert s.aws_region == "us-east-1"
    assert s.jev_url == "https://api.typesafe.ai/v1/systemone"
    assert s.jev_model == "jev-1.13.0"
    assert s.dynamodb_endpoint is None
    assert s.table_prefix == "bankagent-dev"


def test_settings_requires_serving_uri():
    with pytest.raises(KeyError):
        Settings.from_env({})


def test_session_context_require_scope():
    ctx = SessionContext("CLI-X", "S-1", frozenset({SCOPE_READ}), "es", 0)
    ctx.require(SCOPE_READ)
    with pytest.raises(PermissionDenied):
        ctx.require(SCOPE_DISPUTE)


def test_new_id_prefix_and_uniqueness():
    a, b = new_id("DSP"), new_id("DSP")
    assert a.startswith("DSP-") and b.startswith("DSP-") and a != b
