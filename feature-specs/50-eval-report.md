# 50 · Evaluation Report and Charts

**Subsystem:** Evaluation · **Depends on:** 48, 49 · **Reference:** evaluation plan, Task 11

## Goal

Render `reports/eval-<date>.md` with every required section and label, plus its charts.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Report (`reports/eval-<date>.md`) · evaluation §6

The deck quotes only this report and the as-is report.

1. **Setup:** goal mix, held-out hash, run ids; versions of the agent (git SHA), prompts, question sets, thresholds, policy; model ids for agent roles, Jev, persona, judge; run dates; cost assumptions.
2. **Headline table** (§5.2) with confidence intervals and denominators.
3. **Legacy vs new table** (§5.1) with the different-workload label on every row.
4. **Slices** and the investigation of any gap over 10 points.
5. **Results by failure type** (the last six groups of §4.1).
6. **Error analysis:** every failed or unsafe conversation gets one cause: `extract`, Jev, threshold, policy, `compose`, persona, harness. Counts per cause, plus five worked examples quoting decision records.
7. **Judge validation** (κ) and label-review corrections.
8. **Limitations:** synthetic data and its artifacts; no Portuguese-speaking customers; persona realism; n = 120 goals; offline measurement, not production; no system-level same-workload baseline (the resolver's B0-vs-P is the learned-component baseline).
9. **Projected savings** (§5.4), labeled.

Charts follow the dataviz skill and are saved to `reports/figures/eval-*.png`.

## Implementation

### Files

- Create: `eval/src/evalkit/report.py`, `eval/tests/test_report.py`

### Interfaces

- Consumes: `read_goals` (Task 4); `classify`, `CORRECT` (Task 8); everything in `evalkit.metrics` and `evalkit.compare` (Task 9); `validate` (Task 10); `asis_metrics.json` (Task 3).
- Produces:
  - `suggest_cause(rec, row) -> str` (one of `extract`, `Jev`, `threshold`, `policy`, `compose`, `persona`, `harness`, or `""`);
  - `build(goals, records, asis, cfg, judgments=None, labeled=None, review=None, causes=None) -> dict` (every number the report prints);
  - `render(data, date, figures) -> str`; `charts(data, out_dir) -> list[str]`;
  - CLI `python -m evalkit.report --run <dir> --goals <jsonl> --asis <json> [--review <csv>] [--labeled <csv>] --out <reports dir> --date <d>`, writing `classifications.jsonl`, `error_analysis.csv` (kept if it exists, so manual causes survive) and `eval-<date>.md`.

## Scope Limits

- `report.py` and its tests. Projections stay in their own labeled section.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_report_has_every_section_and_labels`, `test_charts_render`, `test_suggest_cause`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 11 (Evaluation report and charts), lines 3762–4088
