# 71 · Staff Sign-In, Console Shell, Queue and Case Header (world C)

**Subsystem:** UI · **Depends on:** 66, 68 · **Reference:** ui plan, Task 19

## Goal

Build staff login, the live queue with filters, and the case header with lifecycle actions and the resolve dialog.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → World C · ui §7.2; Agent console · ui §8.2
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/components/staff/StaffLogin.tsx`, `web/components/staff/Console.tsx`, `web/components/staff/ConsoleWithTabs.tsx`, `web/components/staff/Queue.tsx`, `web/components/staff/CaseHeader.tsx`, `web/lib/staff/actions.ts`, `web/app/agent/page.tsx`, `web/app/agent/[handoffId]/page.tsx`
- Modify: `web/app/login/page.tsx` (staff branch)
- Test: `web/tests/unit/case-header.test.tsx`, `web/tests/unit/queue.test.tsx`

### Interfaces

- Consumes: `/api/handoffs*` (Task 14), `useChannel` (Task 16), `QueueEvent`/`HandoffRow`/`HandoffPacket` (Task 10), `fmtAge` (Task 10).
- Produces:
  - `allowedActions(p: {status, claimed_by}, me: string) -> ("claim" | "takeover" | "return" | "resolve")[]`;
  - `REASON_TEXT` (plain-language reason codes);
  - `Console({me: {sub, name}, initialId?})`, `Queue({rows, filter, onFilter, selected, onSelect, fresh})`, `CaseHeader({packet, control, me, onAction})`;
  - `StaffLogin({next})`.

## Scope Limits

- `/login?staff=1`, `/agent`, `/agent/[handoffId]`: the queue with filters and live updates, and the case header with lifecycle actions and the resolve dialog. Tab contents are Tasks 20–21, and this task renders placeholders for them.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes. Manually, an open handoff can be claimed, and a second browser session sees it move out of *Open* without refreshing.
- The reference task's tests exist and pass:
  `shows only allowed actions and names who holds the case`, `resolve asks for an outcome and a note`, `renders priority as a word, plain reasons, language, age and holder`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 19 (Staff sign-in, console shell, queue and case header (world C)), lines 5630–6063
