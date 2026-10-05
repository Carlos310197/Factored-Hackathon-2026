import time

import boto3
import pytest
from moto import mock_aws

from bankagent.store.codec import from_dynamo, to_dynamo
from bankagent.store.repos import AlreadyExists, Store
from bankagent.store.tables import create_tables


@pytest.fixture
def ddb():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-2")
        create_tables(client, "t")
        yield Store.connect("t", "us-east-2"), client


def dispute(txn_id, created_at, customer="CLI-A"):
    return {"transaction_id": txn_id, "dispute_id": f"DSP-{txn_id}", "customer_id": customer, "amount": 15.99,
            "status": "submitted", "created_at": created_at, "customer_statement": {"original": "x", "en": "y"}}


def test_create_tables_idempotent_with_expected_keys(ddb):
    store, client = ddb
    assert create_tables(client, "t") == ["t-checkpoints", "t-disputes", "t-handoffs", "t-decision_records"]
    ks = client.describe_table(TableName="t-checkpoints")["Table"]["KeySchema"]
    assert ks == [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}]
    gsis = client.describe_table(TableName="t-disputes")["Table"]["GlobalSecondaryIndexes"]
    assert gsis[0]["IndexName"] == "by_customer"


def test_dispute_conditional_put_and_consistent_get(ddb):
    store, _ = ddb
    store.disputes.put_new(dispute("TRX-1", "2026-09-29T10:00:00Z"))
    with pytest.raises(AlreadyExists):
        store.disputes.put_new(dispute("TRX-1", "2026-09-29T11:00:00Z"))
    got = store.disputes.get("TRX-1")
    assert got["amount"] == 15.99 and got["created_at"] == "2026-09-29T10:00:00Z"
    assert store.disputes.get("TRX-404") is None


def test_list_for_customer_newest_first(ddb):
    store, _ = ddb
    store.disputes.put_new(dispute("TRX-1", "2026-09-29T10:00:00Z"))
    store.disputes.put_new(dispute("TRX-2", "2026-09-29T12:00:00Z"))
    store.disputes.put_new(dispute("TRX-3", "2026-09-29T11:00:00Z", customer="CLI-B"))
    assert [d["transaction_id"] for d in store.disputes.list_for_customer("CLI-A")] == ["TRX-2", "TRX-1"]


def test_handoffs_by_status(ddb):
    store, _ = ddb
    store.handoffs.put({"handoff_id": "HND-1", "status": "open", "created_at": "2026-09-29T10:00:00Z", "priority": "critical"})
    assert store.handoffs.get("HND-1")["priority"] == "critical"
    assert [h["handoff_id"] for h in store.handoffs.list_by_status("open")] == ["HND-1"]
    with pytest.raises(AlreadyExists):
        store.handoffs.put({"handoff_id": "HND-1", "status": "open", "created_at": "x"})


def test_decision_log_sequence_ttl_and_floats(ddb):
    store, _ = ddb
    store.log.append("S-1", "T1", "understand", "jev", {"p": 0.91}, {"question_set": "understand.v1"}, 120)
    store.log.append("S-1", "T1", "reply", "llm", {"ok": True})
    store.log.append("S-1", "T2", "understand", "error", {"error": "timeout"})
    items = store.log.list("S-1")
    assert [i["sk"] for i in items] == ["T1#0001", "T1#0002", "T2#0001"]
    assert items[0]["payload"]["p"] == 0.91 and items[0]["versions"]["question_set"] == "understand.v1"
    assert items[0]["latency_ms"] == 120 and items[0]["ttl"] > time.time() + 89 * 86400


def test_codec_roundtrip_drops_nulls():
    v = {"a": 1.5, "b": [2.25, {"c": None, "d": 3}], "e": "x"}
    assert from_dynamo(to_dynamo(v)) == {"a": 1.5, "b": [2.25, {"d": 3}], "e": "x"}
