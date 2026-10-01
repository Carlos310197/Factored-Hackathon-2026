# 89 · CI/CD: Reusable Tests, PR Diff with Stateful Guard, Deploy → Web → Verify

**Subsystem:** Deployment · **Depends on:** 88 · **Reference:** deployment plan, Task 13

## Goal

Write the app workflows, the stateful-replacement guard, the Amplify release script and the post-deploy health check.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #13 (workflow names) in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Workflows · deployment §5.1

`.github/workflows/pipeline.yml` (the data pipeline) stays as specced and runs independently.

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | pull request | `agent-test`: uv pytest, offline. `web-test`: Vitest, the `onSubscribe` `EvaluateCode` tests, Playwright with mocked backends, the axe scan. `infra-check`: infra pytest (§8), `cdk synth` with cdk-nag, `cdk diff` using the diff role, posted as a PR comment, then the stateful-replacement guard (§7). |
| `deploy.yml` | push to `main`, `paths-ignore: docs/**`; `concurrency: deploy-demo` with `cancel-in-progress: false` | `test` (same as CI) → `deploy` on `ubuntu-24.04-arm` (native ARM64 image build, no QEMU): `cdk deploy --all --require-approval never` → `web`: `aws amplify start-job --branch-name main --job-type RELEASE`, then poll until it finishes → `verify` (§5.3) |

### Ordering and traceability · deployment §5.2

- Amplify auto-build is off, so the web never builds against stale environment variables. It is built only after CDK has updated them.
- The agent image tag and the runtime's `GIT_SHA` environment variable are the commit SHA. `app.py` writes `GIT_SHA` into every decision record's versions. The evaluation report reads it as "agent git SHA" (evaluation spec §6, item 1).
- The web build gets `NEXT_PUBLIC_GIT_SHA` and shows it in the footer of staff pages.

### `verify` job · deployment §5.3

A health check, not a functional smoke test:

- the issuer's `/.well-known/openid-configuration` returns 200 and its JWKS has exactly one key;
- `GetAgentRuntime` reports status `READY`, and the `live` endpoint points at the version just deployed;
- the Amplify job ended `SUCCEED`, and `GET /login` returns 200.

Any failure marks the deploy red. There's no automatic rollback (§7).

## Implementation

### Files

- Create: `.github/workflows/app-tests.yml`, `.github/workflows/app-ci.yml`, `.github/workflows/deploy.yml`, `infra/scripts/__init__.py`, `infra/scripts/stateful_guard.py`, `infra/scripts/verify.py`, `infra/scripts/amplify_release.sh`
- Test: `infra/tests/test_guard.py`, `infra/tests/test_verify.py`, `infra/tests/test_workflows.py`

### Interfaces

- Consumes: the stack names and outputs (`LbDemo-Identity.Issuer`, `LbDemo-Agent.RuntimeId`, `LbDemo-Web.AppId` and `.AppUrl`); the repository variables from Task 12.
- Produces:
  - `stateful_guard.findings(text, stack="LbDemo-Data") -> list[str]` and `main(argv) -> int`;
  - `verify.check_identity(issuer, fetch) -> list[str]`, `check_runtime(control, runtime_id, sha) -> list[str]`, `check_web(url, status) -> list[str]` and `main(argv, control=None, fetch=…, status=…) -> int`;
  - `amplify_release.sh <appId>`.

## Scope Limits

- three workflow files, the guard, the release script and the verify script, with their tests. Nothing is pushed or run against AWS in this task.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_guard.py tests/test_verify.py tests/test_workflows.py -v` (in `infra/`) passes.
- The reference task's tests exist and pass:
  `test_safe_diff_passes_even_when_other_stacks_replace_things`, `test_guard_flags_replacement_with_ansi_codes`, `test_main_exit_codes`, `test_identity_checks`, `test_runtime_checks`, `test_web_check`, `test_main_reads_outputs_and_fails_on_any_problem`, `test_deploy_jobs_are_chained_and_never_cancelled`, `test_deploy_runs_cdk_on_arm_with_the_commit_sha`, `test_every_aws_job_uses_oidc_and_no_stored_keys`, `test_pr_workflow_diffs_with_the_read_only_role_then_guards`, `test_tests_workflow_is_reusable_and_covers_all_four_suites`
- **A `cdk diff` for `LbDemo-Data` that replaces or removes a table, printed with ANSI colour codes** (as the CDK CLI does in CI). Expected: the guard exits non-zero and names the resource. Pinned in Task 13 (`test_guard_flags_replacement_with_ansi_codes`).
- **A deploy that fails mid-way** (for example `LbDemo-Agent` fails after `LbDemo-Identity` updated). Expected: the Amplify build and `verify` never start, and a later push isn't cancelled mid-deploy. Pinned in Task 13 (`test_deploy_jobs_are_chained_and_never_cancelled`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 13 (CI/CD: reusable tests, PR diff with the stateful guard, deploy → web → verify), lines 2982–3532
