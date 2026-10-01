# 88 · Bootstrap: GitHub OIDC Stack, `bootstrap.sh`, `seed_demo.py`

**Subsystem:** Deployment · **Depends on:** 87 · **Reference:** deployment plan, Task 12

## Goal

Write the one-time account bootstrap (OIDC roles, secrets, first deploy, Snowflake check) and the demo-identities seeder.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #12 in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### One-time bootstrap (`infra/bootstrap.sh` plus README) · deployment §5.4

The bootstrap runs once from the owner's laptop with admin credentials. After it, every change ships through `deploy.yml`.

1. `cdk bootstrap aws://<account>/us-east-2`.
2. Enable CloudWatch Transaction Search (for AgentCore Observability).
3. Create the GitHub OIDC provider and the deploy and diff roles (a small `Bootstrap` CDK stack deployed only by this script).
4. Create the three secrets. Values are read with a silent prompt and never echoed.
5. First `cdk deploy --all`, then the Amplify job, from the laptop.
6. Snowflake:
   1. `CREATE STORAGE INTEGRATION SI_SERVING` with the role ARN from the `Data` stack output.
   2. `DESC INTEGRATION` → put its IAM user ARN and external ID into `cdk.context.json`.
   3. Redeploy `Data`, which narrows the role's trust to that principal and external ID.
7. `scripts/seed_demo.py`: checks that the tables are empty and that the scenario identities config (UI §4.9) resolves to customers present in the serving set.

## Implementation

### Files

- Create: `infra/lb_infra/stacks/github.py`, `infra/bootstrap.sh`, `agent/scripts/seed_demo.py`
- Modify: `infra/app.py`
- Test: `infra/tests/test_github.py`, `agent/tests/test_seed_demo.py`

### Interfaces

- Consumes: `Config`; the CDK bootstrap qualifier `hnb659fds` (the default); `load_users` (agent-core Task 3); `ServingData(base_uri, region).pointer()` and `.query(run_id, table, where, params)` (agent-core Task 5); `TABLE_SPECS`, `table_name`.
- Produces:
  - `GitHubStack` with outputs `DeployRoleArn` and `DiffRoleArn`, synthesized only with `-c bootstrap=1`;
  - the repository variables `AWS_DEPLOY_ROLE_ARN` and `AWS_DIFF_ROLE_ARN`;
  - `seed_demo.check_label(text) -> None`;
  - `seed_demo.missing_customers(users, has_customer) -> list[str]`;
  - `seed_demo.main(argv) -> int`.

## Scope Limits

- the one-time account setup and the demo-identities upload. The scripts are written and tested here; they're **run** in Task 14.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_github.py -v` (in `infra/`) and `uv run pytest tests/test_seed_demo.py -v` (in `agent/`) pass, and `bash -n infra/bootstrap.sh` reports no syntax errors.
- The reference task's tests exist and pass:
  `test_deploy_role_trusts_only_main_of_this_repo`, `test_diff_role_trusts_pull_requests_and_can_only_assume_the_lookup_role`, `test_deploy_role_assumes_cdk_roles_and_reads_release_status`, `test_existing_oidc_provider_is_reused`, `test_label_header_required`, `test_missing_customers_skips_staff_and_reports_unknown_ids`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 12 (Bootstrap: GitHub OIDC stack, `bootstrap.sh` and `seed_demo.py`), lines 2666–2978
