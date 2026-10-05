import logging
import time

import boto3
import pytest
from moto import mock_aws

from bankagent.settings import load_settings
from bankagent.store.repos import Store
from bankagent.store.tables import TABLE_SPECS, create_tables

BASE = {"SERVING_URI": "s3://bucket/serving"}


class Boom:
    def get_secret_value(self, **_):
        raise AssertionError("Secrets Manager must not be called")


@pytest.fixture
def sm():
    with mock_aws():
        yield boto3.client("secretsmanager", region_name="us-east-1")


def test_jev_key_read_from_secret_and_stripped(sm):
    sm.create_secret(Name="lb-demo/jev", SecretString="tsk-123\n")
    assert load_settings({**BASE, "JEV_SECRET_ID": "lb-demo/jev"}, sm).jev_api_key == "tsk-123"


def test_explicit_env_key_wins_over_secret():
    s = load_settings({**BASE, "JEV_API_KEY": "from-env", "JEV_SECRET_ID": "lb-demo/jev"}, Boom())
    assert s.jev_api_key == "from-env"


def test_no_secret_id_means_no_secrets_call():
    assert load_settings(BASE, Boom()).jev_api_key == ""


def test_missing_secret_leaves_key_empty_and_does_not_raise(sm, caplog):
    caplog.set_level(logging.ERROR)
    s = load_settings({**BASE, "JEV_SECRET_ID": "lb-demo/missing"}, sm)
    assert s.jev_api_key == ""
    assert "Jev secret" in caplog.text and "lb-demo/missing" in caplog.text


def test_git_sha_from_env_with_default():
    assert load_settings({**BASE, "GIT_SHA": "abc1234"}).git_sha == "abc1234"
    assert load_settings(BASE).git_sha == "dev"


@pytest.fixture
def store():
    with mock_aws():
        create_tables(boto3.client("dynamodb", region_name="us-east-1"), "t")
        yield Store.connect("t", "us-east-1")


def test_sessions_expire_after_90_days(store):
    assert TABLE_SPECS["sessions"]["ttl"] == "ttl"
    item = store.sessions.ensure("S-1", "CLI-A", "es")
    assert time.time() + 89 * 86400 < item["ttl"] <= time.time() + 90 * 86400 + 5


def test_decision_record_keeps_trace_id_only_when_given(store):
    store.log.append("S-1", "T1", "understand", "route", {"next": "reply"}, trace_id="1-6720f2a0-0123456789abcdef01234567")
    store.log.append("S-1", "T1", "reply", "llm", {"role": "compose"})
    first, second = store.log.list("S-1")
    assert first["trace_id"] == "1-6720f2a0-0123456789abcdef01234567"
    assert "trace_id" not in second

