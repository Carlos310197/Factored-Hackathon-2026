# 81 · Terraform `data` Root: Tables, Image Repositories, Shared Conventions

**Subsystem:** Deployment · **Depends on:** 77, 78 · **Reference:** deployment plan, Task 5 (intent and test cases only)

> *(Rewritten 2026-10-04: everything is Terraform.)* The reference task builds a CDK app. Use it only for resource settings and test intent, never for code structure. Conventions: `context/code-standards.md` → Deployment → Terraform.

## Goal

Create the `infra/terraform/data/` root: the six retained DynamoDB tables from the agent's specs, the ECR repositories for the agent and identity images, the SSM image parameters, and a by-name reference to the existing serving bucket.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Deployment Topology (Terraform roots, Deployed Infrastructure); Storage Model and Contracts → DynamoDB tables
- Deployment plan #3 and #5, and the 2026-10-04 decisions, in `progress-tracker.md` → Architecture Decisions
- `infra/terraform/app/` as the pattern to copy (backend block, provider, mock-provider tests)

## Requirements

- **Tables:** `lb-demo-checkpoints`, `lb-demo-disputes`, `lb-demo-handoffs`, `lb-demo-decision_records`, `lb-demo-sessions`, `lb-demo-conversation_messages`. Keys, indexes, TTL attributes and Streams exactly as `TABLE_SPECS`/`STREAM_TABLES` in `agent/src/bankagent/store/tables.py`. On-demand billing, point-in-time recovery on, `deletion_protection_enabled = true`, `lifecycle { prevent_destroy = true }`. Streams (`NEW_IMAGE`) on `conversation_messages`, `handoffs` and `decision_records` only.
- **One source for the table shapes:** `agent/scripts/export_table_specs.py` writes `infra/terraform/data/tables.json` from `TABLE_SPECS`; the root reads it with `jsondecode(file("tables.json"))` and builds the tables with `for_each`. A pytest drift test fails when the committed JSON differs from `TABLE_SPECS`.
- **Image repositories:** ECR `lb-demo-agent` and `lb-demo-identity` (immutable tags, scan on push, keep the last 10). They live here so they exist before the roots that run their images.
- **Image parameters:** SSM `String` parameters `/fh26/agent/image` and `/fh26/identity/image`, created with a placeholder value and `lifecycle { ignore_changes = [value] }`. The deploy workflow overwrites them; the consuming roots read them through `terraform_remote_state` or a data source.
- **Serving bucket:** `data "aws_s3_bucket"` for `latam-bank-serving-762197749808-use1` (Terraform `platform` owns it). This root attaches **no** bucket policy and changes nothing on it.
- **Outputs:** `table_names` (map), `table_arns` (map), `stream_arns` (map, three entries), `serving_bucket`, `serving_bucket_arn`, `agent_repository_url`, `identity_repository_url`, `agent_image_parameter`, `identity_image_parameter`.

## Implementation

### Files

- Create: `infra/terraform/data/main.tf` (backend key `data/terraform.tfstate`, provider, locals), `infra/terraform/data/tables.tf`, `infra/terraform/data/ecr.tf`, `infra/terraform/data/outputs.tf`, `infra/terraform/data/tables.json`, `infra/terraform/data/.terraform.lock.hcl`, `agent/scripts/export_table_specs.py`
- Test: `infra/terraform/data/tests/data.tftest.hcl`, `agent/tests/test_table_specs_export.py`

### Interfaces

- Consumes: `TABLE_SPECS` and `STREAM_TABLES` (agent-core Task 6, UI Task 2).
- Produces: the outputs above, read by the other roots with `data "terraform_remote_state" "data"` (bucket `fh26-tfstate-762197749808-use1`, key `data/terraform.tfstate`, region `us-east-1`).

## Scope Limits

- the `data` root, the JSON export script and their tests. No other root.
- `terraform apply` runs only from the deploy workflow on `main`, or with the owner's approval.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests first: the `.tftest.hcl` runs and the drift test are written and fail before the resources exist (CLAUDE.md → Repo Rules).
- `cd infra/terraform/data && terraform fmt -check && terraform init -backend=false && terraform validate && terraform test` passes; `cd agent && uv run pytest tests/test_table_specs_export.py -v` passes.
- `data.tftest.hcl` has these runs (mock provider, `command = plan`, because `prevent_destroy` would fail the test's teardown after an apply), carrying the reference task's intent:
  `six_tables_on_demand_with_pitr_and_deletion_protection`, `ttl_and_streams_match_the_specs`, `keys_and_indexes_match_tables_json`, `serving_bucket_is_read_not_managed`, `image_repositories_are_immutable_and_scanned`, `image_parameters_ignore_value_changes`.
- `test_table_specs_export.py`: `test_committed_json_matches_table_specs`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for resource settings and test intent:

`docs/reference/plans/2026-10-01-deployment.md`: Task 5 (CDK scaffold, configuration, cdk-nag and the `LbDemo-Data` stack), lines 1123–1481
