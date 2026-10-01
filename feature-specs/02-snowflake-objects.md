# 02 · Snowflake Account Objects, Stages and RAW Tables

**Subsystem:** Data pipeline · **Depends on:** 01 · **Reference:** pipeline plan, Task 2 · **[live]**

## Goal

Create the warehouse, databases, schemas, role, stages, storage integration and all-text RAW tables that the loader writes to.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### RAW layer

*From pipeline §5.1:*

One table per source with every source column as `VARCHAR`, plus `_source_file`, `_file_row`, `_file_last_modified`, and `_loaded_at`, filled by the COPY option `INCLUDE_METADATA = (_source_file = METADATA$FILENAME, _file_row = METADATA$FILE_ROW_NUMBER, _file_last_modified = METADATA$FILE_LAST_MODIFIED, _loaded_at = METADATA$START_SCAN_TIME)`. Append-only. File format `CSV, PARSE_HEADER = TRUE, ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE, SKIP_BYTE_ORDER_MARK = TRUE`; loads use `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` (required by `INCLUDE_METADATA`) and the RAW tables have `ENABLE_SCHEMA_EVOLUTION = TRUE`, so a new source column is added to RAW instead of failing the load. `ON_ERROR = ABORT_STATEMENT` so a partition lands whole or not at all. Snowflake's 64-day load history makes re-running the same file a no-op; `FORCE = TRUE` is used only for files the loader has identified as changed.

## Implementation

### Files

- Create: `infra/snowflake/00_account.sql`, `infra/snowflake/01_integrations.sql`, `infra/snowflake/02_raw_tables.sql`, `infra/aws/snowflake-serving-role.md`, `pipeline/setup.py`, `tests/test_setup.py`

### Interfaces

- Consumes: `pipeline.connect.get_connection`.
- Produces: `pipeline.setup.render(sql: str, params: Mapping[str, str]) -> str` (replaces `${NAME}` tokens; raises `KeyError` on a missing one) and `pipeline.setup.run_script(conn, path, params)` (splits on `;` at line ends and executes each statement). Snowflake objects: `WH_PIPELINE`, `PIPELINE_ROLE`, `PIPELINE_SVC` (WIF user), databases `LATAM_BANK`/`LATAM_FIXTURE` with schemas `RAW`, `STAGING`, `CURATED`, `META`; `RAW.ORGANIZER_STAGE`, `RAW.SERVING_STAGE`, `RAW.FIXTURE_STAGE` (internal, in `LATAM_FIXTURE`), file format `RAW.CSV_HEADER`; RAW tables `CUSTOMERS`, `PRODUCTS`, `TRANSACTIONS`, `COMPLAINTS`, `INTERACTIONS`; `META.RUN_MANIFEST`, `META.DQ_RESULTS`.

### Notes

- The serving bucket and the Snowflake role `snowflake-serving-writer` are created **by hand** here; the deployment units reference them and don't create them (deployment plan #3).

## Scope Limits

- DDL scripts, the setup runner and the AWS-role note. No loader logic.
- Organizer keys live only in the stage definition (from `.env` at run time). Never commit them.
- Running the scripts against Snowflake is an owner-approved step.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  `test_render_substitutes_tokens`, `test_render_missing_token_raises`, `test_split_statements_ignores_comments_and_blank`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 2 (Snowflake account objects, stages, and RAW tables), lines 198–455
