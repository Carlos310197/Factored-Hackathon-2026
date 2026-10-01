# 61 · Web Scaffold, Design Tokens, Fonts and Test Harness

**Subsystem:** UI · **Depends on:** none · **Reference:** ui plan, Task 9

## Goal

Create the Next.js 16 app with both worlds' tokens, the fonts, Vitest and Playwright configs, and the shared id helper.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → Visual design · ui §7
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/` (via `create-next-app`), `web/app/globals.css`, `web/app/layout.tsx`, `web/app/page.tsx`, `web/vitest.config.ts`, `web/vitest.setup.ts`, `web/playwright.config.ts`, `web/lib/ids.ts`, `web/.env.example`
- Test: `web/tests/unit/ids.test.ts`

### Interfaces

- Produces:
  - `newClientMessageId(): string`, matching `^[A-Za-z0-9_-]{8,64}$` (the agent's `MESSAGE_ID_RE`);
  - CSS tokens as Tailwind utilities (`bg-b-mist`, `text-c-ink`, `rounded-bubble`, `font-customer`, `font-staff`, and so on);
  - CSS variables `--font-schibsted`, `--font-hanken`.

## Scope Limits

- project setup, `globals.css` tokens for both worlds, fonts, test configs, and one utility with its test. No pages beyond a redirect.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test`, `npm run lint` and `npm run build` all pass. `/` redirects to `/chat`.
- The reference task's tests exist and pass:
  `matches the agent's accepted message-id pattern and is unique`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 9 (Scaffold, design tokens, fonts and the test harness), lines 2240–2462
