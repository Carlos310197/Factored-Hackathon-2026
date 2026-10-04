# 83 · Terraform `agent` Root: the AgentCore Runtime

**Subsystem:** Deployment · **Depends on:** 82, 79 · **Reference:** deployment plan, Task 7 (intent and test cases only)

> *(Rewritten 2026-10-04: everything is Terraform.)* The reference task builds a CDK stack. Use it only for resource settings and test intent. Conventions: `context/code-standards.md` → Deployment → Terraform.

## Goal

Define the least-privilege execution role, the AgentCore runtime with its JWT authorizer, and the `live` endpoint.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #11 (Bedrock signing service from unit 77) in `progress-tracker.md` → Architecture Decisions
- Unit 77's result for "AgentCore runtime in Terraform"

## Requirements

- **Runtime** `lb_demo_agent`: container from the `/fh26/agent/image` parameter (ARM64 image, built by the deploy workflow), network mode `PUBLIC`, inbound `custom_jwt_authorizer` with the identity root's discovery URL (`<issuer>/.well-known/openid-configuration`) and allowed audience `bankagent`, request header allowlist `["Authorization"]` (agent-core plan #2).
- **Resource choice** (settled in unit 77): `aws_bedrockagentcore_agent_runtime` and `aws_bedrockagentcore_agent_runtime_endpoint` from `hashicorp/aws`. If the pinned provider lacks them or the authorizer or header allowlist arguments, use `awscc_bedrockagentcore_runtime` (Cloud Control provider). Last resort: `terraform_data` with `local-exec` calling `aws bedrock-agentcore-control create/update-agent-runtime`, with the runtime id kept as an output.
- **Endpoint** `live`, pointing at the runtime version this apply produced.
- **Environment:** `TABLE_PREFIX=lb-demo-`, `SERVING_URI=s3://<serving bucket>/serving/`, `IDP_ISSUER`, `IDP_AUDIENCE=bankagent`, the model config, `GIT_SHA` (the image tag), `JEV_SECRET_ID=lb-demo/jev`, plus `OTEL_*` for ADOT. No secret values.
- **Execution role** (trust: `bedrock-agentcore.amazonaws.com` with `aws:SourceAccount` = this account): `bedrock:InvokeModel*` on the two configured model or inference-profile ARNs; `s3:GetObject` and `s3:ListBucket` on `serving/*`; DynamoDB item operations on the six tables and their indexes, no `Scan`, no `DeleteItem` on `disputes` or `handoffs`; `secretsmanager:GetSecretValue` on `lb-demo/jev`; ECR pull from `lb-demo-agent`; logs, X-Ray and `cloudwatch:PutMetricData` with the condition namespace `LatamBank`.
- **Outputs:** `runtime_id`, `runtime_arn`, `invoke_url` (`https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/<url-encoded ARN>/invocations?qualifier=live`).

## Implementation

### Files

- Create: `infra/terraform/agent/main.tf` (backend key `agent/terraform.tfstate`, providers, remote state of `data` and `identity`), `infra/terraform/agent/runtime.tf`, `infra/terraform/agent/iam.tf`, `infra/terraform/agent/outputs.tf`, `.terraform.lock.hcl`
- Test: `infra/terraform/agent/tests/agent.tftest.hcl`

### Interfaces

- Consumes: `data` outputs (tables, bucket, `agent_image_parameter`), `identity.issuer`, `agent/Dockerfile` (unit 79), unit 77 results (Steps 1, 2, 3 and 7).
- Produces: the outputs above, read by `app` (`invoke_url`), `ops` and the `verify` job.

## Scope Limits

- the execution role, the runtime, the `live` endpoint and log retention. Building and pushing the image is the deploy workflow's job (unit 89).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests first (CLAUDE.md → Repo Rules).
- `terraform fmt -check && terraform init -backend=false && terraform validate && terraform test` passes in `infra/terraform/agent/`.
- `agent.tftest.hcl` runs: `runtime_shape`, `runtime_environment_has_no_secret_values`, `live_endpoint_tracks_the_new_version`, `execution_role_trusts_agentcore_in_this_account`, `least_privilege_data_access`, `invoke_url_uses_the_live_qualifier`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for resource settings and test intent:

`docs/reference/plans/2026-10-01-deployment.md`: Task 7 (`LbDemo-Agent`: the AgentCore Runtime), lines 1623–1862
