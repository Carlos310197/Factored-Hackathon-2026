# 80 · Identity Service as a Lambda

**Subsystem:** Deployment · **Depends on:** 55 · **Reference:** deployment plan, Task 4

## Goal

Wrap the FastAPI IdP for Lambda with Mangum, load demo identities from S3 and the signing key from Secrets Manager, and build its ARM64 image.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #4 in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/identity/lambda_handler.py`, `agent/Dockerfile.identity`
- Modify: `agent/pyproject.toml` (+ `mangum`), `agent/.dockerignore` (unchanged content; verify `config` stays excluded)
- Test: `agent/tests/test_identity_lambda.py`

### Interfaces

- Consumes:
  - `create_app(users, private_pem, public_pem, kid, issuer, audience, ..., demo_mode=False)` (agent-core Task 3, UI Task 3);
  - `load_users(path)`, `generate_keypair()`.
- Produces:
  - `build(env, s3, secrets) -> Mangum`;
  - `handler(event, context) -> dict` (Lambda entrypoint `bankagent.identity.lambda_handler.handler`).
  - Environment variables: `IDP_ISSUER`, `IDP_AUDIENCE`, `IDP_KID`, `IDP_SIGNING_SECRET_ID`, `DEMO_USERS_S3_URI`, `IDP_DEMO_MODE`.

## Scope Limits

- a Lambda entrypoint around the existing FastAPI app, and its image. No change to the IdP's routes or tokens.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_identity_lambda.py -v` passes, and the identity image builds for ARM64.
- The reference task's tests exist and pass:
  `test_discovery_and_jwks_served_from_secret_key`, `test_cold_start_failure_returns_503_and_retries`, `test_bad_s3_uri_is_a_cold_start_failure`
- **The identity Lambda cold-starts while the demo-identities object is missing or unreadable** (seed not run yet, or the object deleted). Expected: `503 {"error":"identity_unavailable"}`, a logged exception, and **no cached failure**: the next request retries and succeeds once the object exists. Pinned in Task 4 (`test_cold_start_failure_returns_503_and_retries`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 4 (The identity service as a Lambda), lines 925–1115
