# 69 · Customer Login (world B)

**Subsystem:** UI · **Depends on:** 63 · **Reference:** ui plan, Task 17

## Goal

Build `/login` for customers: language, labeled demo identity, password, then the shown OTP, plus the demo bridge.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → World B · ui §7.1; Customer chat · ui §8.1 (Login)
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/app/login/page.tsx`, `web/components/customer/LoginForm.tsx`, `web/lib/demo/bridge.ts`
- Test: `web/tests/unit/login-form.test.tsx`

### Interfaces

- Consumes: `/api/auth/login`, `/api/auth/otp` and `/api/auth/demo-users` (Task 11); `t()` (Task 10).
- Produces:
  - `LoginForm({next, embed, prefillUser?, shortTtl?, auto?})`;
  - `notifyParent(msg: DemoMessage)` and the type `DemoMessage = {type: "demo:auth", step: "otp_verified" | "token_issued"} | {type: "demo:session", sid: string} | {type: "demo:turn-start"} | {type: "demo:turn-reply", turn_id: string | null} | {type: "demo:prefill", text: string}`;
  - `/login?next=&embed=1&user=&short=1&auto=1` (`auto` only works in demo mode, because demo users come from the demo-only endpoint).

## Scope Limits

- `/login` for customers (staff login is Task 19): language, demo identity, password, then OTP. Embed and demo hooks.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes. Manually against the local agent stack: sign in as a demo user and land on `/chat`.
- The reference task's tests exist and pass:
  `filters identities by language and switches the copy`, `signs in with password then the shown OTP and goes to next`, `shows a plain error when the code is rejected`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 17 (Customer login (world B)), lines 5013–5260
