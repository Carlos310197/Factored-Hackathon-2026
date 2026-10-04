# 82 · Terraform `identity` Root: IdP Lambda Behind an HTTP API

**Subsystem:** Deployment · **Depends on:** 81, 80 · **Reference:** deployment plan, Task 6 (intent and test cases only)

> *(Rewritten 2026-10-04: everything is Terraform.)* The reference task builds a CDK stack. Use it only for resource settings and test intent. Conventions: `context/code-standards.md` → Deployment → Terraform.

## Goal

Deploy the identity Lambda (container image) behind a throttled HTTP API and output the issuer URL.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #4 in `progress-tracker.md` → Architecture Decisions

## Requirements

- **Lambda** `lb-demo-identity`: `package_type = "Image"`, `architectures = ["arm64"]`, image from the `/fh26/identity/image` parameter (unit 81), memory 512 MB, timeout 10 s, active X-Ray tracing. Environment: `IDP_ISSUER`, `IDP_AUDIENCE=bankagent`, `IDP_KID`, `IDP_SIGNING_SECRET_ID=lb-demo/idp-signing-key`, `DEMO_USERS_S3_URI=s3://<serving bucket>/identity/demo_users.yaml`, `IDP_DEMO_MODE=1`. No secret values in the environment.
- **HTTP API** `lb-demo-identity`: one `$default` route with an `AWS_PROXY` integration (payload 2.0), `$default` stage with auto-deploy and throttling rate 10/s, burst 20, and a Lambda permission scoped to this API's execution ARN.
- **Issuer:** the API's default endpoint `https://<api-id>.execute-api.us-east-1.amazonaws.com`, no trailing slash. `IDP_ISSUER` is set from `aws_apigatewayv2_api.this.api_endpoint`. There's no cycle: the API resource doesn't depend on the function, only the integration and the permission do.
- **Role:** logs to its own log group, X-Ray write, `secretsmanager:GetSecretValue` on `lb-demo/idp-signing-key` only, `s3:GetObject` on `identity/demo_users.yaml` only.
- **Log group** `/aws/lambda/lb-demo-identity` with 30-day retention, declared before the function.
- **Outputs:** `issuer`, `jwks_url`, `api_id`, `function_name`.

## Implementation

### Files

- Create: `infra/terraform/identity/main.tf` (backend key `identity/terraform.tfstate`, provider, remote state of `data`), `infra/terraform/identity/lambda.tf`, `infra/terraform/identity/api.tf`, `infra/terraform/identity/outputs.tf`, `.terraform.lock.hcl`
- Test: `infra/terraform/identity/tests/identity.tftest.hcl`

### Interfaces

- Consumes: `data` outputs (`serving_bucket`, `serving_bucket_arn`, `identity_image_parameter`); `agent/Dockerfile.identity` and the handler `bankagent.identity.lambda_handler.handler` (unit 80); the secret `lb-demo/idp-signing-key` (unit 88).
- Produces: the outputs above, read by `agent`, `realtime`, `app` and `ops`.

## Scope Limits

- the `identity` root and its tests. The Lambda code comes from unit 80.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests first (CLAUDE.md → Repo Rules).
- `terraform fmt -check && terraform init -backend=false && terraform validate && terraform test` passes in `infra/terraform/identity/` (mock provider, `override_data` for the remote state).
- `identity.tftest.hcl` runs: `lambda_is_arm64_image_with_idp_environment`, `http_api_proxies_everything_and_is_throttled`, `lambda_reads_only_its_secret_and_the_identities_object`, `logs_kept_30_days_and_issuer_output`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for resource settings and test intent:

`docs/reference/plans/2026-10-01-deployment.md`: Task 6 (`LbDemo-Identity`: the IdP Lambda behind an HTTP API), lines 1485–1619
