# 63 · Web Server Auth: JWT, Cookies, IdP Client, Auth Routes, `proxy.ts`

**Subsystem:** UI · **Depends on:** 62, 55 · **Reference:** ui plan, Task 11

## Goal

Verify IdP JWTs on the server, set httpOnly cookies, proxy the auth routes to the IdP, and guard pages.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → BFF route handlers · ui §6
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/lib/server/env.ts`, `web/lib/server/jwt.ts`, `web/lib/server/session.ts`, `web/lib/server/http.ts`, `web/lib/server/idp.ts`, `web/proxy.ts`
- Create: `web/app/api/auth/login/route.ts`, `otp/route.ts`, `staff-login/route.ts`, `logout/route.ts`, `realtime-token/route.ts`, `debug-claims/route.ts`, `demo-users/route.ts`
- Test: `web/tests/unit/jwt.test.ts`, `web/tests/unit/auth-routes.test.ts`, `web/tests/helpers/keys.ts`

### Interfaces

- Consumes: the IdP endpoints (Task 3).
- Produces:
  - `env(): Env` (Zod-parsed, memoized);
  - `makeVerifier(getKey: JWTVerifyGetKey, cfg: {issuer, audience, staffAudience})` returning `{customer(token): Promise<CustomerSession>, staff(token): Promise<StaffSession>}`, where `CustomerSession = {token, sub, sid, lang, scopes, exp}` and `StaffSession = {token, sub, sid, name, exp}`, and either throws `AuthFailure("expired" | "invalid")`;
  - `verifier()` (the production instance);
  - `CUSTOMER_COOKIE = "cust_session"`, `STAFF_COOKIE = "staff_session"`;
  - `customerFrom(req: NextRequest) -> Promise<CustomerSession | null>`, `staffFrom(req) -> Promise<StaffSession | null>`, `customerFromCookies()`, `staffFromCookies()` (for Server Components);
  - `setSessionCookie(res, name, token, maxAge)`, `clearSessionCookie(res, name)`;
  - `ok(data, status?)`, `fail(code, message, status)`, `readJson(req, schema)`, which returns the parsed value or a `NextResponse` 400;
  - `idp`: `login(username, password) -> {login_ticket}`, `otp(ticket, otp, shortTtl) -> {access_token, expires_in, lang}`, `staffLogin(username, password) -> {access_token, expires_in, name}`, `realtimeToken(bearer) -> {token, expires_in}`, `demoUsers() -> DemoUser[]`; throws `IdpError(status)`.

## Scope Limits

- authentication plumbing and the auth routes. No chat, handoffs or trace.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes. A local run against the agent's IdP (`docker compose up` in `agent/`) sets `cust_session` after login and OTP.
- The reference task's tests exist and pass:
  `reads a customer session only from verified claims`, `rejects a staff token as a customer and a customer token as staff`, `reports expiry distinctly`, `rejects a staff-audience token without role agent`, `sets an httpOnly customer cookie with the token lifetime`, `rejects a malformed body with 400 and a wrong code with 401`, `uses the staff cookie when asked as staff, else the customer cookie; 401 without one`, `are 404 outside demo mode`, `demo-users hides staff from the customer picker unless asked`, `debug-claims needs a staff session and returns the customer's verified claims`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 11 (Server auth: env, JWT verification, cookies, the IdP client, `/api/auth/*`, `proxy.ts`), lines 2823–3335
