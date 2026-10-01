# 04 · Loader Snowflake Calls and First Full Load

**Subsystem:** Data pipeline · **Depends on:** 03 · **Reference:** pipeline plan, Task 4 · **[live]**

## Goal

Connect the loader plan to Snowflake (`LIST`, `COPY INTO`, manifest rows) and run the first full load into RAW.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract
- `feature-specs/03-loader-plan.md` → Loader

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Modify: `pipeline/load.py` (append)
- Create: `tests/test_load_live.py`

### Interfaces

- Consumes: Task 3 functions, `pipeline.connect.get_connection`.
- Produces: `list_stage_files(cur, stage: str, prefix: str, stage_url_prefix: str) -> list[StageFile]`, `read_manifest(cur, table: str) -> dict[str, str]`, `copy_files(cur, table: str, stage: str, paths: list[str], force: bool) -> dict[str, int]` (path → rows_loaded), `record_manifest(cur, run_id, table, rows: list[tuple[path, etag, mode, rows_loaded]])`, `run_load(conn, run_id: str, stage: str = "RAW.ORGANIZER_STAGE", stage_url_prefix: str = "", tables=TABLES) -> dict[str, dict[str, int]]` (table → {"new": n, "restated": n, "skipped": n}). CLI: `uv run python -m pipeline.load --run-id <id> [--database LATAM_FIXTURE --stage RAW.FIXTURE_STAGE]`.

## Scope Limits

- Append the Snowflake calls and the CLI to `pipeline/load.py`. Don't change the unit 03 plan logic except to fix a bug, with a test.
- The live test and the first full load run only after the owner approves.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  `test_list_stage_files_returns_relative_paths`, `test_copy_and_manifest_roundtrip_on_fixture_db`
- A header-only (zero-row) partition file: COPY loads 0 rows and the manifest records `rows_loaded = 0` with mode `new`; the run continues. Pinned in Task 4 (`test_plan_loads_zero_row_file_is_new` and the fixture's `transactions_20260621.csv`).
- After the first load, RAW row counts per table are recorded in `progress-tracker.md` → Session Notes.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 4 (Loader Snowflake calls and first full load), lines 583–753
