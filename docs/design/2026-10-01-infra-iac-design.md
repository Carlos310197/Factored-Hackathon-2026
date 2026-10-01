# Infrastructure as code: AWS + Snowflake via Terraform and GitHub Actions

Date: 2026-10-01 · Status: approved design, pending spec review · Owner: Andrés
Related: `docs/superpowers/specs/2026-09-26-data-pipeline-design.md` (§ Snowflake objects, serving contract), `docs/superpowers/plans/2026-09-26-data-pipeline.md` (Tasks 2 and 10 change, §7)

## 1. Goal

Every piece of infrastructure the data pipeline needs is code, applied by GitHub Actions, authenticated without stored secrets. Nothing is created by clicking in a console.

**Success:** a pull request that touches `infra/**` shows a `terraform plan`; merging to `main` applies it; the serving bucket, the Snowflake↔S3 integration, the GitHub deploy role and the Snowflake account objects exist and a smoke test proves the pipeline user can log in and list the serving stage.

**Out of scope:** Okta and IAM Identity Center (groups, assignments) — an Okta API token and lock-out risk for little gain; Carlos's agent infrastructure (DynamoDB, AgentCore) — he gets a sibling folder later; RAW and META tables (§5).

## 2. Facts

| Fact | Source |
|---|---|
| AWS account `762197749808`, admin via SSO profile `hackathon-sso` (Okta → IAM Identity Center) | `aws sts get-caller-identity`, 2026-10-01 |
| Snowflake account `RLQHFPF-AXC97788`, AWS **us-east-1**; local login = snow CLI connection `sbx` (password) | `snow connection test`, 2026-10-01 |
| Organizer bucket and Carlos's Bedrock/AgentCore are in **us-east-2** | dataset findings; agent-core spec §6 |
| Terraform 1.15.2 installed locally | `terraform version` |
| Snowflake provider (`snowflakedb/snowflake` ≥ 2.11) supports `authenticator = "WORKLOAD_IDENTITY"`, `workload_identity_provider = "AWS"`, reading ambient AWS credentials; stages need `preview_features_enabled` | provider docs; Classmethod WIF write-up |
| Snowflake user `WORKLOAD_IDENTITY = (TYPE = AWS, ARN = '<role arn>')` trusts an AWS role | Snowflake WIF docs |
| Team repo `Carlos310197/Factored-Hackathon-2026`, private, becomes public before submission | hackathon brief |

## 3. Trust chain

```
GitHub Actions job ──OIDC token──▶ AWS STS ──AssumeRoleWithWebIdentity──▶ role gha-deploy
role gha-deploy ──signed GetCallerIdentity──▶ Snowflake users TF_DEPLOY / PIPELINE_SVC
Snowflake storage integration ──AssumeRole (external id)──▶ role snowflake-serving ──▶ serving bucket
```

No Snowflake password, key or token is stored in GitHub. The only secrets in the system are the organizer's static S3 keys, which live in SSM Parameter Store and in the Snowflake stage definition (unchanged rule from the pipeline spec).

## 4. Layout

```
infra/terraform/
  bootstrap/    # applied ONCE from a laptop; state then migrated to S3
  platform/     # applied only by GitHub Actions
.github/workflows/infra.yml
```

Region: AWS resources in **us-east-2** (next to the organizer bucket and the agent runtime, which reads the serving bucket on every request). IAM is global. Snowflake stays in us-east-1; its daily export to the serving bucket crosses regions, accepted.

### 4.1 `bootstrap/` (local, one time)

Providers: `aws` (profile `hackathon-sso`), `snowflake` (local password login from the `sbx` connection, role ACCOUNTADMIN), `github` (token from `gh auth token`, account `andrezc98`).

| Resource | Detail |
|---|---|
| State bucket `fh26-tfstate-762197749808` | us-east-2, versioning on, SSE-S3, public access blocked. Backend uses `use_lockfile = true` (no DynamoDB). |
| `aws_iam_openid_connect_provider` | `token.actions.githubusercontent.com`, audience `sts.amazonaws.com` |
| Role `gha-deploy` | Trust: `sub` in `repo:Carlos310197/Factored-Hackathon-2026:ref:refs/heads/main` or `repo:Carlos310197/Factored-Hackathon-2026:pull_request`. Policy: `AdministratorAccess` (ponytail: one role for plan and apply; split a read-only plan role once the repo is public). |
| Snowflake user `TF_DEPLOY` | `TYPE = SERVICE`, `WORKLOAD_IDENTITY = (TYPE = AWS, ARN = gha-deploy)`, granted `SYSADMIN` and `SECURITYADMIN` (integration creation needs `ACCOUNTADMIN`: granted too, documented). |
| SSM `/fh26/organizer/aws_key_id`, `/fh26/organizer/aws_secret` | SecureString, values read from local `.env` at apply time; `lifecycle { ignore_changes = [value] }` so CI never needs `.env`. |
| GitHub repo variables | `AWS_ROLE_ARN`, `AWS_REGION`, `SNOWFLAKE_ORGANIZATION`, `SNOWFLAKE_ACCOUNT`, `TF_STATE_BUCKET`. Variables, not secrets: none is sensitive. |

After the first apply, `terraform init -migrate-state` moves bootstrap state into the state bucket under `bootstrap/terraform.tfstate`. Re-running bootstrap is only needed to change the trust chain itself.

### 4.2 `platform/` (CI only)

Providers: `aws` (ambient OIDC credentials), `snowflake` (`WORKLOAD_IDENTITY`/`AWS`, user `TF_DEPLOY`). State key `platform/terraform.tfstate`.

| Resource | Detail |
|---|---|
| Serving bucket `latam-bank-serving-762197749808` | us-east-2, private, versioning off, SSE-S3 |
| Snowflake objects | warehouse `WH_PIPELINE` (X-Small, auto-suspend 60); role `PIPELINE_ROLE`; databases `LATAM_BANK`, `LATAM_FIXTURE`, each with schemas `RAW`, `STAGING`, `CURATED`, `META`; grants to `PIPELINE_ROLE` |
| Storage integration `SERVING_INT` + role `snowflake-serving` | Role trust references the integration's `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID`; role name fixed up front so the integration can name it before the role exists. Policy: read/write/list on the serving bucket only. |
| File format `RAW.CSV_HEADER` | the pipeline plan's options (PARSE_HEADER, BOM skip, column-count mismatch off) |
| Stages | `RAW.ORGANIZER_STAGE` on `s3://<organizer>/data/` with keys from SSM data sources; `RAW.SERVING_STAGE` via `SERVING_INT`; `LATAM_FIXTURE.RAW.FIXTURE_STAGE` internal |
| User `PIPELINE_SVC` | `TYPE = SERVICE`, `WORKLOAD_IDENTITY = (TYPE = AWS, ARN = gha-deploy)`, default role `PIPELINE_ROLE`, warehouse `WH_PIPELINE` |

Organizer keys reach Terraform state through the stage resource. The state bucket is private and encrypted; that is the accepted exposure.

## 5. What stays out of Terraform

RAW and META tables stay in the pipeline's SQL scripts (`infra/snowflake/02_raw_tables.sql`, run by `pipeline/setup.py`): RAW tables use `ENABLE_SCHEMA_EVOLUTION`, so their columns change on purpose and Terraform would fight the drift.

## 6. Workflow `.github/workflows/infra.yml`

- Triggers: `pull_request` and `push` to `main`, both filtered to `infra/terraform/platform/**` and the workflow file.
- `permissions: id-token: write, contents: read, pull-requests: write`.
- Steps: checkout → `aws-actions/configure-aws-credentials` (role from `vars.AWS_ROLE_ARN`) → `hashicorp/setup-terraform` → `fmt -check` → `init` → `validate` → `plan -out`.
- PR: post the plan as a comment (update one comment, not one per push).
- `main`: `apply` the saved plan. `concurrency: infra-apply`, no cancel in progress.
- Failure: the job fails; nothing retries automatically (state lock released by Terraform; a stale lock file is removed with `terraform force-unlock`, documented).

## 7. Changes to the data pipeline plan

- Task 2 shrinks to: RAW and META table SQL, `pipeline/setup.py`, `tests/test_setup.py`. Account objects, stages, integration and `infra/aws/snowflake-serving-role.md` are deleted from it.
- Task 1's `connect.py` gains `workload_identity_provider = "AWS"` for CI (replacing the GitHub-token `OIDC` branch). Local dev keeps `SNOWFLAKE_CONNECTION_NAME`.
- Task 10: the pipeline workflow assumes `gha-deploy` and logs in as `PIPELINE_SVC`. dbt-snowflake WIF support is still unverified; fallback is a key pair for `PIPELINE_SVC` generated by Terraform (`tls_private_key`) and stored in SSM, still with nothing by hand.

## 8. Testing

- CI: `terraform fmt -check`, `validate`, `plan` on every PR.
- After apply: `pytest -m snowflake tests/test_infra_smoke.py` (run in the workflow after apply): `PIPELINE_SVC` logs in via WIF, `LIST @RAW.SERVING_STAGE` and `LIST @RAW.ORGANIZER_STAGE` succeed, `DESC INTEGRATION SERVING_INT` shows the expected role ARN.

## 9. Risks

- **Snowflake provider WIF + preview stage resources** may behave differently than documented. Fallback: create stages with `snowflake_execute` (raw SQL resource) in the same stack.
- **Bootstrap needs ACCOUNTADMIN password login** from Terraform; if the provider cannot use the `sbx` password connection, pass `SNOWFLAKE_PASSWORD` from the environment for that one run.
- **Trial expiry** (~2026-10-26) is after submission; no impact.
- **Repo rename** before submission changes the OIDC `sub` claim; the rename is a bootstrap re-apply with the new repo name.
