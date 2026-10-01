# 73 · Trace Components, the Reveal, `/trace/[sid]` and the Trace Tab

**Subsystem:** UI · **Depends on:** 72 · **Reference:** ui plan, Task 21

## Goal

Render trace turn blocks with the reveal motion, the standalone trace page, the live console Trace tab and the stage lights.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → Motion · ui §7.4; Trace component · ui §8.3
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/components/trace/TraceTurn.tsx`, `web/components/trace/TraceList.tsx`, `web/components/trace/AnalysingCard.tsx`, `web/app/trace/[sid]/page.tsx`
- Modify: `web/components/staff/ConsoleWithTabs.tsx` (the Trace tab)
- Test: `web/tests/unit/trace-components.test.tsx`

### Interfaces

- Consumes: `TraceTurn`, `TraceBar` (Task 15); `stageOf`, `STAGES` (Task 15); `Gauge` (Task 20); `useChannel` (Task 16); `TraceEvent` (Task 10).
- Produces:
  - `TraceTurnView({turn, reveal?, collapsed?, onToggle?})`;
  - `AnalysingCard({turnNumber, lit: Stage[], current: Stage | null})`;
  - `TraceList({sid, mode: "page" | "console" | "demo", refreshKey?, onTurnComplete?, running?})`: fetches `/api/trace/:sid`; subscribes to `/trace/<sid>` as staff; lights stages from `record` events; on `turn_complete` or a `refreshKey` change, refetches and reveals the newest turn; in `demo` mode older turns collapse.

## Scope Limits

- rendering the view model from Task 15, the stage lights, and the live list. No demo-stage layout (that's Task 22).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes. `/trace/<sid>` for a real session shows every turn, newest on top. With reduced motion set in the OS, bars appear without animating.
- The reference task's tests exist and pass:
  `renders open bars with verdicts, the fold, the reply check, errors and the route strip`, `expands the folded signals on demand`, `collapsed shows only the route strip`, `marks finished, current and pending stages`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 21 (Trace components, the reveal, `/trace/[sid]` and the console Trace tab), lines 6345–6631
