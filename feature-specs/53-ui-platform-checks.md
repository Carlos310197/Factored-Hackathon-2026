# 53 · UI Platform Checks (Amplify SSR, AppSync Events, CDK)

**Subsystem:** UI · **Depends on:** none · **Reference:** ui plan, Task 1 · **[live]**

## Goal

Verify the platform facts the UI spec marked as unverified before building on them.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/architecture-context.md` → Platform Facts · ui §2

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Modify: `docs/superpowers/plans/2026-09-30-ui.md` (append "Task 1 results")

### Interfaces

- Produces: the results that Tasks 8, 9, 13 and 24 read.

### Notes

- Record the results in `progress-tracker.md` (Session Notes, plus Architecture Decisions for anything that changes later units), not in the plan.
- If the 25 s SSR check fails, unit 76 sets `CHAT_ASYNC=1` (unit 65 implements both modes).

## Scope Limits

- checks and a written record only. No product code. Nothing that creates AWS resources is run without the owner's approval.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- the plan's "Task 1 results" section (at the end of this file) records a yes/no and evidence for each of the five checks, plus which conditional notes apply.
- The reference task's tests exist and pass:
  (no automated tests in this task)
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 1 (Platform checks (Amplify SSR, AppSync Events, CDK constructs)), lines 122–181
