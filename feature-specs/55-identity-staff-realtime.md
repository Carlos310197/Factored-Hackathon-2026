# 55 · Identity: Staff Login, Realtime Token, Demo List, Short-TTL Tokens

**Subsystem:** UI · **Depends on:** 14 · **Reference:** ui plan, Task 3

## Goal

Extend the IdP with roles, staff identities and login, subscribe-only realtime tokens, the demo picker list and short-TTL demo tokens.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- UI plan #5 and #6 in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From ui §4:*

8. **Identity service.**
   - About 3 labelled staff identities: role `agent`, scope `handoff:work`, display name.
   - `POST /auth/staff/login`.
   - `POST /auth/realtime-token`: a 15-minute, subscribe-only token for the caller's role and `sid`.
   - Demo identities may request a 30-second access token, for the "expired token" scenario only.

## Implementation

### Files

- Modify: `agent/src/bankagent/auth/tokens.py`, `agent/src/bankagent/identity/users.py`, `agent/src/bankagent/identity/app.py`
- Test: `agent/tests/test_identity_ui.py`

### Interfaces

- Consumes: `issue_token`, `generate_keypair`, `jwks_from_public`, `DemoUser`, `load_users`, `create_app` (agent-core Task 3).
- Produces:
  - `issue_token(..., extra: dict | None = None)`: `extra` claims are merged in, and customer tokens now carry `role: "customer"`.
  - `DemoUser` gains `role="customer"`, `display_name=""`, `demo_password=""`, `scenarios=()` and `short_ttl_allowed=False`.
  - `create_app(..., staff_audience="bankagent-staff", realtime_audience="realtime", demo_mode=False)`.
  - `POST /auth/otp` accepts `short_ttl: bool` (a 30 s token, only when `short_ttl_allowed`), and refuses non-customer users.
  - `POST /auth/staff/login {username, password}` → `{access_token, token_type, expires_in, name}`, with claims `aud=bankagent-staff`, `sub=username`, `sid=STAFF-…`, `scope=handoff:work`, `role=agent`, `name`.
  - `POST /auth/realtime-token` (header `Authorization: Bearer <customer or staff token>`) → `{token, expires_in}`, with claims `aud=realtime`, `sub`, `sid`, `role`, `scope=realtime:subscribe`, and `exp` ≤ the source token's `exp`.
  - `GET /auth/demo-users` (only with `demo_mode`) → `[{username, demo_password, otp, lang, role, display_name, scenarios}]`; `404` otherwise.

## Scope Limits

- `auth/tokens.py`, `identity/users.py` and `identity/app.py` only. The agent's own verification is unchanged: it keeps accepting only audience `bankagent`.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_identity.py tests/test_identity_ui.py -v` passes.
- The reference task's tests exist and pass:
  `test_customer_token_has_customer_role_and_still_verifies_for_agent`, `test_short_ttl_only_for_allowed_users`, `test_staff_cannot_use_customer_login`, `test_staff_login_issues_staff_audience_token_rejected_by_agent_verifier`, `test_customer_cannot_use_staff_login`, `test_realtime_token_for_customer_is_bound_to_sid_and_never_outlives_source`, `test_realtime_token_for_agent`, `test_realtime_token_rejects_missing_or_bad_token`, `test_demo_users_only_in_demo_mode`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 3 (Identity service: roles, staff login, realtime token, demo list, short-TTL tokens), lines 464–752
