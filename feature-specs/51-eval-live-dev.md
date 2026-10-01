# 51 · Eval Live Run I: Smoke, Goal Sets, Review, Dev Run, Freeze

**Subsystem:** Evaluation · **Depends on:** 50, 24 · **Reference:** evaluation plan, Task 12 · **[live]**

## Goal

Configure the persona and prices, generate and review the goal sets, run the 30 dev goals, then freeze the held-out set and its hash.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Modify: `eval/config.yaml` (persona model, serving path, prices, legacy cost), `docs/superpowers/specs/2026-10-01-evaluation-design.md` (§10 changelog)
- Generated and committed: `eval/goals/dev_v1.jsonl`, `eval/goals/heldout_v1.jsonl`, `eval/goals/heldout_v1.sha256`, `eval/goals/review_heldout_v1.csv`, `eval/runs/<dev_run_id>/` (run.json, conversations.jsonl, classifications.jsonl, calibration_notes.md)

### Interfaces

- Consumes: Tasks 4–11; the agent-core plan complete through its Task 14; DynamoDB Local from `agent/docker-compose.yml`; the local serving set from `agent/scripts/build_local_serving.py`.
- Produces: the frozen held-out goal set and its hash.

### Notes

- The Files list says to edit the spec's changelog under `docs/superpowers/specs/`. Record it in `context/progress-tracker.md` → Spec Changelog instead (the design specs are frozen).

## Scope Limits

- configuration, generated data and one dev run. Every step that calls the persona, Bedrock or Jev needs the owner's approval for that step. No code changes except fixes to bugs found here, each with a test in the owning task's test file.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- The held-out SHA-256 is recorded in `progress-tracker.md` → Spec Changelog → Evaluation before any held-out run.
- Calibration notes from the dev run are committed.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 12 (Live run I: smoke test, goal sets, review, dev run, freeze), lines 4092–4151
