"""Test doubles for OpenAI (Bedrock) and, from Task 10, Jev."""
import json
import re
from types import SimpleNamespace


class _FakeChatCompletions:
    def __init__(self, owner: "FakeLLM"):
        self.o = owner

    def create(self, **kw):
        self.o.calls.append(kw)
        schema = kw["response_format"]["json_schema"]["schema"]
        props = schema["properties"]
        user = kw["messages"][1]["content"] if len(kw["messages"]) > 1 else kw["messages"][0]["content"]
        if "english_gloss" in props:
            role = "extract"
        elif "reply_text" in props:
            role = "compose"
        else:
            role = "open_questions"
        self.o.roles.append(role)
        if role in self.o.fail:
            import openai
            raise openai.APIConnectionError(request=SimpleNamespace(method="POST", url="https://bedrock.test"))
        data = {"extract": self.o.extraction, "compose": self.o.composition,
                "open_questions": lambda u: {"questions": ["Which card was used?"]}}[role](user)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data, ensure_ascii=False)),
                                     finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        )


class FakeLLM:
    def __init__(self, language="es", multi_intent=False, secondary=None, mentions=None, fail=(), refuse=(),
                 reply_text=None):
        self.language, self.multi_intent, self.secondary = language, multi_intent, secondary
        self.mentions, self.fail, self.refuse, self.reply_text = mentions or {}, set(fail), set(refuse), reply_text
        self.calls, self.roles = [], []
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(self))

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


# ---- Jev test double (Task 10) ----

from bankagent.decisions.jev import JevError, JevResult, state_hash, validate_answers
from bankagent.decisions.understand import NOUL_QUESTIONS


def choice(label, labels, p=0.95, second=None, second_p=0.0):
    probs = {label: p}
    if second:
        probs[second] = second_p
    rest = [x for x in labels if x not in probs]
    left = max(0.0, 1.0 - sum(probs.values()))
    probs.update({x: left / len(rest) for x in rest})
    return {"type": "choice", "choice": label, "probabilities": probs, "confidence": p}


def noul(p):
    return {"type": "noul", "noul": p}


def understand_answers(questions, intent="account_info", ip=0.95, second=None, sp=0.0, target=None, tp=0.95,
                       reason="unclear", confirmation=None, cp=0.95, nouls=None):
    ans = {"intent": choice(intent, list(questions["intent"]["criteria"]), ip, second, sp)}
    crit = questions["target_transaction"]["criteria"]
    if target is None:
        label = "none_mentioned"
    elif target in crit:
        label = target
    else:  # match by a substring of the candidate description, e.g. "Netflix"
        label = next(a for a, d in crit.items() if target in d)
    ans["target_transaction"] = choice(label, list(crit), tp)
    ans["dispute_reason"] = choice(reason, list(questions["dispute_reason"]["criteria"]))
    for q in NOUL_QUESTIONS:
        ans[q] = noul((nouls or {}).get(q, 0.02))
    if "confirmation" in questions:
        ans["confirmation"] = choice(confirmation or "unclear", list(questions["confirmation"]["criteria"]),
                                     cp if confirmation else 0.6)
    return ans


class FakeJev:
    """Scripted Jev. One spec per 'understand' call ("fail" raises JevError).
    verify=True: all claims supported; False: none supported and promises flagged; "fail": JevError."""

    def __init__(self, specs, verify=True):
        self.specs, self.verify, self.calls = list(specs), verify, []

    def decide(self, state, questions):
        kind = "understand" if "intent" in questions else "verify"
        self.calls.append((kind, state, questions))
        if kind == "understand":
            spec = self.specs.pop(0)
            if spec == "fail":
                raise JevError("scripted failure")
            answers = understand_answers(questions, **spec)
        else:
            if self.verify == "fail":
                raise JevError("scripted verify failure")
            ok = self.verify is True
            answers = {q: noul((0.95 if ok else 0.1) if q.startswith("claim_supported") else (0.02 if ok else 0.9))
                       for q in questions}
        return JevResult(validate_answers(questions, {"answers": answers}), {"input_tokens": 50}, 1,
                         state_hash(state), "fake-jev")

    def count(self, kind):
        return sum(1 for c in self.calls if c[0] == kind)
