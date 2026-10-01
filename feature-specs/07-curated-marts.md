# 07 · Curated Marts, Decline-Reason Seed and DQ Results

**Subsystem:** Data pipeline · **Depends on:** 06 · **Reference:** pipeline plan, Task 7

## Goal

Build the contract-enforced curated marts and the decline-reason seed, and persist dbt test results to `META.DQ_RESULTS`.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract
- `context/architecture-context.md` → Serving contract → CURATED · pipeline §5.3 (the column contract)

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `dbt/models/curated/dim_customer.sql`, `dim_product.sql`, `fct_transaction.sql`, `fct_complaint.sql`, `fct_interaction.sql`, `dbt/models/curated/schema.yml`, `dbt/seeds/seed_decline_reason.csv`, `dbt/seeds/seeds.yml`, `pipeline/dq_results.py`, `tests/test_dq_results.py`

### Interfaces

- Consumes: `stg_*` from Task 6.
- Produces: curated tables per spec §5.3; `pipeline.dq_results.parse_dbt_results(run_results: dict, manifest: dict) -> list[dict]` with keys `test_name, model, severity, status, failures`; `pipeline.dq_results.write(cur, run_id, rows)`; CLI `uv run python -m pipeline.dq_results --run-id <id> [--database ...]` reading `dbt/target/run_results.json` and `dbt/target/manifest.json`.

## Scope Limits

- Curated models, the seed and the DQ-results writer. No export.
- Column names and types exactly as pipeline §5.3. PII columns never leave RAW.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_parse_only_tests_with_model_and_severity`
- `dbt build` is green with contracts enforced, and `META.DQ_RESULTS` has rows for the run.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 7 (Curated marts with enforced contracts, the decline-reason seed, and DQ results), lines 1420–1700
