# 25 · Agent Live Checks, Definition-of-Done Run and README

**Subsystem:** Agent core · **Depends on:** 24 · **Reference:** agent-core plan, Task 14 · **[live]**

## Goal

Measure serving read latency, run the agent-core definition-of-done demo against real Jev and Bedrock, and write the agent README.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `context/project-overview.md` → Success Criteria → Definition of done · agent-core §11

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/scripts/smoke_serving.py`, `agent/README.md`
- Modify: `agent/docs/smoke-results.md`

### Interfaces

- Consumes: everything above.
- Produces: recorded smoke results (serving read latency), a demo transcript of the definition-of-done scenarios (spec §11), and `agent/README.md`.

## Scope Limits

- Measurement, the demo run and docs only. Fix bugs found here in their owning unit's code, with a test.
- Check the data-use gate (Open Questions) before any end-to-end run. Every Jev, Bedrock and S3 step needs the owner's approval.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- The definition-of-done run is recorded in `agent/docs/smoke-results.md`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 14 (Live checks, the end-to-end demo run, and the README), lines 5795–5944
