import json

import httpx
import pytest

from bankagent.decisions.jev import JevClient, JevError

Q = {
    "intent": {"type": "choice", "instructions": "x", "criteria": {"a": "A", "b": "B"}},
    "human": {"type": "noul", "instructions": "y"},
}
OK = {
    "model": "jev-1.13.0",
    "answers": {
        "intent": {"type": "choice", "choice": "a", "probabilities": {"a": 0.9, "b": 0.1}, "confidence": 0.8},
        "human": {"type": "noul", "noul": 0.2},
    },
    "usage": {"input_tokens": 10, "output_tokens": 0},
}


def client(handler):
    return JevClient("k", transport=httpx.MockTransport(handler))


def test_parses_typed_answers_and_sends_model_and_auth():
    seen = {}

    def h(req):
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=OK)

    r = client(h).decide({"m": "hola"}, Q)
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "jev-1.13.0" and seen["body"]["questions"] == Q
    assert r.answers["intent"].label == "a" and r.answers["intent"].p == 0.9
    assert abs(r.answers["intent"].margin - 0.8) < 1e-9
    assert r.answers["intent"].top(1) == ["a"]
    assert r.answers["human"].p == 0.2
    assert len(r.state_hash) == 16 and r.usage["input_tokens"] == 10


def test_missing_answer_is_error():
    body = {"answers": {"intent": OK["answers"]["intent"]}}
    with pytest.raises(JevError, match="missing answer: human"):
        client(lambda req: httpx.Response(200, json=body)).decide({}, Q)


def test_label_outside_criteria_is_error():
    body = json.loads(json.dumps(OK))
    body["answers"]["intent"]["choice"] = "zzz"
    with pytest.raises(JevError, match="invalid choice answer"):
        client(lambda req: httpx.Response(200, json=body)).decide({}, Q)


def test_noul_out_of_range_is_error():
    body = json.loads(json.dumps(OK))
    body["answers"]["human"]["noul"] = 1.5
    with pytest.raises(JevError, match="invalid noul answer"):
        client(lambda req: httpx.Response(200, json=body)).decide({}, Q)


def test_retries_once_on_5xx_then_succeeds():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=OK)

    assert client(h).decide({}, Q).answers["intent"].label == "a"
    assert len(calls) == 2


def test_two_5xx_fail_after_one_retry():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(JevError, match="server error 503"):
        client(h).decide({}, Q)
    assert len(calls) == 2


def test_4xx_is_not_retried():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(401, text="bad key")

    with pytest.raises(JevError, match="http 401"):
        client(h).decide({}, Q)
    assert len(calls) == 1


def test_timeout_is_retried_once():
    calls = []

    def h(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(200, json=OK)

    assert client(h).decide({}, Q).answers["human"].p == 0.2
    assert len(calls) == 2


def test_empty_key_builds_but_decide_raises_jev_error():
    with pytest.raises(JevError, match="empty"):
        JevClient("").decide({}, Q)
