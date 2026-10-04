# 89 · CI/CD: Reusable Tests, PR Plans with Stateful Guard, Deploy → Verify

**Subsystem:** Deployment · **Depends on:** 88 · **Reference:** deployment plan, Task 13 (intent and test cases only)

> *(Rewritten 2026-10-04: everything is Terraform; the web is on ECS Fargate Spot.)* `cdk synth`/`cdk diff`/`cdk deploy` become `terraform plan`/`apply` per root, cdk-nag becomes `trivy config` (unit 87), and the Amplify release becomes an image push plus an ECS rollout.

## Goal

Write the app workflows, the stateful-replacement guard over Terraform plans, the deploy script and the post-deploy health check.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #13 (workflow names) in `progress-tracker.md` → Architecture Decisions
- `.github/workflows/infra.yml` and `tests/test_infra_workflow.py` (the existing pattern)

## Requirements

*From deployment §5.1–5.3, as amended for Terraform:*

### Workflows

`.github/workflows/pipeline.yml` (the data pipeline) stays as built and runs independently.

| Workflow | Trigger | Jobs |
|---|---|---|
| `infra.yml` (exists, extended) | pull request on `infra/terraform/**`; push to `main` | **PR:** for every root (`platform`, `data`, `identity`, `agent`, `realtime`, `app`, `ops`): `terraform fmt -check`, `validate`, `test` (offline, mocked), then `terraform plan` with `gha-plan`, posted as a PR comment; the stateful guard over `data`'s plan JSON. `trivy config` once. **Push to `main`:** apply `platform` only, as today. `bootstrap` is never applied from CI. |
| `app-tests.yml` (reusable) | `workflow_call` | `agent-test`: uv pytest, offline. `web-test`: Vitest, the `onSubscribe` `EvaluateCode` tests, Playwright with mocked backends, the axe scan. `realtime-test`: `npm ci && npm run build && npm test` in `infra/realtime/`. `infra-test`: root `uv run pytest` (Terraform source checks, guard, verify, workflows). |
| `app-ci.yml` | pull request | calls `app-tests.yml` |
| `deploy.yml` | push to `main`, `paths-ignore: docs/**`; `concurrency: deploy-demo` with `cancel-in-progress: false` | `test` (calls `app-tests.yml`) → `images`: agent and identity on `ubuntu-24.04-arm` (native ARM64, no QEMU), web on `ubuntu-latest` (amd64); each pushed to ECR as `:<git sha>` and its `/fh26/<name>/image` parameter overwritten → `apply`: `terraform apply` in order `data` (plan saved, guard, then apply that plan) → `identity` → `agent` → `realtime` (after `npm run build`) → `app` (waits for ECS steady state) → `ops` → `verify` |

`app` moves out of `infra.yml`'s apply matrix into `deploy.yml`, so one workflow owns each root's applies.

### Ordering and traceability

- Each root applies only after the roots it reads through remote state, so no service starts against stale outputs. Images are pushed before any root that runs them is applied.
- The agent image tag and the runtime's `GIT_SHA` environment variable are the commit SHA. `app.py` writes `GIT_SHA` into every decision record's versions. The evaluation report reads it as "agent git SHA" (evaluation spec §6, item 1).
- The web image gets `NEXT_PUBLIC_GIT_SHA` at build time and shows it in the footer of staff pages.

### `verify` job

A health check, not a functional smoke test:

- the issuer's `/.well-known/openid-configuration` returns 200 and its JWKS has exactly one key;
- `GetAgentRuntime` reports status `READY`, and the `live` endpoint points at the version just deployed;
- the ECS service `latam-bank-web` is steady with one running task whose task definition uses the image tag of this SHA. `GET /login` returning 200 is checked through the demo-day ALB once it exists; until then the runner's IP isn't in `allowed_cidrs`, so the container health check stands in.

Any failure marks the deploy red. There's no automatic rollback (§7); the ECS circuit breaker still rolls back a web task that never gets healthy.

### Stateful guard

`infra/scripts/stateful_guard.py` reads `terraform show -json <plan>` and fails when any `aws_dynamodb_table` has `delete` in its `change.actions` (a destroy or a replace), naming the resource address. It runs on PR plans and before the `data` apply in `deploy.yml`. `prevent_destroy` and table deletion protection stay as the backstops.

## Implementation

### Files

- Create: `.github/workflows/app-tests.yml`, `.github/workflows/app-ci.yml`, `.github/workflows/deploy.yml`, `infra/scripts/stateful_guard.py`, `infra/scripts/verify.py`, `infra/scripts/deploy.sh` (the same steps as the `images` and `apply` jobs, for the laptop's first deploy)
- Modify: `.github/workflows/infra.yml` (all roots in the PR matrix, plans with `gha-plan`, guard, trivy; `app` removed from the apply matrix)
- Test: `tests/test_stateful_guard.py`, `tests/test_verify.py`, `tests/test_app_workflows.py`, `tests/test_infra_workflow.py` (extended)

### Interfaces

- Consumes: each root's outputs (`identity.issuer`, `agent.runtime_id`, `app.cluster`, `app.service`, `app.ecr_repository_url`, `data.agent_repository_url`, `data.identity_repository_url`); the role ARNs from unit 88.
- Produces:
  - `stateful_guard.findings(plan_json: dict) -> list[str]` and `main(argv) -> int`;
  - `verify.check_identity(issuer, fetch) -> list[str]`, `check_runtime(control, runtime_id, sha) -> list[str]`, `check_web(ecs, cluster, service, sha) -> list[str]` and `main(argv, control=None, ecs=None, fetch=…) -> int`;
  - `deploy.sh <git sha>`.

## Scope Limits

- the workflow files, the guard, the deploy script and the verify script, with their tests. Nothing is pushed or run against AWS in this unit.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests first (CLAUDE.md → Repo Rules).
- `uv run pytest tests/test_stateful_guard.py tests/test_verify.py tests/test_app_workflows.py tests/test_infra_workflow.py -v` passes.
- Tests carrying the reference task's intent: `test_safe_plan_passes_even_when_other_roots_replace_things`, `test_guard_flags_table_replacement`, `test_main_exit_codes`, `test_identity_checks`, `test_runtime_checks`, `test_web_check`, `test_main_reads_outputs_and_fails_on_any_problem`, `test_deploy_jobs_are_chained_and_never_cancelled`, `test_deploy_builds_arm_images_on_arm_with_the_commit_sha`, `test_roots_apply_in_dependency_order`, `test_every_aws_job_uses_oidc_and_no_stored_keys`, `test_pr_plans_use_the_read_only_role_then_guard`, `test_tests_workflow_is_reusable_and_covers_all_four_suites`, `test_app_is_applied_only_by_deploy`.
- **A plan for `data` that replaces or removes a table.** Expected: the guard exits non-zero and names the resource address. Pinned in `test_guard_flags_table_replacement`.
- **A deploy that fails mid-way** (for example the `agent` apply fails after `identity` applied). Expected: `app`, `ops` and `verify` never start, and a later push isn't cancelled mid-deploy. Pinned in `test_deploy_jobs_are_chained_and_never_cancelled`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for the verify checks and test intent:

`docs/reference/plans/2026-10-01-deployment.md`: Task 13 (CI/CD: reusable tests, PR diff with the stateful guard, deploy → web → verify), lines 2982–3532
