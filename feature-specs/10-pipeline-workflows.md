# 10 · GitHub Actions: CI and the Scheduled Pipeline

**Subsystem:** Data pipeline · **Depends on:** 09 · **Reference:** pipeline plan, Task 10 · **[live]**

## Goal

Run the fixture proof on every pull request, and run load → dbt build → export daily and on every push to `main`.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract
- `context/architecture-context.md` → Access Controls and Secrets → Access and secrets · pipeline §7 (GitHub OIDC → Snowflake)

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `.github/workflows/ci.yml`, `.github/workflows/pipeline.yml`

### Interfaces

- Consumes: CLIs from Tasks 4, 7, 8; dbt `ci` target; Snowflake user `PIPELINE_SVC` (WIF subject `repo:<org>/<repo>:ref:refs/heads/main`).
- Repository secrets: `SNOWFLAKE_PRIVATE_KEY` (contents of `pipeline_rsa_key.p8`, used until WIF is confirmed for dbt). Repository variables: `SNOWFLAKE_ACCOUNT`, `SERVING_BUCKET`.

## Scope Limits

- `.github/workflows/ci.yml` and `pipeline.yml` only. The app's workflows are `app-*.yml` and `deploy.yml` (deployment plan #13).
- Try GitHub OIDC for the Python steps; keep the key pair only where dbt needs it.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- A push shows both workflows green on GitHub.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 10 (GitHub Actions: CI on pull requests, scheduled pipeline on main), lines 2116–2248
