"""RS256 session tokens: issued by the mock IdP, verified by the agent. customer_id comes only from here."""
import time

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from bankagent.context import SessionContext


class AuthError(Exception):
    pass


def generate_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
    public_pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return private_pem, public_pem


def jwks_from_public(public_pem: str, kid: str) -> dict:
    pub = serialization.load_pem_public_key(public_pem.encode())
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(pub, as_dict=True)
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def issue_token(private_pem: str, kid: str, issuer: str, audience: str, customer_id: str, session_id: str,
                scopes, lang: str, ttl_s: int = 900, now: float | None = None, extra: dict | None = None) -> str:
    iat = int(now if now is not None else time.time())
    claims = {"iss": issuer, "aud": audience, "client_id": audience, "sub": customer_id, "sid": session_id,
              "scope": " ".join(sorted(scopes)), "lang": lang, "iat": iat, "exp": iat + ttl_s}
    claims.update(extra or {})
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})


def verify_token(token: str, jwks: dict, issuer: str, audience: str) -> SessionContext:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        jwk = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if jwk is None:
            raise AuthError("unknown signing key")
        claims = jwt.decode(token, jwt.PyJWK(jwk).key, algorithms=["RS256"], audience=audience, issuer=issuer,
                            options={"require": ["exp", "iat", "sub", "sid", "iss", "aud"]})
    except AuthError:
        raise
    except jwt.ExpiredSignatureError as e:
        raise AuthError("expired") from e
    except jwt.PyJWTError as e:
        raise AuthError(f"invalid token: {e}") from e
    lang = claims.get("lang") if claims.get("lang") in ("es", "pt") else "es"
    return SessionContext(customer_id=claims["sub"], session_id=claims["sid"],
                          scopes=frozenset(claims.get("scope", "").split()), lang=lang, expires_at=int(claims["exp"]))


class JwksCache:
    """Fetches the IdP's JWKS and caches it; refetches after ttl_s."""

    def __init__(self, url: str, ttl_s: int = 600, fetch=None):
        self.url, self.ttl_s = url, ttl_s
        self._fetch = fetch or (lambda u: httpx.get(u, timeout=3.0).raise_for_status().json())
        self._value: dict | None = None
        self._at = 0.0

    def get(self) -> dict:
        if self._value is None or time.time() - self._at > self.ttl_s:
            self._value, self._at = self._fetch(self.url), time.time()
        return self._value
