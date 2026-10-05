from datetime import date

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from moto import mock_aws

from bankagent.context import SCOPE_DISPUTE, SCOPE_READ, PermissionDenied, SessionContext
from bankagent.data.serving import ServingData
from bankagent.policy.dispute import DisputePolicy
from bankagent.store.repos import Store
from bankagent.store.tables import create_tables
from bankagent.tools.read import NotFound, ReadTools
from bankagent.tools.write import AlreadyDisputed, PolicyRejected, WriteFailed, WriteTools
from tests.fixtures.serving_fixture import C1, C2, RUN_ID, t

CTX = SessionContext(C1, "S-1", frozenset({SCOPE_READ, SCOPE_DISPUTE}), "es", 0)
AS = date(2026, 6, 17)
STMT = {"original": "Me cobraron dos veces", "en": "I was charged twice"}


@pytest.fixture
def env(serving_root):
    with mock_aws():
        create_tables(boto3.client("dynamodb", region_name="us-east-2"), "t")
        store = Store.connect("t", "us-east-2")
        yield store, ReadTools(ServingData(str(serving_root))), WriteTools(store, DisputePolicy.load())


def txn(read, n):
    return read.get_transaction(CTX, RUN_ID, AS, t(n)).data


def create(write, tx, reason="duplicate_charge", escalation=False, ctx=CTX):
    return write.create_dispute(ctx, tx, reason, STMT, AS, escalation, "S-1", "T1", "es")


def test_automated_dispute_written_then_verified(env):
    store, read, write = env
    r = create(write, txn(read, 101))
    assert r.source == "disputes" and r.data["route"] == "automated" and r.data["status"] == "submitted"
    assert r.data["dispute_id"].startswith("DSP-") and r.data["policy_version"] == "dispute-policy.v1"
    rec = store.disputes.get(t(101))
    assert rec["customer_statement"] == STMT and rec["session_id"] == "S-1" and rec["language"] == "es"
    v = write.verify_dispute(CTX, r.data, AS)
    assert v.source == "disputes.verify" and v.data["verified"] is True and v.data["mismatches"] == []
    assert len(v.data["record_hash"]) == 64


def test_second_dispute_on_same_transaction(env):
    _, read, write = env
    first = create(write, txn(read, 101))
    with pytest.raises(AlreadyDisputed) as e:
        create(write, txn(read, 101))
    assert e.value.existing["dispute_id"] == first.data["dispute_id"]


def test_over_limit_is_recorded_for_human_review(env):
    _, read, write = env
    r = create(write, txn(read, 105), reason="wrong_amount")
    assert r.data["route"] == "human_review" and r.data["status"] == "pending_review"


def test_escalation_forces_human_review(env):
    _, read, write = env
    assert create(write, txn(read, 100), escalation=True).data["route"] == "human_review"


def test_declined_rejected_by_policy_and_not_written(env):
    store, read, write = env
    with pytest.raises(PolicyRejected) as e:
        create(write, txn(read, 102))
    assert e.value.result.redirect == "explain_decline" and store.disputes.get(t(102)) is None


def test_requires_dispute_scope(env):
    _, read, write = env
    with pytest.raises(PermissionDenied):
        create(write, txn(read, 101), ctx=SessionContext(C1, "S-1", frozenset({SCOPE_READ}), "es", 0))


def test_foreign_transaction_is_not_found(env):
    _, read, write = env
    with pytest.raises(NotFound):
        create(write, {**txn(read, 101), "customer_id": C2})


def test_unknown_write_outcome_resolved_by_read_back(env, monkeypatch):
    store, read, write = env
    real = store.disputes.put_new

    def lands_then_times_out(item):
        real(item)
        raise EndpointConnectionError(endpoint_url="http://ddb")

    monkeypatch.setattr(store.disputes, "put_new", lands_then_times_out)
    r = create(write, txn(read, 100))
    assert store.disputes.get(t(100))["dispute_id"] == r.data["dispute_id"]


def test_unknown_write_outcome_twice_without_record_fails(env, monkeypatch):
    store, read, write = env

    def down(item):
        raise EndpointConnectionError(endpoint_url="http://ddb")

    monkeypatch.setattr(store.disputes, "put_new", down)
    with pytest.raises(WriteFailed):
        create(write, txn(read, 100))


def test_verify_detects_mismatch(env):
    _, read, write = env
    r = create(write, txn(read, 101))
    v = write.verify_dispute(CTX, {**r.data, "status": "resolved"}, AS)
    assert v.data["verified"] is False and v.data["mismatches"] == ["status"]


def test_list_disputes_scoped_to_customer(env):
    _, read, write = env
    create(write, txn(read, 101))
    r = write.list_disputes(CTX, AS)
    assert [d["transaction_id"] for d in r.data] == [t(101)]
    other = SessionContext(C2, "S-2", frozenset({SCOPE_READ}), "pt", 0)
    assert write.list_disputes(other, AS).data == []
