"""Mock OIDC identity service. Issues RS256 JWTs for demo users."""
import secrets
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from bankagent.auth.tokens import generate_keypair, issue_token, jwks_from_public
from bankagent.identity.users import DemoUser, hash_password


class LoginRequest(BaseModel):
    username: str
    password: str


class OtpRequest(BaseModel):
    login_ticket: str
    otp: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    lang: str


def create_app(users: dict[str, DemoUser], private_pem: str, public_pem: str, kid: str, issuer: str, audience: str,
               scopes: tuple[str, ...] = ("inquiry:read", "dispute:create"), ttl_s: int = 900, clock=time.time) -> FastAPI:
    """Create the FastAPI identity service app."""
    app = FastAPI(title="Mock OIDC Identity Service")

    # Store login tickets: ticket -> username
    tickets: dict[str, str] = {}

    @app.post("/auth/login")
    def login(req: LoginRequest) -> dict:
        user = users.get(req.username)
        if not user or user.password_sha256 != hash_password(req.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

        ticket = secrets.token_urlsafe(32)
        tickets[ticket] = user.username
        return {"login_ticket": ticket}

    @app.post("/auth/otp", response_model=TokenResponse)
    def otp(req: OtpRequest) -> TokenResponse:
        username = tickets.pop(req.login_ticket, None)
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired ticket")

        user = users[username]
        if user.otp != req.otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid otp")

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
            ttl_s=ttl_s,
            now=clock()
        )

        return TokenResponse(access_token=token, token_type="Bearer", expires_in=ttl_s, lang=user.lang)

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


if __name__ == "__main__":
    import uvicorn
    from bankagent.settings import Settings

    settings = Settings.from_env()
    private_pem, public_pem = generate_keypair()
    users = {}  # In production, load from config file

    app = create_app(
        users=users,
        private_pem=private_pem,
        public_pem=public_pem,
        kid=settings.issuer.split("/")[-1] if "/" in settings.issuer else "default",
        issuer=settings.issuer,
        audience=settings.audience
    )

    uvicorn.run(app, host="0.0.0.0", port=8081)
