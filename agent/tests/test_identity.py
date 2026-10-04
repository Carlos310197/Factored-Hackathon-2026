import time

import pytest
import yaml
from fastapi.testclient import TestClient

from bankagent.auth.tokens import AuthError, generate_keypair, issue_token, jwks_from_public, verify_token
from bankagent.context import SCOPE_DISPUTE, SCOPE_READ
from bankagent.identity.app import create_app
from bankagent.identity.users import hash_password, load_users

ISS, AUD, KID = "http://idp.test", "bankagent", "k1"
PRIV, PUB = generate_keypair()
JWKS = jwks_from_public(PUB, KID)


@pytest.fixture
def users(tmp_path):
    p = tmp_path / "users.yaml"
    p.write_text(yaml.safe_dump({"users": [
        {"username": "ana.mx", "password_sha256": hash_password("demo-ana"), "otp": "123456",
         "customer_id": "CLI-FIXC00000001", "lang": "es"},
        {"username": "joao.pt", "password_sha256": hash_password("demo-joao"), "otp": "654321",
         "customer_id": "CLI-FIXC00000002", "lang": "pt"},
    ]}))
    return load_users(p)


@pytest.fixture
def api(users):
    return TestClient(create_app(users, PRIV, PUB, KID, ISS, AUD))


def login(api, username="ana.mx", password="demo-ana", otp="123456"):
    r = api.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return api.post("/auth/otp", json={"login_ticket": r.json()["login_ticket"], "otp": otp})


def test_full_login_issues_token_verifiable_with_published_jwks(api):
    r = login(api)
    assert r.status_code == 200 and r.json()["token_type"] == "Bearer" and r.json()["expires_in"] == 900
    jwks = api.get("/jwks.json").json()
    ctx = verify_token(r.json()["access_token"], jwks, ISS, AUD)
    assert ctx.customer_id == "CLI-FIXC00000001" and ctx.lang == "es"
    assert ctx.scopes == frozenset({SCOPE_READ, SCOPE_DISPUTE}) and ctx.session_id.startswith("S-")


def test_portuguese_user_gets_pt_session(api):
    ctx = verify_token(login(api, "joao.pt", "demo-joao", "654321").json()["access_token"], JWKS, ISS, AUD)
    assert ctx.lang == "pt"


def test_wrong_password_is_401(api):
    assert api.post("/auth/login", json={"username": "ana.mx", "password": "nope"}).status_code == 401


def test_unknown_user_is_401(api):
    assert api.post("/auth/login", json={"username": "ghost", "password": "x"}).status_code == 401


def test_wrong_otp_is_401_and_ticket_is_single_use(api):
    t = api.post("/auth/login", json={"username": "ana.mx", "password": "demo-ana"}).json()["login_ticket"]
    assert api.post("/auth/otp", json={"login_ticket": t, "otp": "000000"}).status_code == 401
    assert api.post("/auth/otp", json={"login_ticket": t, "otp": "123456"}).status_code == 401


def test_discovery_document_points_to_jwks(api):
    d = api.get("/.well-known/openid-configuration").json()
    assert d["issuer"] == ISS and d["jwks_uri"] == f"{ISS}/jwks.json"
    assert d["id_token_signing_alg_values_supported"] == ["RS256"]


def test_expired_token_rejected():
    tok = issue_token(PRIV, KID, ISS, AUD, "CLI-X", "S-1", {SCOPE_READ}, "es", ttl_s=900, now=time.time() - 1000)
    with pytest.raises(AuthError, match="expired"):
        verify_token(tok, JWKS, ISS, AUD)


def test_tampered_token_rejected():
    tok = issue_token(PRIV, KID, ISS, AUD, "CLI-X", "S-1", {SCOPE_READ}, "es")
    head, payload, sig = tok.split(".")
    tampered = f"{head}.{payload[:-2]}{'A' if payload[-2] != 'A' else 'B'}{payload[-1]}.{sig}"
    with pytest.raises(AuthError):
        verify_token(tampered, JWKS, ISS, AUD)


def test_wrong_audience_and_issuer_rejected():
    tok = issue_token(PRIV, KID, ISS, "other-aud", "CLI-X", "S-1", {SCOPE_READ}, "es")
    with pytest.raises(AuthError):
        verify_token(tok, JWKS, ISS, AUD)
    tok = issue_token(PRIV, KID, "http://evil", AUD, "CLI-X", "S-1", {SCOPE_READ}, "es")
    with pytest.raises(AuthError):
        verify_token(tok, JWKS, ISS, AUD)


def test_unknown_kid_rejected():
    other_priv, _ = generate_keypair()
    tok = issue_token(other_priv, "k2", ISS, AUD, "CLI-X", "S-1", {SCOPE_READ}, "es")
    with pytest.raises(AuthError, match="unknown signing key"):
        verify_token(tok, JWKS, ISS, AUD)


def test_unsupported_lang_claim_defaults_to_es():
    tok = issue_token(PRIV, KID, ISS, AUD, "CLI-X", "S-1", {SCOPE_READ}, "fr")
    assert verify_token(tok, JWKS, ISS, AUD).lang == "es"
