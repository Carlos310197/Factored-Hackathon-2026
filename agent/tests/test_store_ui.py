import boto3
import pytest
from moto import mock_aws

from bankagent.store.repos import Store
from bankagent.store.tables import create_tables


@pytest.fixture
def ddb():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-2")
        create_tables(client, "t")
        yield Store.connect("t", "us-east-2"), client


def test_new_tables_exist_and_streams_are_on(ddb):
    _, client = ddb
    assert client.describe_table(TableName="t-sessions")["Table"]["KeySchema"] == [
        {"AttributeName": "session_id", "KeyType": "HASH"}]
    for name in ("t-handoffs", "t-decision_records", "t-conversation_messages"):
        spec = client.describe_table(TableName=name)["Table"]["StreamSpecification"]
        assert spec == {"StreamEnabled": True, "StreamViewType": "NEW_IMAGE"}, name


def test_session_ensure_is_idempotent_and_control_defaults_to_agent(ddb):
    store, _ = ddb
    first = store.sessions.ensure("S-1", "CLI-A", "es")
    again = store.sessions.ensure("S-1", "CLI-OTHER", "pt")
    assert first["customer_id"] == again["customer_id"] == "CLI-A" and again["language"] == "es"
    assert store.sessions.control("S-1") == "agent" and store.sessions.control("S-404") == "agent"


def test_claim_marks_new_ids_and_returns_existing_marker(ddb):
    store, _ = ddb
    assert store.messages.claim("S-1", "m-00000001") is None
    marker = store.messages.claim("S-1", "m-00000001")
    assert marker["state"] == "running" and "reply" not in marker
    store.messages.store_reply("S-1", "m-00000001", {"reply_text": "hola", "awaiting": "none"})
    assert store.messages.claim("S-1", "m-00000001")["reply"]["reply_text"] == "hola"


def test_append_and_list_in_order_after_cursor_without_markers(ddb):
    store, _ = ddb
    t = [1000.0]
    store.messages.clock = lambda: t[0]
    a = store.messages.append("S-1", "customer", "hola", message_id="m-a", turn_id="TRN-1")
    t[0] += 1
    store.messages.claim("S-1", "m-b")
    b = store.messages.append("S-1", "assistant", "¿en qué te ayudo?", turn_id="TRN-1",
                              meta={"awaiting": "none", "refs": []})
    items = store.messages.list("S-1")
    assert [i["message_id"] for i in items] == ["m-a", b["message_id"]]
    assert items[0]["turn_id"] == "TRN-1" and items[1]["meta"]["awaiting"] == "none"
    assert [i["message_id"] for i in store.messages.list("S-1", after=a["sk"])] == [b["message_id"]]
    assert items[0]["ttl"] == 1000 + 90 * 86400  # TTL follows the injected clock
