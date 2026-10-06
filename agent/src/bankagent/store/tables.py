"""DynamoDB table definitions (spec §7.2). The checkpoints layout (PK/SK/ttl) is what DynamoDBSaver requires."""
TABLE_SPECS = {
    "checkpoints": {"keys": [("PK", "S", "HASH"), ("SK", "S", "RANGE")], "gsis": [], "ttl": "ttl"},
    "disputes": {"keys": [("transaction_id", "S", "HASH")],
                 "gsis": [("by_customer", [("customer_id", "S", "HASH"), ("created_at", "S", "RANGE")])], "ttl": None},
    "handoffs": {"keys": [("handoff_id", "S", "HASH")],
                 "gsis": [("by_status", [("status", "S", "HASH"), ("created_at", "S", "RANGE")])], "ttl": None},
    "decision_records": {"keys": [("session_id", "S", "HASH"), ("sk", "S", "RANGE")], "gsis": [], "ttl": "ttl"},
    # UI spec §4.1–4.2
    # by_customer: the customer's own conversation list (newest first); the BFF writes ended_at / hidden on the item
    "sessions": {"keys": [("session_id", "S", "HASH")],
                 "gsis": [("by_customer", [("customer_id", "S", "HASH"), ("created_at", "S", "RANGE")])], "ttl": "ttl"},  # 90 days
    "conversation_messages": {"keys": [("session_id", "S", "HASH"), ("sk", "S", "RANGE")], "gsis": [], "ttl": "ttl"},
}
# Tables whose changes are pushed to the UI by the realtime publisher (UI spec §3)
STREAM_TABLES = ("handoffs", "decision_records", "conversation_messages")
STREAM_SPEC = {"StreamEnabled": True, "StreamViewType": "NEW_IMAGE"}


def table_name(prefix: str, name: str) -> str:
    return f"{prefix}-{name}"


def create_tables(client, prefix: str) -> list[str]:
    names = []
    for name, spec in TABLE_SPECS.items():
        tname = table_name(prefix, name)
        names.append(tname)
        attrs = {a: t for a, t, _ in spec["keys"]}
        for _, keys in spec["gsis"]:
            attrs.update({a: t for a, t, _ in keys})
        kwargs = {
            "TableName": tname, "BillingMode": "PAY_PER_REQUEST",
            "AttributeDefinitions": [{"AttributeName": a, "AttributeType": t} for a, t in attrs.items()],
            "KeySchema": [{"AttributeName": a, "KeyType": k} for a, _, k in spec["keys"]],
        }
        if spec["gsis"]:
            kwargs["GlobalSecondaryIndexes"] = [
                {"IndexName": n, "KeySchema": [{"AttributeName": a, "KeyType": k} for a, _, k in keys],
                 "Projection": {"ProjectionType": "ALL"}} for n, keys in spec["gsis"]]
        if name in STREAM_TABLES:
            kwargs["StreamSpecification"] = STREAM_SPEC
        try:
            client.create_table(**kwargs)
            client.get_waiter("table_exists").wait(TableName=tname)
            if spec["ttl"]:
                client.update_time_to_live(TableName=tname,
                                           TimeToLiveSpecification={"Enabled": True, "AttributeName": spec["ttl"]})
        except client.exceptions.ResourceInUseException:
            if name in STREAM_TABLES:  # tables created before the UI work: turn Streams on once
                current = client.describe_table(TableName=tname)["Table"].get("StreamSpecification") or {}
                if not current.get("StreamEnabled"):
                    client.update_table(TableName=tname, StreamSpecification=STREAM_SPEC)
    return names
