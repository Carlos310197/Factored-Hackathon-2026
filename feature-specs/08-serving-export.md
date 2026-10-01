# 08 · Serving Export with Atomic Pointer (sorted by customer)

**Subsystem:** Data pipeline · **Depends on:** 07 · **Reference:** pipeline plan, Task 8 · **[live]**

## Goal

Unload the curated marts as lowercase-column parquet to a run folder in the serving bucket, sorted by `customer_id`, then flip `latest.json`.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract
- `context/architecture-context.md` → Serving contract → Serving export · pipeline §5.4
- `context/architecture-context.md` → Interfaces Between Subsystems → To the data pipeline · agent-core §9.3

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `pipeline/export.py`, `tests/test_export.py`

### Interfaces

- Consumes: curated tables (Task 7), `RAW.SERVING_STAGE` (Task 2).
- Produces: `EXPORT_TABLES`, `export_select(table: str, columns: list[str]) -> str`, `table_columns(cur, schema, table) -> list[str]`, `unload_table(cur, table, run_id, stage) -> int`, `build_pointer(run_id, exported_at, max_process_date, tables: dict[str,int]) -> dict`, `write_pointer(cur, pointer, stage)`, `list_runs(cur, stage) -> list[str]`, `prune_runs(cur, stage, keep=3)`, `run_export(conn, run_id, stage="RAW.SERVING_STAGE") -> dict`. CLI: `uv run python -m pipeline.export --run-id <id> [--database ... --stage ...]`. Pointer schema: `{"run_id": str, "exported_at": ISO-8601, "max_process_date": "YYYY-MM-DD", "tables": {"dim_customer": rows, ...}}` and files at `<stage>/<run_id>/<table>/data_*.parquet`.

*Also, from agent-core plan Task 15:*

- Produces: the pipeline's `export_select(table, columns)` appends `order by CUSTOMER_ID` when the table has that column, so DuckDB in the agent can skip row groups by customer (agent spec §7.1, §9.3).

### Notes

- This unit also covers agent-core plan Task 15 (the sort-order request). Its pinned tests are listed below and its code lives in the second reference.

## Scope Limits

- `pipeline/export.py` and its tests.
- The agent core's change request is built in here: `export_select` sorts `fct_transaction`, `fct_complaint` and `dim_product` by `customer_id`; tables without that column are unsorted.
- The real export to the bucket is an owner-approved step.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  `test_export_tables`, `test_export_select_quotes_lowercase`, `test_build_pointer_shape`, `test_runs_to_prune_keeps_newest_three`, `test_run_export_does_not_write_pointer_on_failure`
- Column-name case: Snowflake stores unquoted identifiers uppercase; parquet must carry lowercase names or DuckDB queries in the agent break. Pinned in Task 8 (`test_export_select_quotes_lowercase`) and the fixture test's parquet column assertion.
- Pointer flip with a failed unload: if any table's unload fails, `latest.json` must not move. Pinned in Task 8 (`test_run_export_does_not_write_pointer_on_failure`).
- Agent-core Task 15 tests pass too: `test_export_select_quotes_lowercase_and_sorts_by_customer`, `test_export_select_without_customer_column_is_unsorted`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 8 (Export to the serving bucket with an atomic pointer), lines 1704–1881

`docs/reference/plans/2026-09-29-agent-core.md`: Task 15 (Request the serving-export sort order from the pipeline), lines 5948–6007
