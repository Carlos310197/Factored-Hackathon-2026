# 11 · Data Pipeline README

**Subsystem:** Data pipeline · **Depends on:** 10 · **Reference:** pipeline plan, Task 11

## Goal

Document the pipeline for judges and teammates: contracts, freshness, lineage, quarantine, the fixture proof, the serving contract, access and limitations.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract
- `context/project-overview.md` → Success Criteria → Definition of done · pipeline §9

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `README.md` (pipeline section; the agent side adds its own sections later)

### Interfaces

None: this is a documentation or run task.

## Scope Limits

- The pipeline section of the root `README.md` only. Other subsystems add their own sections later.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- Every command in "Reproduce" runs as written.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 11 (README for the data pipeline), lines 2252–2329
