# 36 · Resolver Jev Runs and Evaluation Report

**Subsystem:** Transaction resolver · **Depends on:** 35 · **Reference:** resolver plan, Task 11

## Goal

Run the Jev-based systems with cached, resumable results, apply the fixed adoption rule, and render the evaluation report.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Adoption rule (fixed before the test run) · resolver §6.4

- **P replaces B2 in the agent** if both hold on test:
  1. its wrong-action rate is not higher than B2's (point estimate);
  2. its hard-slice resolved-within-one-step is higher than B2's.
- **Otherwise** the report states that the ranker did not help, and the agent keeps `understand.v1` with the agent-core thresholds.
- The decision is recorded in the report and in this spec's changelog.

### Error analysis · resolver §6.5

Every act-wrong or failed case on test gets one cause:
- `extract` missed or mangled a field;
- a description style the simulator does not model;
- the ranker ranked the target below another candidate;
- Jev overrode a correct top-ranked candidate;
- the message is genuinely ambiguous (also failed in the human-ceiling pass).

The report includes counts per cause and five worked examples.

### Report · resolver §6.6

`resolver/reports/eval-<date>.md` contains:
- the system table;
- slice tables with confidence intervals;
- the reliability diagram and coverage curve (PNG);
- the error analysis;
- the human ceiling;
- versions: artifact, question sets, thresholds, prompts, models;
- the adoption decision.

The slides quote this report only.

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/jev_runs.py`, `agent/src/bankagent/resolver/evaluate.py`, `agent/tests/test_resolver_evaluate.py`

### Interfaces

- Consumes: `build_understand_request`, `select_candidates`, `JevError` (agent-core and Task 4); `Resolver`, `Scores` (Task 6); Task 10's systems and metrics; `main` (Task 5); `search` (Task 7); the test doubles `understand_answers` (agent-core `tests/fakes.py`), `ListTracker` (Task 7), `dirs` (Task 5).
- Produces:
  - `SYSTEMS = ("B2", "P")`, `session_facts(lang)`, `jev_request(row, qset, scores=None)`, `to_target(result, aliases)`;
  - `runs_path(root, set, system, repeat)`, `load_runs(path)`, `run_system(rows, system, jev, qsets, resolver, path) -> new_calls` (resumable JSON lines);
  - `score_rows(rows, resolver) -> (scores, latency_ms)`, `tune_systems(dev_rows, scores, dev_runs) -> (thresholds, curves)`, `evaluate(rows, scores, th, runs) -> {system: [outcomes per repeat]}`;
  - `summary_table`, `slice_masks`, `adoption(results, rows)`, `write_error_sheet(...)`, `cause_counts`, `plot_curves`, `plot_reliability`, `reliability_bins`, `latency_line`, `render_report(...)`.
  - Test doubles `ScriptedJev(fail_every=0)` and `rows_for(history_serving, split, n, seed)`.

## Scope Limits

- `jev_runs.py` and `evaluate.py`. Jev runs need `--live`. The adoption rule is code, fixed before the test run.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_runs_are_cached_and_resumable`, `test_tune_evaluate_report_pieces`, `test_adoption_not_run_without_jev`, `test_offline_flow_finalize_tune_report`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 11 (Jev runs and the evaluation report), lines 3332–3854
