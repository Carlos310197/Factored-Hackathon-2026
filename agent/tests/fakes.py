"""Test doubles for Claude (Bedrock) and, from Task 10, Jev."""
import json
import re
from types import SimpleNamespace

import anthropic
import httpx


class _FakeMessages:
    def __init__(self, owner: "FakeLLM"):
        self.o = owner

    def create(self, **kw):
        self.o.calls.append(kw)
        props = kw["output_config"]["format"]["schema"]["properties"]
        user = kw["messages"][0]["content"]
        if "english_gloss" in props:
            role = "extract"
        elif "reply_text" in props:
            role = "compose"
        else:
            role = "open_questions"
        self.o.roles.append(role)
        if role in self.o.fail:
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://bedrock.test"))
        if role in self.o.refuse:
            return SimpleNamespace(stop_reason="refusal", content=[], usage=SimpleNamespace(input_tokens=1, output_tokens=0))
        data = {"extract": self.o.extraction, "compose": self.o.composition,
                "open_questions": lambda u: {"questions": ["Which card was used?"]}}[role](user)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(data, ensure_ascii=False))],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))


class FakeLLM:
    def __init__(self, language="es", multi_intent=False, secondary=None, mentions=None, fail=(), refuse=(),
                 reply_text=None):
        self.language, self.multi_intent, self.secondary = language, multi_intent, secondary
        self.mentions, self.fail, self.refuse, self.reply_text = mentions or {}, set(fail), set(refuse), reply_text
        self.calls, self.roles = [], []
        self.messages = _FakeMessages(self)

    def extraction(self, user: str) -> dict:
        msg = re.search(r"<customer_message>\n(.*)\n</customer_message>", user, re.S).group(1)
        return {"language_detected": self.language, "english_gloss": f"EN: {msg}", "multi_intent": self.multi_intent,
                "secondary_request_en": self.secondary,
                "mentions": {"merchant": None, "amount": None, "currency": None, "date_from": None, "date_to": None}
                | self.mentions,
                "customer_statement": {"original": msg, "en": f"EN: {msg}"}}

    def composition(self, user: str) -> dict:
        goal = json.loads(re.search(r"<goal>(.*?)</goal>", user, re.S).group(1))
        receipts = json.loads(re.search(r"<receipts>(.*?)</receipts>", user, re.S).group(1))
        text = self.reply_text or (f"[{goal.get('kind')}]" + (" +queued" if goal.get("queued_offer") else "")
                                   + (" +human" if goal.get("offer_human") else ""))
        return {"reply_text": text,
                "claims": [{"claim_en": f"{goal.get('kind')} reply", "receipt_ids": [r["receipt_id"] for r in receipts]}]}
