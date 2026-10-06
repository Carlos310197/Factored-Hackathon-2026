import time
from types import SimpleNamespace

import boto3
import pytest
from moto import mock_aws
from starlette.testclient import TestClient

import bankagent.app as entry
from bankagent.auth.tokens import generate_keypair, issue_token, jwks_from_public
from bankagent.context import SCOPE_DISPUTE, SCOPE_READ
from bankagent.runtime import build_runtime
from bankagent.settings import Settings
from bankagent.store.tables import create_tables
from tests.ui_fakes import FakeService as UiFakeService
from tests.fixtures.serving_fixture import C1, C2

ISS, AUD = "http://idp.test", "bankagent"
PRIV, PUB = generate_keypair()
JWKS = jwks_from_public(PUB, "k1")


def make_rt(jwks_get=lambda: JWKS):
    return SimpleNamespace(settings=SimpleNamespace(issuer=ISS, audience=AUD), jwks=SimpleNamespace(get=jwks_get),
                           service=UiFakeService())


def tok(lang="es", now=None):
    return issue_token(PRIV, "k1", ISS, AUD, C1, "S-1", {SCOPE_READ, SCOPE_DISPUTE}, lang, now=now)


def test_no_token_asks_to_log_in():
    rt = make_rt()
    r = entry.handle({"message": "hola"}, {}, rt)
    assert r["error"] == "auth_required" and "inicies sesión" in r["reply_text"] and rt.service.calls == []


def test_bearer_header_any_case():
    rt = make_rt()
    assert entry.handle({"message": "hola"}, {"authorization": f"Bearer {tok()}"}, rt)["reply_text"] == "ok"
    assert all(ctx.customer_id == C1 for ctx, _, _ in rt.service.calls)


def test_expired_token_reports_session_expired_in_requested_language():
    rt = make_rt()
    r = entry.handle({"message": "oi", "lang": "pt"}, {"Authorization": f"Bearer {tok(now=time.time() - 2000)}"}, rt)
    assert r["error"] == "session_expired" and "sessão" in r["reply_text"] and rt.service.calls == []


def test_tampered_token_rejected():
    rt = make_rt()
    bad = tok()[:-4] + "AAAA"
    assert entry.handle({"message": "hola"}, {"Authorization": f"Bearer {bad}"}, rt)["error"] == "auth_required"


@pytest.mark.parametrize("message", ["", "   ", 123, None, "x" * 2001])
def test_invalid_messages_rejected_without_service_call(message):
    rt = make_rt()
    r = entry.handle({"message": message}, {"Authorization": f"Bearer {tok()}"}, rt)
    assert r["error"] == "invalid_message" and rt.service.calls == []


def test_payload_customer_id_is_ignored():
    rt = make_rt()
    entry.handle({"message": "saldo", "customer_id": C2}, {"Authorization": f"Bearer {tok()}"}, rt)
    assert rt.service.calls[0][0].customer_id == C1


def test_identity_outage_is_reported_not_raised():
    def down():
        raise RuntimeError("jwks unreachable")

    r = entry.handle({"message": "hola"}, {"Authorization": f"Bearer {tok()}"}, make_rt(down))
    assert r["error"] == "identity_unavailable"


def test_http_contract_ping_and_invocations(monkeypatch):
    rt = make_rt()
    monkeypatch.setattr(entry, "_runtime", rt)
    client = TestClient(entry.app)
    assert client.get("/ping").json()["status"] == "Healthy"
    body = client.post("/invocations", json={"message": "hola"}, headers={"Authorization": f"Bearer {tok()}"}).json()
    assert body["reply_text"] == "ok" and rt.service.calls[0][0].customer_id == C1


def test_build_runtime_wires_real_components(serving_root, monkeypatch):
    with mock_aws():
        create_tables(boto3.client("dynamodb", region_name="us-east-2"), "t")
        settings = Settings.from_env({"SERVING_URI": str(serving_root), "JEV_API_KEY": "test-key", "TABLE_PREFIX": "t",
                                      "IDP_JWKS_URL": "http://idp.test/jwks.json"})
        rt = build_runtime(settings)
        assert rt.jwks.url == "http://idp.test/jwks.json" and rt.service.graph is not None
        assert rt.service.deps.models["compose"].model == "openai.gpt-oss-120b"


class _WarmRead:
    def __init__(self):
        self.calls = []
        self.serving = SimpleNamespace(pointer=lambda: SimpleNamespace(run_id="R1", max_process_date="2026-06-17"))

    def get_accounts(self, ctx, run_id, as_of):
        self.calls.append((ctx.customer_id, run_id, str(as_of)))


def _warm_rt(jwks_get=lambda: JWKS):
    rt = make_rt(jwks_get)
    rt.service.deps.read = _WarmRead()
    return rt


def test_warmup_reads_the_callers_own_data_and_runs_no_turn():
    rt = _warm_rt()
    r = entry.handle({"warmup": True}, {"Authorization": f"Bearer {tok()}"}, rt)
    assert r == {"warm": True}
    assert rt.service.deps.read.calls == [(C1, "R1", "2026-06-17")]
    assert rt.service.calls == [] and rt.service.deps.store.sessions.items == {}


def test_warmup_needs_a_valid_token_and_never_raises():
    rt = _warm_rt()
    assert entry.handle({"warmup": True}, {}, rt)["error"] == "auth_required"

    def down():
        raise RuntimeError("jwks unreachable")
    assert entry.handle({"warmup": True}, {"Authorization": f"Bearer {tok()}"}, _warm_rt(down))["warm"] is False
    broken = _warm_rt()
    broken.service.deps.read.serving = SimpleNamespace(pointer=lambda: (_ for _ in ()).throw(RuntimeError("s3")))
    assert entry.handle({"warmup": True}, {"Authorization": f"Bearer {tok()}"}, broken) == {"warm": False}
    assert rt.service.deps.read.calls == []


def test_runtime_is_built_once_under_concurrent_first_calls(monkeypatch):
    import threading
    built = []

    def slow_build(_settings):
        built.append(1)
        time.sleep(0.05)
        return "rt"
    monkeypatch.setattr(entry, "_runtime", None)
    monkeypatch.setattr("bankagent.runtime.build_runtime", slow_build)
    monkeypatch.setattr(entry, "load_settings", lambda: None)
    threads = [threading.Thread(target=entry.runtime) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert built == [1] and entry._runtime == "rt"


def test_each_turn_logs_one_plain_duration_line_for_the_latency_metric():
    import logging
    import re
    seen = []
    handler = logging.Handler()
    handler.emit = seen.append
    entry.metrics.addHandler(handler)
    try:
        entry.handle({"message": "saldo"}, {"Authorization": f"Bearer {tok()}"}, make_rt())
        entry.handle({"message": ""}, {"Authorization": f"Bearer {tok()}"}, make_rt())  # rejected: no turn, no line
    finally:
        entry.metrics.removeHandler(handler)
    turns = [r for r in seen if r.getMessage().startswith("turn_end")]
    assert [r.levelno for r in turns] == [logging.INFO]
    assert re.fullmatch(r"turn_end \d+", turns[0].getMessage())


def _request_lines(*calls):
    import logging
    seen = []
    handler = logging.Handler()
    handler.emit = seen.append
    entry.metrics.addHandler(handler)
    try:
        for payload, headers, rt in calls:
            entry.handle(payload, headers, rt)
    finally:
        entry.metrics.removeHandler(handler)
    return [r.getMessage() for r in seen if r.getMessage().startswith("request ")]


def test_every_request_logs_one_outcome_line_even_without_a_turn():
    auth = {"Authorization": f"Bearer {tok()}"}
    lines = _request_lines(
        ({"message": "hola"}, {}, make_rt()),
        ({"message": "hola"}, {"Authorization": f"Bearer {tok(now=time.time() - 2000)}"}, make_rt()),
        ({"message": ""}, auth, make_rt()),
        ({"message": "saldo", "client_message_id": "cm-12345678"}, auth, make_rt()),
        ({"warmup": True}, auth, _warm_rt()),
    )
    assert lines == ["request auth_required - -", "request session_expired - -", "request invalid_message S-1 -",
                     "request turn S-1 cm-12345678", "request warmup_ok S-1 -"]


def test_a_retried_message_logs_duplicate_not_a_second_turn():
    rt, auth = make_rt(), {"Authorization": f"Bearer {tok()}"}
    msg = {"message": "saldo", "client_message_id": "cm-12345678"}
    assert _request_lines((msg, auth, rt), (msg, auth, rt)) == ["request turn S-1 cm-12345678",
                                                                "request duplicate S-1 cm-12345678"]
