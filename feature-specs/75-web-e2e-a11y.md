# 75 · Web End-to-End Tests and Accessibility Scans

**Subsystem:** UI · **Depends on:** 74 · **Reference:** ui plan, Task 23

## Goal

Cover the customer, console and demo flows with Playwright against the production build, and scan every page with axe.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/code-standards.md` → Testing requirements → Testing · ui §12
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Modify: `web/lib/server/session.ts` (the E2E cookie path)
- Create: `web/e2e/fixtures.ts`, `web/e2e/customer.spec.ts`, `web/e2e/console.spec.ts`, `web/e2e/demo.spec.ts`
- Test: `web/tests/unit/e2e-guard.test.ts`

### Interfaces

- Consumes: every page and component from Tasks 17–22.
- Produces:
  - E2E cookies, honoured **only** when `E2E_MOCK=1` and `DEMO_MODE=1`: customer `cust_session=e2e.customer.<sub>.<sid>.<lang>`, staff `staff_session=e2e.staff.<sub>.<name>`;
  - `mockApi(page, handlers)` in `e2e/fixtures.ts`.

## Scope Limits

- Playwright specs against the production build, with `/api/*` mocked in the browser and an E2E-only cookie format for server-rendered pages. No product changes except the guarded E2E session path.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm run e2e` passes in both projects. The axe scans report no `serious` or `critical` violations on `/login`, `/chat`, `/agent`, `/trace/<sid>` and `/demo`.
- The reference task's tests exist and pass:
  `are ignored unless E2E_MOCK=1 and DEMO_MODE=1`, `clarify: options become chips and a tap sends the text`, `confirm → filed: the card shows the draft, confirming shows the receipt`, `handoff → takeover: reference chip, agent joins, agent message appears`, `expired token: the sign-in sheet keeps the conversation`, `login page has no serious accessibility issues`, `claim → take over → message → return → resolve`, `trace page renders turns and passes the a11y scan`, `acts 1–3`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 23 (End-to-end tests and accessibility scans), lines 6975–7311
