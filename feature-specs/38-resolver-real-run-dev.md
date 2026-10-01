# 38 · Resolver Real Run I: Train, Dev Set, Finalize, Tune

**Subsystem:** Transaction resolver · **Depends on:** 37 · **Reference:** resolver plan, Task 13 · **[live]**

## Goal

Train for real, build the dev set (Bedrock), choose and calibrate the finalist, run B2 and P on dev (Jev), and tune the thresholds.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create (generated): `agent/resolver/data/dev_v1.jsonl`, `agent/src/bankagent/resolver/artifacts/v1/model.json` (plus `model.txt` if LightGBM wins), `agent/src/bankagent/resolver/artifacts/v1/MODEL_CARD.md`, `agent/resolver/runs/jev/dev/B2_r1.jsonl`, `agent/resolver/runs/jev/dev/P_r1.jsonl`, `agent/resolver/reports/thresholds_dev.json`, `agent/resolver/reports/dev_coverage_curve.png`, `agent/resolver/reports/dev_reliability.png`, `agent/src/bankagent/decisions/thresholds.v2.yaml`

### Interfaces

None: this is a documentation or run task.

## Scope Limits

- Generated artifacts and fixes only. Every live step (about 600 Bedrock and 600 Jev calls) needs the owner's approval.
- The test set is not touched.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- The artifact, model card, dev runs, threshold report and `thresholds.v2.yaml` are committed; `uv run pytest` passes.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 13 (Real run I: train, dev set, finalize, Jev on dev, tune), lines 4202–4261
