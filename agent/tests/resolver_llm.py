"""Scripted LLM for resolver dataset tests: the dev writer echoes its details; extract returns fixed mentions."""
import json
import re
from types import SimpleNamespace

import openai


class _Completions:
    def __init__(self, owner):
        self.o = owner

    def create(self, **kw):
        o = self.o
        o.calls.append(kw)
        o.n += 1
        if o.fail_every and o.n % o.fail_every == 0:
            raise openai.APIConnectionError(request=SimpleNamespace(method="POST", url="https://bedrock.test"))
        user = kw["messages"][1]["content"]
        if "response_format" not in kw:  # the dev writer: plain text, no JSON schema
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content="Hola, " + " / ".join(re.findall(r"^- (.*)$", user, re.M))), finish_reason="stop")],
                usage=SimpleNamespace(prompt_tokens=80, completion_tokens=30))
        else:
            msg = re.search(r"<customer_message>\n(.*)\n</customer_message>", user, re.S).group(1)
            data = {"language_detected": "es", "english_gloss": f"EN: {msg}", "multi_intent": False,
                    "secondary_request_en": None,
                    "mentions": {"merchant": None, "amount": None, "currency": None, "date_from": None,
                                 "date_to": None, "type_hint": None, "channel_hint": None, "city": None} | o.mentions,
                    "customer_statement": {"original": msg, "en": f"EN: {msg}"}}
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data, ensure_ascii=False)),
                                     finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=80, completion_tokens=30))


class ScriptedLLM:
    def __init__(self, mentions: dict | None = None, fail_every: int = 0):
        self.mentions, self.fail_every, self.calls, self.n = mentions or {}, fail_every, [], 0
        self.chat = SimpleNamespace(completions=_Completions(self))
