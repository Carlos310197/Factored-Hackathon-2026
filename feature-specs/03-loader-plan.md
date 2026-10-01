# 03 · Loader Plan Logic

**Subsystem:** Data pipeline · **Depends on:** 02 · **Reference:** pipeline plan, Task 3

## Goal

Write the pure functions that decide, per staged file, whether to load it as new, force-reload it as restated, or skip it.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Loader

*From pipeline §5.1:*

Loader (`pipeline/load.py`, Python + snowflake-connector, no AWS credentials): `LIST @organizer_stage/<table>/` → compare `name` and `md5` (ETag) against `META.RUN_MANIFEST` → for each new file `COPY INTO` with `PATTERN` of that file; for each changed file `COPY INTO … FORCE = TRUE`; insert one manifest row per file (`run_id`, `table`, `file`, `etag`, `rows_loaded`, `loaded_at`, `mode` = new|restated|skipped). Dimension CSVs are treated the same way (one file each). Retries: one retry on connector/network errors; a second failure fails the job.

## Implementation

### Files

- Create: `pipeline/load.py`, `tests/test_load.py`

### Interfaces

- Produces: `StageFile(path: str, md5: str, size: int)`, `LoadAction(path: str, mode: Literal["new","restated","skipped"])`, `plan_loads(files: list[StageFile], manifest: dict[str, str]) -> list[LoadAction]`, `relative_path(stage_url_prefix: str, listed_name: str) -> str`, `chunks(seq, n)`.
- Table registry: `TABLES = {"CUSTOMERS": "customers.csv", "PRODUCTS": "products.csv", "TRANSACTIONS": "transactions/", "COMPLAINTS": "complaints/", "INTERACTIONS": "call_center_interactions/"}` (RAW table → stage prefix).

## Scope Limits

- Pure functions only: no Snowflake calls (those are unit 04).
- The manifest comparison is by file name and ETag (`md5`).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_plan_loads_new_restated_skipped`, `test_plan_loads_zero_row_file_is_new`, `test_relative_path_strips_stage_prefix`, `test_relative_path_internal_stage_strips_stage_name`, `test_chunks`, `test_tables_registry`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 3 (Loader plan logic (pure functions)), lines 459–579
