"""Container contract for `docker compose up` (dynamodb + init-tables + identity + agent).
None of these requests reaches Jev or Bedrock: they stop at auth and message validation."""
import httpx
import pytest

pytestmark = pytest.mark.container
AGENT, IDP = "http://localhost:8080", "http://localhost:8081"


def test_ping_is_healthy():
    assert httpx.get(f"{AGENT}/ping").json()["status"] == "Healthy"


def test_invocation_without_token_asks_to_log_in():
    r = httpx.post(f"{AGENT}/invocations", json={"message": "hola"}, timeout=30).json()
    assert r["error"] == "auth_required"


def test_identity_publishes_discovery_and_jwks():
    d = httpx.get(f"{IDP}/.well-known/openid-configuration").json()
    assert d["issuer"] == "http://identity:8081" and d["jwks_uri"].endswith("/jwks.json")
    assert httpx.get(f"{IDP}/jwks.json").json()["keys"][0]["alg"] == "RS256"


def test_valid_token_with_empty_message_is_rejected_before_any_model_call():
    t = httpx.post(f"{IDP}/auth/login", json={"username": "demo01", "password": "demo-01"}).json()["login_ticket"]
    tok = httpx.post(f"{IDP}/auth/otp", json={"login_ticket": t, "otp": "123456"}).json()["access_token"]
    r = httpx.post(f"{AGENT}/invocations", json={"message": "  "}, headers={"Authorization": f"Bearer {tok}"},
                   timeout=30).json()
    assert r["error"] == "invalid_message"
