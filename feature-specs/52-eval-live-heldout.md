# 52 · Eval Live Run II: Held-Out Run, Judge Validation, Report

**Subsystem:** Evaluation · **Depends on:** 51 · **Reference:** evaluation plan, Task 13 · **[live]**

## Goal

Run the frozen held-out set (3 repetitions), validate the judge, and write the evaluation report.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Generated and committed: `eval/runs/<heldout_run_id>/` (run.json, conversations.jsonl, classifications.jsonl, judgments.jsonl, human_sheet.csv, human_sheet_labeled.csv, error_analysis.csv), `reports/eval-<date>.md`, `reports/figures/eval-*.png`
- Modify: `docs/superpowers/specs/2026-10-01-evaluation-design.md` (§10 changelog)

### Interfaces

- Consumes: Tasks 4–12; the frozen `heldout_v1.jsonl`; `analysis/asis/out/asis_metrics.json`.
- Produces: the evaluation report the deck quotes.

### Notes

- The Files list says to edit the spec's changelog under `docs/superpowers/specs/`. Record it in `context/progress-tracker.md` → Spec Changelog instead (the design specs are frozen).

## Scope Limits

- one held-out run (3 repetitions), the judge run, human labels and the report. A rerun is allowed only to fix a harness or agent bug, and the report then discloses both results.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- The evaluation definition of done (`context/project-overview.md` → Success Criteria · evaluation §10) is met.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 13 (Live run II: held-out run, judge validation, report), lines 4155–4198
