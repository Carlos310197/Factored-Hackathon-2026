# 84 · Terraform `realtime` Root: AppSync Events, Authorizer, Publisher

**Subsystem:** Deployment · **Depends on:** 81, 82, 59, 60 · **Reference:** deployment plan, Task 8 (intent and test cases only)

> *(Rewritten 2026-10-04: everything is Terraform.)* The reference task builds a Python CDK stack and retires a TypeScript CDK app. Here there is no CDK at all: the TypeScript in `infra/realtime/` is handler code only, bundled to JavaScript and deployed by this root. Conventions: `context/code-standards.md` → Deployment → Terraform.

## Goal

Define the Event API, its three namespaces, the Lambda authorizer and the stream publisher in Terraform, reusing the UI handlers.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Real-Time UI; Deployment Topology; Access Controls and Secrets
- UI plan #7 (`/queue/all`) in `progress-tracker.md` → Architecture Decisions
- Unit 77's result for "AppSync Events in Terraform"

## Requirements

- **Event API** `lb-demo-realtime` (`aws_appsync_api` with `event_config`; fallback `awscc_appsync_api`, settled in unit 77): connection and subscribe auth with the Lambda authorizer, publish auth `AWS_IAM` only.
- **Namespaces** `session`, `queue`, `trace` (`aws_appsync_channel_namespace`), each with `code_handlers = file("${path.module}/../../realtime/handlers/namespace.js")` (the `onSubscribe` channel rule from unit 59).
- **Authorizer Lambda** `lb-demo-realtime-authorizer` (Node.js 22, ARM64, zip of `infra/realtime/dist/authorizer/`): env `IDP_ISSUER`, `IDP_JWKS_URL` from the identity root; logs only; X-Ray active.
- **Publisher Lambda** `lb-demo-realtime-publisher` (zip of `infra/realtime/dist/publisher/`): env `EVENTS_HTTP_DOMAIN`; `appsync:EventPublish` on this API only; read on the three streams; `sqs:SendMessage` to the DLQ.
- **Event source mappings** on the three stream ARNs from `data`: `bisect_batch_on_function_error = true`, `function_response_types = ["ReportBatchItemFailures"]`, `maximum_retry_attempts = 5`, on-failure destination the DLQ, starting position `LATEST`.
- **DLQ** `lb-demo-realtime-dlq`: 14-day retention, SSE on, a queue policy that denies non-TLS.
- **Bundles:** `infra/realtime/package.json` gets `"build": "esbuild ... --outdir=dist"`; the root zips `dist/*` with `data "archive_file"`. `dist/` is gitignored; CI runs `npm ci && npm run build` before any `terraform` command in this root.
- **Log groups** for both Lambdas, 30-day retention.
- **Outputs:** `http_domain`, `realtime_domain`, `api_arn`, `dlq_name`, `publisher_name`, `authorizer_name`.

## Implementation

### Files

- Create: `infra/terraform/realtime/main.tf` (backend key `realtime/terraform.tfstate`, provider, remote state of `data` and `identity`), `infra/terraform/realtime/api.tf`, `infra/terraform/realtime/lambdas.tf`, `infra/terraform/realtime/outputs.tf`, `.terraform.lock.hcl`
- Modify: `infra/realtime/package.json` (+ `build` script, + `esbuild` dev dependency), `.gitignore` (+ `infra/realtime/dist/`)
- Test: `infra/terraform/realtime/tests/realtime.tftest.hcl`

### Interfaces

- Consumes: `infra/realtime/authorizer/index.ts`, `infra/realtime/publisher/index.ts`, `infra/realtime/handlers/namespace.js` (units 59–60); `data.stream_arns`; `identity.issuer`, `identity.jwks_url`.
- Produces: the outputs above, read by `app` and `ops`.

## Scope Limits

- the `realtime` root, the bundle script and its tests. No handler code changes.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests first (CLAUDE.md → Repo Rules).
- `cd infra/realtime && npm run build && npm test` passes; then `terraform fmt -check && terraform init -backend=false && terraform validate && terraform test` passes in `infra/terraform/realtime/`.
- `realtime.tftest.hcl` runs: `event_api_with_three_namespaces`, `publish_is_iam_only_and_subscribe_is_lambda`, `three_stream_sources_with_bisect_retries_and_dlq`, `publisher_can_publish_and_authorizer_knows_the_issuer`, `dlq_retains_14_days_and_requires_tls`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for resource settings and test intent:

`docs/reference/plans/2026-10-01-deployment.md`: Task 8 (`LbDemo-Realtime`: AppSync Events from Python, reusing the UI plan's handlers), lines 1866–2052
