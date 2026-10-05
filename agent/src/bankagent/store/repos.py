"""Repositories over DynamoDB: disputes (atomic one-per-transaction), handoffs, decision records."""
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from bankagent.store.codec import from_dynamo, to_dynamo
from bankagent.store.tables import table_name


class AlreadyExists(Exception):
    pass


def _conditional_put(table, item: dict, key: str) -> None:
    try:
        table.put_item(Item=to_dynamo(item), ConditionExpression=f"attribute_not_exists({key})")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise AlreadyExists(item[key]) from e
        raise


class DisputeRepo:
    def __init__(self, table):
        self.t = table

    def put_new(self, item: dict) -> None:
        _conditional_put(self.t, item, "transaction_id")

    def get(self, transaction_id: str) -> dict | None:
        r = self.t.get_item(Key={"transaction_id": transaction_id}, ConsistentRead=True)
        return from_dynamo(r["Item"]) if "Item" in r else None

    def list_for_customer(self, customer_id: str) -> list[dict]:
        r = self.t.query(IndexName="by_customer", KeyConditionExpression=Key("customer_id").eq(customer_id),
                         ScanIndexForward=False)
        return [from_dynamo(i) for i in r["Items"]]


class HandoffRepo:
    def __init__(self, table):
        self.t = table

    def put(self, item: dict) -> None:
        _conditional_put(self.t, item, "handoff_id")

    def get(self, handoff_id: str) -> dict | None:
        r = self.t.get_item(Key={"handoff_id": handoff_id}, ConsistentRead=True)
        return from_dynamo(r["Item"]) if "Item" in r else None

    def list_by_status(self, status: str) -> list[dict]:
        r = self.t.query(IndexName="by_status", KeyConditionExpression=Key("status").eq(status),
                         ScanIndexForward=False)
        return [from_dynamo(i) for i in r["Items"]]


class DecisionLog:
    """The execution record (spec §7.4): one item per step, keyed session → turn#seq, 90-day TTL."""
    TTL_DAYS = 90

    def __init__(self, table, clock=time.time):
        self.t, self.clock = table, clock
        self._seq: dict[tuple[str, str], int] = {}

    def append(self, session_id: str, turn_id: str, node: str, kind: str, payload: dict,
               versions: dict | None = None, latency_ms: int | None = None) -> None:
        key = (session_id, turn_id)
        seq = self._seq.get(key, 0) + 1
        self._seq[key] = seq
        now = self.clock()
        self.t.put_item(Item=to_dynamo({
            "session_id": session_id, "sk": f"{turn_id}#{seq:04d}", "turn_id": turn_id, "seq": seq, "node": node,
            "kind": kind, "ts": datetime.fromtimestamp(now, timezone.utc).isoformat(), "payload": payload,
            "versions": versions or {}, "latency_ms": latency_ms, "ttl": int(now) + self.TTL_DAYS * 86400}))

    def list(self, session_id: str) -> list[dict]:
        items, kwargs = [], {"KeyConditionExpression": Key("session_id").eq(session_id)}
        while True:
            r = self.t.query(**kwargs)
            items += [from_dynamo(i) for i in r["Items"]]
            if "LastEvaluatedKey" not in r:
                return items
            kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


@dataclass
class Store:
    disputes: DisputeRepo
    handoffs: HandoffRepo
    log: DecisionLog

    @classmethod
    def connect(cls, prefix: str, region: str, endpoint: str | None = None) -> "Store":
        res = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint)
        return cls(DisputeRepo(res.Table(table_name(prefix, "disputes"))),
                   HandoffRepo(res.Table(table_name(prefix, "handoffs"))),
                   DecisionLog(res.Table(table_name(prefix, "decision_records"))))
