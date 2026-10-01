# 05 · dbt Project, Sources with Freshness, Unexpected-Column Test

**Subsystem:** Data pipeline · **Depends on:** 04 · **Reference:** pipeline plan, Task 5

## Goal

Create the dbt project with source definitions that carry the freshness policy, plus the warn-level test that surfaces unexpected RAW columns.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From pipeline §5.2 (the parts this unit owns; the rest is unit 06):*

- Only contract columns are selected; an unexpected column in RAW is surfaced by a warn-level singular test that compares `INFORMATION_SCHEMA.COLUMNS` to the contract.

- Source freshness (`sources.yml`, `loaded_at_field: _loaded_at`): warn after 2 days, error after 7 days. This is the written freshness policy.

## Implementation

### Files

- Create: `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/models/staging/sources.yml`, `dbt/tests/warn_unexpected_columns.sql`, `dbt/.gitignore`

### Interfaces

- Produces: dbt profile `latam_bank` with targets `dev` (database `LATAM_BANK`, key pair), `ci` (same, env-driven), `fixture` (database `LATAM_FIXTURE`); sources `raw.customers|products|transactions|complaints|interactions` and `meta.run_manifest|dq_results`. Commands: `cd dbt && uv run dbt build --target dev`.

## Scope Limits

- `dbt_project.yml`, `profiles.yml`, `sources.yml` and the singular warn test. No models yet.
- The profile reads credentials from the environment only.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 5 (dbt project, sources with freshness, and the unexpected-column test), lines 757–1017
