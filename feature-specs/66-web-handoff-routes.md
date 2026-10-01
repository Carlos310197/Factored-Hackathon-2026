# 66 · Handoff Routes for the Console

**Subsystem:** UI · **Depends on:** 64 · **Reference:** ui plan, Task 14

## Goal

Expose the queue, packet and lifecycle actions to signed-in agents as thin routes over unit 64.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → BFF route handlers · ui §6
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/app/api/handoffs/route.ts`, `web/app/api/handoffs/[id]/route.ts`, `web/app/api/handoffs/[id]/[action]/route.ts`
- Test: `web/tests/unit/handoff-routes.test.ts`

### Interfaces

- Consumes: `staffFrom` (Task 11); `listHandoffs`, `getHandoff`, `claim`, `takeover`, `returnToAssistant`, `resolve`, `ConflictError` (Task 12); `getSession` (Task 12).
- Produces:
  - `GET /api/handoffs?filter=open|mine|in_takeover|resolved` → `{data: HandoffRow[]}`. `mine` = claimed, in takeover or returned, with `claimed_by = me`.
  - `GET /api/handoffs/[id]` → `{data: {packet: HandoffPacket, control: string}}`.
  - `POST /api/handoffs/[id]/{claim|takeover|return|resolve}` → `{data: HandoffPacket}`; `409 conflict`; `404` for an unknown action; `resolve` takes the body `{code: ResolutionCode, note: string ≤ 500}`.

## Scope Limits

- `app/api/handoffs/**` routes. They're thin over Task 12.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes.
- The reference task's tests exist and pass:
  `is 401 without staff`, `mine keeps only my claimed, in-takeover and returned cases`, `dispatches each action with the signed-in agent`, `maps ConflictError to 409, unknown actions to 404 and a bad resolve body to 400`, `returns the packet with the session's control`
- **An agent resolving or returning a case they don't hold** (a second tab, or a colleague's case). Expected: a conflict (`409` from the route), and the other agent's takeover is unchanged. Pinned in Task 12 (`takeover sets control and writes a system message; return by a non-holder is 409 and control is unchanged`) and Task 14 (`maps ConflictError to 409…`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 14 (Handoff routes for the console), lines 4079–4268
