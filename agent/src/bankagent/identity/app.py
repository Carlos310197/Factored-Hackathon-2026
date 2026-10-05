"""Mock OIDC identity service. Issues RS256 JWTs for demo users."""
import os
import secrets
import time

import jwt
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from bankagent.auth.tokens import generate_keypair, issue_token, jwks_from_public
from bankagent.identity.users import DemoUser, hash_password, load_users


class LoginRequest(BaseModel):
    username: str
    password: str


class OtpRequest(BaseModel):
    login_ticket: str
    otp: str
    short_ttl: bool = False


SHORT_TTL_S = 30
TICKET_AUDIENCE = "login-ticket"
TICKET_TTL_S = 300
STAFF_SCOPE = "handoff:work"
REALTIME_SCOPE = "realtime:subscribe"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    lang: str


def create_app(users: dict[str, DemoUser], private_pem: str, public_pem: str, kid: str, issuer: str, audience: str,
               scopes: tuple[str, ...] = ("inquiry:read", "dispute:create"), ttl_s: int = 900, clock=time.time,
               staff_audience: str = "bankagent-staff", realtime_audience: str = "realtime",
               demo_mode: bool = False) -> FastAPI:
    """Create the FastAPI identity service app."""
    app = FastAPI(title="Mock OIDC Identity Service")

    # Login tickets are short-lived signed tokens, so login and OTP can land on different Lambda containers. A ticket's
    # audience is TICKET_AUDIENCE, never accepted as an access token. Single use is per container (spent set): across
    # containers a ticket can be retried until it expires (TICKET_TTL_S).
    spent: set[str] = set()

    @app.post("/auth/login")
    def login(req: LoginRequest) -> dict:
        user = users.get(req.username)
        if not user or user.password_sha256 != hash_password(req.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

        now = int(clock())
        ticket = jwt.encode({"iss": issuer, "aud": TICKET_AUDIENCE, "sub": user.username, "iat": now,
                             "exp": now + TICKET_TTL_S, "jti": secrets.token_urlsafe(8)},
                            private_pem, algorithm="RS256", headers={"kid": kid})
        return {"login_ticket": ticket}

    @app.post("/auth/otp", response_model=TokenResponse)
    def otp(req: OtpRequest) -> TokenResponse:
        username = None
        if req.login_ticket not in spent:
            spent.add(req.login_ticket)
            try:  # expiry is checked against the injected clock, not wall time
                claims = jwt.decode(req.login_ticket, public_pem, algorithms=["RS256"], audience=TICKET_AUDIENCE,
                                    issuer=issuer, options={"verify_exp": False})
                if int(claims["exp"]) > clock():
                    username = claims["sub"]
            except jwt.PyJWTError:
                pass
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired ticket")

        user = users[username]
        if user.role != "customer" or not user.otp or user.otp != req.otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid otp")
        ttl = SHORT_TTL_S if req.short_ttl and user.short_ttl_allowed else ttl_s

        session_id = "S-" + secrets.token_hex(8)
        token = issue_token(
            private_pem=private_pem,
            kid=kid,
            issuer=issuer,
            audience=audience,
            customer_id=user.customer_id,
            session_id=session_id,
            scopes=list(scopes),
            lang=user.lang,
            ttl_s=ttl,
            now=clock(),
            extra={"role": "customer"},
        )

        return TokenResponse(access_token=token, token_type="Bearer", expires_in=ttl, lang=user.lang)

    @app.post("/auth/staff/login")
    def staff_login(req: LoginRequest) -> dict:
        user = users.get(req.username)
        if not user or user.role != "agent" or user.password_sha256 != hash_password(req.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
        name = user.display_name or user.username
        token = issue_token(private_pem, kid, issuer, staff_audience, user.username,
                            "STAFF-" + secrets.token_hex(8), [STAFF_SCOPE], "es", ttl_s, now=clock(),
                            extra={"role": "agent", "name": name})
        return {"access_token": token, "token_type": "Bearer", "expires_in": ttl_s, "name": name}

    @app.post("/auth/realtime-token")
    def realtime_token(authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bearer token required")
        try:
            src = jwt.decode(authorization[7:].strip(), public_pem, algorithms=["RS256"], issuer=issuer,
                             audience=[audience, staff_audience])
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from e
        now = int(clock())
        ttl = max(1, min(900, int(src["exp"]) - now))
        token = issue_token(private_pem, kid, issuer, realtime_audience, src["sub"], src["sid"], [REALTIME_SCOPE],
                            src.get("lang", "es"), ttl, now=now, extra={"role": src.get("role", "customer")})
        return {"token": token, "expires_in": ttl}

    @app.get("/auth/demo-users")
    def demo_users() -> list[dict]:
        if not demo_mode:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        return [{"username": u.username, "demo_password": u.demo_password, "otp": u.otp, "lang": u.lang,
                 "role": u.role, "display_name": u.display_name, "scenarios": list(u.scenarios)}
                for u in users.values() if u.role == "customer"]  # staff credentials are never published

    @app.get("/.well-known/openid-configuration")
    def openid_configuration() -> dict:
        return {
            "issuer": issuer,
            "jwks_uri": f"{issuer}/jwks.json",
            "response_types_supported": ["id_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"]
        }

    @app.get("/jwks.json")
    def jwks() -> dict:
        return jwks_from_public(public_pem, kid)

    return app


def create_app_from_env(env=None) -> FastAPI:
    """Build the IdP from the environment: DEMO_USERS (the labeled test identities file), IDP_ISSUER,
    IDP_AUDIENCE and IDP_KID. This is what `python -m bankagent.identity.app` (the container) runs."""
    e = os.environ if env is None else env
    private_pem, public_pem = generate_keypair()
    return create_app(users=load_users(e.get("DEMO_USERS", "config/demo_users.yaml")),
                      private_pem=private_pem,
                      public_pem=public_pem,
                      kid=e.get("IDP_KID", "idp-local"),
                      issuer=e.get("IDP_ISSUER", "http://localhost:8081"),
                      audience=e.get("IDP_AUDIENCE", "bankagent"),
                      demo_mode=e.get("IDP_DEMO_MODE") == "1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app_from_env(), host="0.0.0.0", port=8081)
