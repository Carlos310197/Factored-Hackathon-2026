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
from tests.fixtures.serving_fixture import C1, C2

ISS, AUD = "http://idp.test", "bankagent"
PRIV, PUB = generate_keypair()
JWKS = jwks_from_public(PUB, "k1")


class FakeService:
    def __init__(self):
        self.calls = []

    def handle_turn(self, ctx, message):
        self.calls.append((ctx, message))
        return {"reply_text": "ok", "language": ctx.lang, "awaiting": "none", "options": [], "refs": [],
                "data_as_of": "2026-06-17"}


def make_rt(jwks_get=lambda: JWKS):
    return SimpleNamespace(settings=SimpleNamespace(issuer=ISS, audience=AUD), jwks=SimpleNamespace(get=jwks_get),
                           service=FakeService())


def tok(lang="es", now=None):
    return issue_token(PRIV, "k1", ISS, AUD, C1, "S-1", {SCOPE_READ, SCOPE_DISPUTE}, lang, now=now)


def test_no_token_asks_to_log_in():
    rt = make_rt()
    r = entry.handle({"message": "hola"}, {}, rt)
    assert r["error"] == "auth_required" and "inicies sesión" in r["reply_text"] and rt.service.calls == []


def test_bearer_header_any_case_and_payload_fallback():
    rt = make_rt()
    assert entry.handle({"message": "hola"}, {"authorization": f"Bearer {tok()}"}, rt)["reply_text"] == "ok"
    assert entry.handle({"message": "hola", "session_token": tok()}, {}, rt)["reply_text"] == "ok"
    assert all(ctx.customer_id == C1 for ctx, _ in rt.service.calls)


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
