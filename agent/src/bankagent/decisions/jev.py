"""Jev (TypeSafe) decision client: typed answers, one bounded retry, strict response validation.
A missing or malformed answer is an error, never an approval."""
import hashlib
import json
import time
from dataclasses import dataclass

import httpx


class JevError(Exception):
    """Transport, protocol or validation failure. Callers treat it as 'uncertain', never as a decision."""


@dataclass(frozen=True)
class ChoiceAnswer:
    label: str
    probabilities: dict[str, float]
    confidence: float | None = None

    @property
    def p(self) -> float:
        return self.probabilities.get(self.label, 0.0)

    @property
    def margin(self) -> float:
        ranked = sorted(self.probabilities.values(), reverse=True)
        return ranked[0] - (ranked[1] if len(ranked) > 1 else 0.0)

    def top(self, n: int, exclude: frozenset[str] | set[str] = frozenset()) -> list[str]:
        ranked = sorted(self.probabilities.items(), key=lambda kv: -kv[1])
        return [k for k, _ in ranked if k not in exclude][:n]


@dataclass(frozen=True)
class NoulAnswer:
    p: float


@dataclass(frozen=True)
class JevResult:
    answers: dict[str, ChoiceAnswer | NoulAnswer]
    usage: dict
    latency_ms: int
    state_hash: str
    model: str


def state_hash(state) -> str:
    raw = json.dumps(state, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def validate_answers(questions: dict, body: dict) -> dict[str, ChoiceAnswer | NoulAnswer]:
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise JevError("response has no answers object")
    out: dict[str, ChoiceAnswer | NoulAnswer] = {}
    for qid, q in questions.items():
        a = answers.get(qid)
        if not isinstance(a, dict):
            raise JevError(f"missing answer: {qid}")
        if a.get("type") != q["type"]:
            raise JevError(f"type mismatch for {qid}: {a.get('type')}")
        if q["type"] == "choice":
            labels = set(q["criteria"])
            probs = a.get("probabilities") or {}
            if a.get("choice") not in labels or not probs or not set(probs) <= labels:
                raise JevError(f"invalid choice answer for {qid}")
            if any(not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0 for v in probs.values()):
                raise JevError(f"probability out of range for {qid}")
            out[qid] = ChoiceAnswer(a["choice"], {k: float(v) for k, v in probs.items()}, a.get("confidence"))
        elif q["type"] == "noul":
            v = a.get("noul")
            if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
                raise JevError(f"invalid noul answer for {qid}")
            out[qid] = NoulAnswer(float(v))
        else:
            raise JevError(f"unsupported question type {q['type']}")
    return out


class JevClient:
    def __init__(self, api_key: str, url: str = "https://api.typesafe.ai/v1/systemone", model: str = "jev-1.13.0",
                 timeout: float = 3.0, transport: httpx.BaseTransport | None = None):
        self.api_key = api_key  # empty (secret unreadable): built anyway, decide() raises JevError so the graph clarifies
        self.url, self.model = url, model
        self._http = httpx.Client(timeout=timeout, transport=transport,
                                  headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})

    def decide(self, state, questions: dict) -> JevResult:
        if not self.api_key:
            raise JevError("JEV_API_KEY is empty")
        payload = {"model": self.model, "state": state, "questions": questions}
        start = time.monotonic()
        body = self._post_with_one_retry(payload)
        answers = validate_answers(questions, body)
        return JevResult(answers, body.get("usage") or {}, int((time.monotonic() - start) * 1000),
                         state_hash(state), body.get("model", self.model))

    def _post_with_one_retry(self, payload: dict) -> dict:
        last: JevError | None = None
        for _ in range(2):
            try:
                r = self._http.post(self.url, json=payload)
            except httpx.TimeoutException as e:
                last = JevError(f"timeout: {e}")
                continue
            except httpx.HTTPError as e:
                raise JevError(f"transport error: {e}") from e
            if r.status_code >= 500:
                last = JevError(f"server error {r.status_code}")
                continue
            if r.status_code != 200:
                raise JevError(f"http {r.status_code}: {r.text[:200]}")
            try:
                return r.json()
            except ValueError as e:
                raise JevError("response is not JSON") from e
        raise last
