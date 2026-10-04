# 88 · Bootstrap: Secrets, Plan Role, Transaction Search, `seed_demo.py`

**Subsystem:** Deployment · **Depends on:** 87 · **Reference:** deployment plan, Task 12 (intent and test cases only)

> *(Rewritten 2026-10-04: everything is Terraform.)* The one-time bootstrap already exists as the Terraform root `infra/terraform/bootstrap/` (state bucket, GitHub OIDC provider, `gha-deploy`, `TF_DEPLOY`, organizer keys), applied from a laptop with `apply.sh`. This unit extends that root and its script; there's no CDK bootstrap, no `GitHubStack` and no `infra/bootstrap.sh`.

## Goal

Add the app's secrets, a read-only plan role for pull requests and CloudWatch Transaction Search to the bootstrap root, and write the demo-identities seeder.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Deployment Topology (Deployed Infrastructure); Access Controls and Secrets
- Deployment plan #12 in `progress-tracker.md` → Architecture Decisions
- `infra/terraform/bootstrap/` (`main.tf`, `apply.sh`, `tests/bootstrap.tftest.hcl`)

## Requirements

*From deployment §5.4, as amended for Terraform:*

The bootstrap runs once from the owner's laptop with admin credentials (`infra/terraform/bootstrap/apply.sh`, SSO profile `hackathon-sso`). After it, every change ships through GitHub Actions.

1. ~~`cdk bootstrap`~~: not needed. The Terraform state bucket already exists.
2. Enable CloudWatch Transaction Search (for AgentCore Observability): `aws_cloudwatch_log_resource_policy` for X-Ray plus `aws_xray_trace_segment_destination`, or the AWS CLI call `aws xray update-trace-segment-destination --destination CloudWatchLogs` in `apply.sh` if the pinned provider lacks it (unit 77 records which).
3. GitHub OIDC provider and `gha-deploy`: already exist. **Add** role `gha-plan`: trusted by `repo:Carlos310197/Factored-Hackathon-2026:pull_request` only, `ReadOnlyAccess` plus what `terraform plan` needs on the state bucket (read, and write only on `*.tflock` lock files), with a Snowflake read-only user for `platform` plans. `gha-deploy`'s trust then narrows to `ref:refs/heads/main`.
4. Secrets: `aws_secretsmanager_secret` containers `lb-demo/jev` and `lb-demo/idp-signing-key` with **no** `aws_secretsmanager_secret_version` in Terraform, so values never reach state. `infra/terraform/bootstrap/put-secrets.sh` sets them with `aws secretsmanager put-secret-value`, reading each value with a silent prompt (the signing key is generated locally with `openssl` and piped in), never echoed. Both secrets have `prevent_destroy`.
5. First deploy: from the laptop, run the deploy workflow's steps once (`infra/scripts/deploy.sh`, unit 89), or push to `main`.
6. ~~Snowflake storage integration~~: already done by Terraform `platform/` (`SI_SERVING`, `snowflake-serving`); `infra.yml`'s smoke test checks the stage after every apply.
7. `agent/scripts/seed_demo.py`: checks that the tables are empty and that the scenario identities config (UI §4.9) resolves to customers present in the serving set, then uploads `config/demo_users.yaml` to `s3://<serving bucket>/identity/demo_users.yaml` (deployment plan #4).

## Implementation

### Files

- Create: `infra/terraform/bootstrap/secrets.tf`, `infra/terraform/bootstrap/plan_role.tf`, `infra/terraform/bootstrap/observability.tf`, `infra/terraform/bootstrap/put-secrets.sh`, `agent/scripts/seed_demo.py`
- Modify: `infra/terraform/bootstrap/main.tf` (narrow `gha-deploy` trust to `main`), `infra/terraform/bootstrap/apply.sh`, `infra/terraform/platform/snowflake.tf` (the read-only Snowflake user for `gha-plan`), `.github/workflows/infra.yml` (PR jobs assume `gha-plan`)
- Test: `infra/terraform/bootstrap/tests/bootstrap.tftest.hcl` (extended), `agent/tests/test_seed_demo.py`, `tests/test_infra_workflow.py` (extended)

### Interfaces

- Consumes: `load_users` (agent-core Task 3); `ServingData(base_uri, region).pointer()` and `.query(run_id, table, where, params)` (agent-core Task 5); `TABLE_SPECS`; the `data` root's `table_names`.
- Produces:
  - bootstrap outputs `deploy_role_arn`, `plan_role_arn`, `jev_secret_arn`, `idp_signing_secret_arn` (the non-secret ARNs are written into the workflow files, as today);
  - `seed_demo.check_label(text) -> None`;
  - `seed_demo.missing_customers(users, has_customer) -> list[str]`;
  - `seed_demo.main(argv) -> int`.

## Scope Limits

- the bootstrap root, its scripts and the seeder. The scripts are written and tested here; applying the bootstrap and running them happens in unit 90, with the owner's approval.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests first (CLAUDE.md → Repo Rules).
- `terraform test` passes in `infra/terraform/bootstrap/`; `cd agent && uv run pytest tests/test_seed_demo.py -v` and `uv run pytest tests/test_infra_workflow.py -v` pass; `bash -n` passes on both scripts.
- Runs and tests carrying the reference task's intent: `deploy_role_trusts_only_main_of_this_repo`, `plan_role_trusts_pull_requests_and_is_read_only`, `secrets_have_no_version_in_state`, `existing_oidc_provider_is_reused`; `test_label_header_required`, `test_missing_customers_skips_staff_and_reports_unknown_ids`; `test_pr_jobs_use_the_plan_role`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for the seeder's code and the bootstrap's intent:

`docs/reference/plans/2026-10-01-deployment.md`: Task 12 (Bootstrap: GitHub OIDC stack, `bootstrap.sh` and `seed_demo.py`), lines 2666–2978
