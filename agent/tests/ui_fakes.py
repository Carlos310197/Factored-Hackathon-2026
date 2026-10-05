"""In-memory stand-ins for SessionRepo / MessageLog / DecisionLog used by entrypoint tests."""
from types import SimpleNamespace


class FakeSessions:
    def __init__(self):
        self.items = {}

    def ensure(self, session_id, customer_id, lang):
        self.items.setdefault(session_id, {"session_id": session_id, "customer_id": customer_id, "language": lang,
                                           "control": "agent"})
        return self.items[session_id]

    def control(self, session_id):
        return self.items.get(session_id, {}).get("control", "agent")


class FakeMessages:
    def __init__(self):
        self.markers, self.rows = {}, []

    def claim(self, session_id, message_id):
        key = (session_id, message_id)
        if key in self.markers:
            return dict(self.markers[key])
        self.markers[key] = {"state": "running"}
        return None

    def store_reply(self, session_id, message_id, reply):
        self.markers[(session_id, message_id)] = {"state": "done", "reply": reply}

    def append(self, session_id, role, text, *, message_id=None, turn_id=None, author=None, meta=None):
        row = {"session_id": session_id, "role": role, "text": text, "message_id": message_id or f"m{len(self.rows)}",
               "turn_id": turn_id, "author": author, "meta": meta}
        self.rows.append(row)
        return row


class FakeLog:
    def __init__(self):
        self.records = []

    def append(self, session_id, turn_id, node, kind, payload, versions=None, latency_ms=None):
        self.records.append({"session_id": session_id, "turn_id": turn_id, "node": node, "kind": kind,
                             "payload": payload})


def fake_store():
    return SimpleNamespace(sessions=FakeSessions(), messages=FakeMessages(), log=FakeLog())


class FakeService:
    def __init__(self, store=None, reply=None):
        self.calls = []
        self.deps = SimpleNamespace(store=store or fake_store())
        self.reply = reply or {"reply_text": "ok", "awaiting": "none", "options": [], "refs": [],
                               "data_as_of": "2026-06-17"}

    def handle_turn(self, ctx, message, turn_id=None):
        self.calls.append((ctx, message, turn_id))
        return {**self.reply, "language": ctx.lang, "turn_id": turn_id}
