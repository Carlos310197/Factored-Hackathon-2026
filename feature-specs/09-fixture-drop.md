# 09 · Fixture Drop and the End-to-End Proof Test

**Subsystem:** Data pipeline · **Depends on:** 08 · **Reference:** pipeline plan, Task 9 · **[live]**

## Goal

Generate the labeled synthetic fixture drop and prove, end to end in `LATAM_FIXTURE`, that new partitions, restatements, duplicates, new columns and bad types are handled.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Fixture drop and tests · pipeline §8

A Snowflake internal stage `LATAM_FIXTURE.RAW.FIXTURE_STAGE` (uploaded with `PUT` by the test, no AWS credentials needed) mirrors the organizer layout for `transactions` only; the generator and its README in `fixtures/` label it synthetic:
- a new partition `year=2026/month=06/day=18/transactions_20260618.csv` (200 rows);
- a restated `transactions_20260617.csv` with 3 rows whose `transaction_status` changed and 5 exact duplicate rows appended;
- a file with an extra column `merchant_country`;
- a file with one row whose `amount` is `N/A`.

`tests/test_fixture_drop.py` (pytest, one file): points the loader at `fixture_stage` and database `LATAM_FIXTURE`, runs `load` then `dbt build --target fixture`, then asserts via SQL: the new partition's rows are present; the 5 duplicates collapse to unique keys; the 3 changed rows show the restated status; `merchant_country` exists in RAW, is absent from staging, and the unexpected-column test is recorded as `warn`; the `N/A` row is in `QUARANTINE` with reason `cast_failed:amount`; the run manifest records modes `new` and `restated`; the pointer's `run_id` advanced. The test runs in CI on every pull request.

Other checks: dbt schema and singular tests (5.2), and a unit test for the loader's ETag comparison.

## Implementation

### Files

- Create: `fixtures/README.md`, `fixtures/make_fixture.py`, `tests/test_fixture_drop.py`, `tests/test_make_fixture.py`

### Interfaces

- Consumes: loader CLI functions (`run_load`), dbt `fixture` target, `run_export`, `dq_results`.
- Produces: `fixtures.make_fixture.write_phase(out_dir: Path, phase: int) -> list[Path]` writing files under `out_dir/transactions/year=2026/month=06/day=DD/transactions_202606DD.csv`. Phase 1: day 17 original (20 rows). Phase 2: day 17 restated (3 rows changed to `Reversed` + 5 duplicate rows appended), day 18 new (10 rows), day 19 with extra column `merchant_country`, day 20 with one `amount = N/A`, day 21 header-only.

## Scope Limits

- `fixtures/` and the two tests. No changes to production models except bug fixes with a test.
- The fixture is labeled synthetic in its README and generator.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  `test_phase1_and_phase2_shapes`, `test_fixture_drop_end_to_end`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 9 (Fixture drop generator and the end-to-end proof test), lines 1885–2112
