# 14 · Session Tokens and the Mock OIDC Identity Service

**Subsystem:** Agent core · **Depends on:** 12 · **Reference:** agent-core plan, Task 3

## Goal

Issue and verify RS256 session JWTs, and serve a mock OIDC IdP (login → OTP → token, discovery, JWKS) for labeled test identities.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `context/architecture-context.md` → Agent Core → Components (`identity/`) and One turn (step 1)

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/auth/__init__.py`, `agent/src/bankagent/auth/tokens.py`, `agent/src/bankagent/identity/__init__.py`, `agent/src/bankagent/identity/users.py`, `agent/src/bankagent/identity/app.py`, `agent/tests/test_identity.py`

### Interfaces

- Consumes: `SessionContext`, scopes (Task 1).
- Produces:
  - `generate_keypair() -> tuple[str, str]` (private PEM, public PEM);
  - `jwks_from_public(public_pem, kid) -> dict`;
  - `issue_token(private_pem, kid, issuer, audience, customer_id, session_id, scopes, lang, ttl_s=900, now=None) -> str`;
  - `verify_token(token, jwks, issuer, audience) -> SessionContext` (raises `AuthError`; the message is `"expired"` for an expired token);
  - `JwksCache(url, ttl_s=600, fetch=None)` with `.get() -> dict`;
  - `DemoUser`, `load_users(path) -> dict[str, DemoUser]`, `hash_password(p) -> str`;
  - `create_app(users, private_pem, public_pem, kid, issuer, audience, scopes=(...), ttl_s=900, clock=time.time) -> FastAPI`, with routes `POST /auth/login`, `POST /auth/otp`, `GET /.well-known/openid-configuration`, `GET /jwks.json`;
  - `python -m bankagent.identity.app` serves on port 8081.

## Scope Limits

- `auth/tokens.py`, `identity/users.py`, `identity/app.py`. The staff, realtime and short-TTL additions are unit 55.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_full_login_issues_token_verifiable_with_published_jwks`, `test_portuguese_user_gets_pt_session`, `test_wrong_password_is_401`, `test_unknown_user_is_401`, `test_wrong_otp_is_401_and_ticket_is_single_use`, `test_discovery_document_points_to_jwks`, `test_expired_token_rejected`, `test_tampered_token_rejected`, `test_wrong_audience_and_issuer_rejected`, `test_unknown_kid_rejected`, `test_unsupported_lang_claim_defaults_to_es`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 3 (Session tokens and the mock OIDC identity service), lines 661–1003
