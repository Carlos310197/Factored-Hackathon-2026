# 42 · As-Is Reconciliation, Charts, Report and the Real Run

**Subsystem:** Evaluation · **Depends on:** 41 · **Reference:** evaluation plan, Task 3

## Goal

Reconcile against the curated marts, draw the charts, write the as-is report, and run it on the local drop.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Outputs · evaluation §3.3

- `analysis/asis/out/asis_metrics.json`: every number used downstream, keyed by metric and slice, with `n` for each. Its schema is the contract §5.1 reads.
- `reports/asis-<date>.md`: the narrative, with tags and charts.
- `reports/figures/asis-*.png`: charts built following the dataviz skill.
- Committed. The runner is deterministic: same input files, same outputs.

### Reconciliation · evaluation §3.4

When the curated marts exist, `analysis/asis/reconcile.py` compares, for the same window: interaction count, complaint count and FCR for `Transaccional` against `fct_interaction` and `fct_complaint`. A difference over 0.1% fails the run. If the marts are not available, the report states "not reconciled".

## Implementation

### Files

- Create: `analysis/asis/reconcile.py`, `analysis/asis/reconcile.sql`, `analysis/asis/charts.py`, `analysis/asis/report.py`, `analysis/asis/run.py`, `analysis/asis/tests/test_run.py`
- Generated and committed: `analysis/asis/out/asis_metrics.json`, `reports/asis-<date>.md`, `reports/figures/asis-*.png`

### Interfaces

- Consumes: `connect`, `collect`, `detect_all` (Tasks 1–2).
- Produces:
  - `reconcile(metrics: dict, curated: dict | None) -> {"status": "reconciled"|"mismatch"|"not reconciled", "checks": [...]}`; `TOLERANCE = 0.001`;
  - `render_all(metrics: dict, out_dir: Path) -> list[str]` (file names);
  - `render(metrics, artifacts, recon, date, figures) -> str`;
  - CLI `python -m asis.run [--data] [--out] [--reports] [--curated-counts] [--date]`, returning 0, or 1 on a reconciliation mismatch;
  - `asis_metrics.json` = `{"meta": {...}, "metrics": {...}, "artifacts": [...], "reconciliation": {...}}` (the contract `evalkit.compare` reads).

## Scope Limits

- The real run reads local files only (no live calls). If the marts aren't available, the report says "not reconciled".
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_reconcile_passes_on_exact_match_and_fails_beyond_tolerance`, `test_charts_are_written`, `test_report_tags_artifacts_and_states_reconciliation`, `test_run_is_deterministic`, `test_run_fails_on_mismatch_without_writing`
- `asis_metrics.json`, `reports/asis-<date>.md` and the figures are committed, and the run is deterministic.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 3 (Reconciliation, charts, report, CLI and the real as-is run), lines 750–1099
