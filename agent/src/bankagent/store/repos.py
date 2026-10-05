"""Repositories over DynamoDB: disputes (atomic one-per-transaction), handoffs, decision records."""
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from bankagent.ids import new_id
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
               versions: dict | None = None, latency_ms: int | None = None, trace_id: str | None = None) -> None:
        key = (session_id, turn_id)
        seq = self._seq.get(key, 0) + 1
        self._seq[key] = seq
        now = self.clock()
        item = {
            "session_id": session_id, "sk": f"{turn_id}#{seq:04d}", "turn_id": turn_id, "seq": seq, "node": node,
            "kind": kind, "ts": datetime.fromtimestamp(now, timezone.utc).isoformat(), "payload": payload,
            "versions": versions or {}, "latency_ms": latency_ms, "ttl": int(now) + self.TTL_DAYS * 86400}
        if trace_id:
            item["trace_id"] = trace_id  # links the audit record to its trace
        self.t.put_item(Item=to_dynamo(item))

    def list(self, session_id: str) -> list[dict]:
        items, kwargs = [], {"KeyConditionExpression": Key("session_id").eq(session_id)}
        while True:
            r = self.t.query(**kwargs)
            items += [from_dynamo(i) for i in r["Items"]]
            if "LastEvaluatedKey" not in r:
                return items
            kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="microseconds")


class SessionRepo:
    """One item per conversation (UI spec §4.1). `control` is changed only by the BFF's takeover/return."""

    TTL_DAYS = 90

    def __init__(self, table, clock=time.time):
        self.t, self.clock = table, clock

    def ensure(self, session_id: str, customer_id: str, lang: str) -> dict:
        now = self.clock()
        item = {"session_id": session_id, "customer_id": customer_id, "language": lang, "control": "agent",
                "created_at": _iso(now), "ttl": int(now) + self.TTL_DAYS * 86400}
        try:
            _conditional_put(self.t, item, "session_id")
        except AlreadyExists:
            pass
        return self.get(session_id)

    def get(self, session_id: str) -> dict | None:
        r = self.t.get_item(Key={"session_id": session_id}, ConsistentRead=True)
        return from_dynamo(r["Item"]) if "Item" in r else None

    def control(self, session_id: str) -> str:
        return (self.get(session_id) or {}).get("control", "agent")


class MessageLog:
    """The conversation transcript (UI spec §4.2) plus idempotency markers (`~idem#<message_id>`, kind=idem)."""
    TTL_DAYS = 90
    IDEM = "~idem#"

    def __init__(self, table, clock=time.time):
        self.t, self.clock = table, clock

    def _ttl(self) -> int:
        return int(self.clock()) + self.TTL_DAYS * 86400

    def claim(self, session_id: str, message_id: str) -> dict | None:
        item = {"session_id": session_id, "sk": f"{self.IDEM}{message_id}", "kind": "idem", "message_id": message_id,
                "state": "running", "ttl": self._ttl()}
        try:
            _conditional_put(self.t, item, "sk")
            return None
        except AlreadyExists:
            r = self.t.get_item(Key={"session_id": session_id, "sk": item["sk"]}, ConsistentRead=True)
            return from_dynamo(r["Item"])

    def store_reply(self, session_id: str, message_id: str, reply: dict) -> None:
        self.t.update_item(Key={"session_id": session_id, "sk": f"{self.IDEM}{message_id}"},
                           UpdateExpression="SET #s = :done, reply = :r",
                           ExpressionAttributeNames={"#s": "state"},
                           ExpressionAttributeValues={":done": "done", ":r": to_dynamo(reply)})

    def append(self, session_id: str, role: str, text: str, *, message_id: str | None = None,
               turn_id: str | None = None, author: str | None = None, meta: dict | None = None) -> dict:
        ts, mid = _iso(self.clock()), message_id or new_id("MSG")
        item = {"session_id": session_id, "sk": f"{ts}#{mid}", "kind": "message", "message_id": mid, "role": role,
                "text": text, "turn_id": turn_id, "author": author, "meta": meta, "ts": ts, "ttl": self._ttl()}
        self.t.put_item(Item=to_dynamo(item))
        return {k: v for k, v in item.items() if v is not None}

    def list(self, session_id: str, after: str | None = None) -> list[dict]:
        cond = Key("session_id").eq(session_id)
        if after:
            cond = cond & Key("sk").gt(after)
        items, kwargs = [], {"KeyConditionExpression": cond, "FilterExpression": Attr("kind").eq("message")}
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
    sessions: SessionRepo | None = None
    messages: MessageLog | None = None

    @classmethod
    def connect(cls, prefix: str, region: str, endpoint: str | None = None) -> "Store":
        res = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint)
        return cls(DisputeRepo(res.Table(table_name(prefix, "disputes"))),
                   HandoffRepo(res.Table(table_name(prefix, "handoffs"))),
                   DecisionLog(res.Table(table_name(prefix, "decision_records"))),
                   SessionRepo(res.Table(table_name(prefix, "sessions"))),
                   MessageLog(res.Table(table_name(prefix, "conversation_messages"))))
