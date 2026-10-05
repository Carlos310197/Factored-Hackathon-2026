import time

import jwt
import pytest
import yaml
from fastapi.testclient import TestClient

from bankagent.auth.tokens import generate_keypair, jwks_from_public, verify_token
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
         "customer_id": "CLI-FIXC00000001", "lang": "es", "demo_password": "demo-ana",
         "scenarios": ["dispute_filed"], "short_ttl_allowed": True},
        {"username": "rui.pt", "password_sha256": hash_password("demo-rui"), "otp": "111111",
         "customer_id": "CLI-FIXC00000002", "lang": "pt"},
        {"username": "agent.ana", "password_sha256": hash_password("staff-ana"), "role": "agent",
         "display_name": "Ana R."},
    ]}))
    return load_users(p)


def client(users, demo_mode=False):
    return TestClient(create_app(users, PRIV, PUB, KID, ISS, AUD, demo_mode=demo_mode))


def customer_token(api, username="ana.mx", password="demo-ana", otp="123456", short_ttl=False):
    t = api.post("/auth/login", json={"username": username, "password": password}).json()["login_ticket"]
    return api.post("/auth/otp", json={"login_ticket": t, "otp": otp, "short_ttl": short_ttl})


def claims(token, aud):
    return jwt.decode(token, PUB, algorithms=["RS256"], audience=aud, issuer=ISS)


def test_customer_token_has_customer_role_and_still_verifies_for_agent(users):
    tok = customer_token(client(users)).json()["access_token"]
    assert claims(tok, AUD)["role"] == "customer"
    assert verify_token(tok, JWKS, ISS, AUD).customer_id == "CLI-FIXC00000001"


def test_short_ttl_only_for_allowed_users(users):
    api = client(users)
    short = customer_token(api, short_ttl=True).json()
    assert short["expires_in"] == 30
    normal = customer_token(api, "rui.pt", "demo-rui", "111111", short_ttl=True).json()
    assert normal["expires_in"] == 900


def test_staff_cannot_use_customer_login(users):
    api = client(users)
    t = api.post("/auth/login", json={"username": "agent.ana", "password": "staff-ana"}).json()["login_ticket"]
    assert api.post("/auth/otp", json={"login_ticket": t, "otp": ""}).status_code == 401


def test_staff_login_issues_staff_audience_token_rejected_by_agent_verifier(users):
    r = client(users).post("/auth/staff/login", json={"username": "agent.ana", "password": "staff-ana"})
    assert r.status_code == 200 and r.json()["name"] == "Ana R."
    c = claims(r.json()["access_token"], "bankagent-staff")
    assert c["role"] == "agent" and c["scope"] == "handoff:work" and c["sid"].startswith("STAFF-")
    with pytest.raises(Exception):
        verify_token(r.json()["access_token"], JWKS, ISS, AUD)


def test_customer_cannot_use_staff_login(users):
    r = client(users).post("/auth/staff/login", json={"username": "ana.mx", "password": "demo-ana"})
    assert r.status_code == 401


def test_realtime_token_for_customer_is_bound_to_sid_and_never_outlives_source(users):
    api = client(users)
    src = customer_token(api, short_ttl=True).json()["access_token"]
    r = api.post("/auth/realtime-token", headers={"Authorization": f"Bearer {src}"})
    assert r.status_code == 200
    c, s = claims(r.json()["token"], "realtime"), claims(src, AUD)
    assert c["role"] == "customer" and c["sid"] == s["sid"] and c["scope"] == "realtime:subscribe"
    assert c["exp"] <= s["exp"]


def test_realtime_token_for_agent(users):
    api = client(users)
    staff = api.post("/auth/staff/login", json={"username": "agent.ana", "password": "staff-ana"}).json()
    r = api.post("/auth/realtime-token", headers={"Authorization": f"Bearer {staff['access_token']}"})
    assert claims(r.json()["token"], "realtime")["role"] == "agent"


def test_realtime_token_rejects_missing_or_bad_token(users):
    api = client(users)
    assert api.post("/auth/realtime-token").status_code == 401
    assert api.post("/auth/realtime-token", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_demo_users_only_in_demo_mode(users):
    assert client(users).get("/auth/demo-users").status_code == 404
    listed = client(users, demo_mode=True).get("/auth/demo-users").json()
    ana = next(u for u in listed if u["username"] == "ana.mx")
    assert ana["demo_password"] == "demo-ana" and ana["otp"] == "123456" and ana["scenarios"] == ["dispute_filed"]
    assert all("password_sha256" not in u for u in listed)
    assert all(u["role"] == "customer" for u in listed)  # staff credentials are never published
    assert "agent.ana" not in {u["username"] for u in listed}
