# 85 · Web on ECS Fargate Spot, Build Tag and Trace Link

**Subsystem:** Deployment · **Depends on:** 81, 82, 83, 84, 75 · **Reference:** deployment plan, Task 9 (web-app half only)

> *(Rewritten 2026-10-04.)* The web runs on ECS Fargate Spot, not Amplify Hosting. The hosting shell is already deployed by Terraform `infra/terraform/app` (cluster `latam-bank`, service `latam-bank-web`, ECR repo `latam-bank-web`, placeholder image). This unit wires the real image and its environment into that root. All infrastructure is Terraform. See `progress-tracker.md` → Architecture Decisions, 2026-10-04.

## Goal

Ship the `web/` container image to the existing ECS service with its environment and a DynamoDB-only task role, and add the build tag and CloudWatch trace link to the web app.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Deployment Topology (including Deployed Infrastructure); Access Controls and Secrets
- Deployment plan #1 and #2, and the 2026-10-04 decisions, in `progress-tracker.md` → Architecture Decisions
- `infra/terraform/app/` (`main.tf`, `ecs.tf`, `tests/app.tftest.hcl`)

## Requirements

- **Image:** `web/Dockerfile` builds the Next.js standalone output for `linux/amd64` (the task definition is `X86_64`), listens on `PORT=3000`, `HOSTNAME=0.0.0.0`. The health check `wget -qO- http://127.0.0.1:3000/` must succeed, so the image includes `wget` (Alpine base) and `/` answers 200 or a redirect that `wget` follows.
- **Tag:** the git SHA. The ECR repo has immutable tags.
- **Which image runs:** the deploy workflow writes `<ecr_repository_url>:<git sha>` to the SSM parameter `/fh26/web/image`, and `infra/terraform/app` owns that parameter (`aws_ssm_parameter`, created with the placeholder image, `lifecycle { ignore_changes = [value] }`) and uses its refreshed value as the container image. The image is never a workflow-only `-var`, so a manual or later `terraform apply` of `app` can't roll the service back to the placeholder.
- **Environment:** the container gets the values the web env schema (`web/lib/server/env.ts`, UI Task 11) needs: the issuer URL, the AgentCore invoke URL, the AppSync Events endpoints, the table names, the region and `NEXT_PUBLIC_GIT_SHA`. They come from the other roots' outputs through `data "terraform_remote_state"` (`data`, `identity`, `agent`, `realtime`). No secret goes into `environment`; any future secret uses the task definition's `secrets` from Secrets Manager.
- **Task role** `latam-bank-web-task`: read and write on `sessions`, `conversation_messages` and `handoffs`; read on `decision_records`; their indexes. No `InvokeAgentRuntime` (deployment plan #1), no `Scan`, no `*` resources.
- **Placeholder removal:** `var.command` defaults to `null` once the real image ships, so the container runs its own `CMD`.
- **Unchanged:** Fargate Spot, one task, public IP, security group limited to `var.allowed_cidrs`, circuit breaker with rollback. The demo-day ALB with HTTPS and the switch to `FARGATE` are a separate, owner-approved change.

## Implementation

### Files

- Create: `web/Dockerfile`, `web/.dockerignore`, `web/lib/trace/xray.ts`, `web/components/staff/BuildTag.tsx`, `web/app/agent/layout.tsx`, `web/app/trace/layout.tsx`, `web/app/demo/layout.tsx`
- Modify: `infra/terraform/app/main.tf`, `infra/terraform/app/ecs.tf`, `web/next.config.ts` (`output: "standalone"`), `web/lib/server/records.ts`, `web/lib/trace/viewModel.ts`, `web/components/trace/TraceTurn.tsx`
- Test: `infra/terraform/app/tests/app.tftest.hcl`, `web/tests/unit/xray.test.ts`

### Interfaces

- Consumes:
  - remote state: `data.table_names` and `table_arns`, `identity.issuer`, `agent.invoke_url`, `realtime.http_domain` and `realtime_domain`;
  - the web env schema in `web/lib/server/env.ts` (UI Task 11);
  - `buildTrace`/`TraceTurn` (UI Task 15);
  - `TraceTurnView` (UI Task 21).
- Produces:
  - Terraform outputs `cluster`, `service`, `ecr_repository_url` (existing), plus `task_role_arn`;
  - the SSM parameter `/fh26/web/image`, owned by the `app` root and overwritten by the deploy workflow (unit 89);
  - `xrayTraceUrl(traceId: string, region?: string): string | null` (default region `us-east-1`);
  - `TraceTurn.traceUrl?: string`.

## Scope Limits

- the Terraform `app` root, the web image, and three small additions to `web/` (an X-Ray link helper, the trace link, a build tag on staff pages). No other UI changes.
- `terraform apply` against AWS runs only through `deploy.yml` on `main`, or with the owner's approval.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests are written first and fail, then pass after the implementation (CLAUDE.md → Repo Rules).
- `cd infra/terraform/app && terraform fmt -check && terraform init -backend=false && terraform validate && terraform test` passes, and `cd web && npm test` passes.
- `app.tftest.hcl` pins: the service uses `FARGATE_SPOT` with the circuit breaker and rollback; ingress is only `var.allowed_cidrs` on 3000; the task role policy grants only the four tables (and their indexes) with no `Scan` and no `InvokeAgentRuntime`; the container environment carries every key `env.ts` requires and no secret.
- The web tests from the reference task exist and pass: `builds the CloudWatch X-Ray console link`, `rejects anything that isn't an X-Ray trace id`, `links a turn when one of its records carries trace_id`, `has no link without trace_id`.
- `docker build --platform linux/amd64 web/` succeeds and the container answers on port 3000.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands. Use only the web-app parts (X-Ray helper, trace link, build tag); the Amplify stack in it is superseded:

`docs/reference/plans/2026-10-01-deployment.md`: Task 9 (`LbDemo-Web`: Amplify Hosting, plus the build tag and trace link in the web app), lines 2056–2322
