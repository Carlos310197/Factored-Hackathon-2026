# 06 · Staging Models: Typing, Dedup, Quarantine and Tests

**Subsystem:** Data pipeline · **Depends on:** 05 · **Reference:** pipeline plan, Task 6

## Goal

Type, normalize and deduplicate every source into STAGING, route bad rows to QUARANTINE, and add the schema, singular and unit tests.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### STAGING layer

*From pipeline §5.2 (the freshness and unexpected-column bullets are unit 05):*

- Cast every column to the data-dictionary type; `'True'/'False'` → boolean; `process_date` parsed from `_source_file`; event timestamps kept exactly as delivered.
- Normalization: sentiment `Positivo/Neutral/Negativo/Muy Negativo` → `Positive/Neutral/Negative/Very Negative`; empty strings → null; whitespace trimmed on keys.
- Dedup: `QUALIFY ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _loaded_at DESC, _file_row DESC) = 1`.

- Quarantine: `STAGING.QUARANTINE` (one table: `table_name`, `pk_value`, `reason`, `_source_file`, `_loaded_at`, `raw_row VARIANT`) receives rows that fail a cast, a not-null contract column, or an enum. Foreign-key violations are an error-level `relationships` test instead (referential integrity is 100% in the real drop, and a broken FK is a systemic problem, not a row problem). Staging models exclude quarantined rows. A singular test errors when quarantined rows exceed 1% of the rows loaded in that run.
- Tests (dbt schema tests): `unique` + `not_null` on every primary key; `not_null` on dictionary NOT NULL columns; `accepted_values` on `transaction_status`, `transaction_type`, `channel`, `case_type`, `status`, `priority`, `reason_category`, `product_type`, `product_status`; `relationships` on `customer_id` → customers and `product_id` → products. Warn-level tests: `not_null` on `duration_seconds`, `customer_detected_accent`, `claimed_amount`; a singular test flagging event date more than one day away from `process_date`.

## Implementation

### Files

- Create: `dbt/models/staging/typed_transactions.sql`, `typed_customers.sql`, `typed_products.sql`, `typed_complaints.sql`, `typed_interactions.sql`, `stg_transactions.sql`, `stg_customers.sql`, `stg_products.sql`, `stg_complaints.sql`, `stg_interactions.sql`, `quarantine.sql`, `dbt/models/staging/schema.yml`, `dbt/models/staging/unit_tests.yml`, `dbt/tests/assert_quarantine_rate.sql`, `dbt/tests/warn_event_vs_process_date.sql`

### Interfaces

- Consumes: sources from Task 5.
- Produces: `stg_*` views with typed contract columns (names as in spec §5.3, lowercase); `quarantine` table (`table_name`, `pk_value`, `reason`, `_source_file`, `_loaded_at`, `raw_row VARIANT`). Reason strings: `null:<col>`, `cast_failed:<col>`, `enum:<col>`.

## Scope Limits

- `dbt/models/staging/**` and the two singular tests. No curated marts.
- The dbt unit test is written first and must fail before the models exist.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- Duplicate keys inside one file (not across loads): the row with the highest `_file_row` wins. Pinned in Task 6's dbt unit test row `T3`.
- A timestamp in a different format (e.g. ISO `T` separator) would quarantine an entire partition and trip the 1% test rather than silently nulling. Pinned in Task 6's dbt unit test row `T4` (reason `cast_failed:transaction_date`).
- `dbt test --select test_type:unit` passes, then `dbt build --select staging` is green.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 6 (Staging models with typing, dedup, quarantine, tests and a dbt unit test), lines 1021–1416
