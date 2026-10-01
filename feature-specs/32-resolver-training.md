# 32 · Resolver Training, Selection and MLflow Tracking

**Subsystem:** Transaction resolver · **Depends on:** 28, 31 · **Reference:** resolver plan, Task 7

## Goal

Train logistic regression and LightGBM over the grids, select one finalist per family on simulated validation, and log every run to MLflow.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From resolver §4.3 (items 2–4 are unit 34):*

1. **Hyperparameter search runs on simulated validation cases** from dev customers and dev anchors:
   - logistic regression: C ∈ {0.01, 0.1, 1, 10, 100};
   - LightGBM: `num_leaves` ∈ {7, 15, 31}, `learning_rate` ∈ {0.05, 0.1}, `n_estimators` ∈ {200, 500};
   - selected by hard-slice top-1 accuracy.

### Tracking · resolver §4.5

- MLflow with a local file store (`mlruns/`, gitignored). Every `train.py` run logs:
  - params: seed, `simulate.yaml` hash, serving `run_id`, feature list, hyperparameters;
  - dev metrics;
  - the artifact.
- `train.py --promote <run_id>` writes `resolver/artifacts/v1/` and refreshes the metrics in `MODEL_CARD.md`. Those files are committed.

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/train.py`, `agent/src/bankagent/resolver/tracking.py`, `agent/tests/test_resolver_train.py`

### Interfaces

- Consumes: `case_features`, `FEATURES` (Task 1); `Resolver` (Task 6); `simulate` (Task 3), `sample_histories` (Task 2) in tests.
- Produces:
  - `VERSION = "resolver.v1"`, `LOGREG_GRID`, `LGBM_GRID`;
  - `Finalist(family, params, path, val_metrics)`;
  - `build_matrix(cases) -> (X, y)`;
  - `fit_logreg(X, y, C, seed, out_dir, metadata) -> Resolver` and `fit_lightgbm(X, y, params, seed, out_dir, metadata) -> Resolver`;
  - `case_metrics(resolver, cases, mentions_key="mentions") -> {n, n_hard, top1, top1_hard, top1_easy, nil_auc, ece}`. `mentions_key="extraction"` reads `row["extraction"]["mentions"]`.
  - `expected_calibration_error(conf)`;
  - `search(train, val, out_dir, tracker, seed, metadata, logreg_grid=..., lgbm_grid=...) -> {"logreg": Finalist, "lightgbm": Finalist}` (also writes `finalists.json`);
  - `MlflowTracker(root)` with `.log(run_name, params, metrics, artifact_dir)`.

## Scope Limits

- `train.py` and `tracking.py`. Offline dependencies only (`resolver` group).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_build_matrix_shapes`, `test_search_logs_every_run_and_keeps_one_finalist_per_family`, `test_expected_calibration_error`, `test_mlflow_tracker_logs_a_run`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 7 (Training, selection and MLflow tracking), lines 2372–2638
