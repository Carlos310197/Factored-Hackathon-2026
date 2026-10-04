# 77 · Deployment Platform Checks

**Subsystem:** Deployment · **Depends on:** none · **Reference:** deployment plan, Task 1 · **[live]**

## Goal

Check the Terraform-provider, Bedrock-signing, bucket, GitHub-runner, quota and observability facts that later units depend on, and fill the capacity table's quota values.

> *(Updated 2026-10-04: everything is Terraform.)* The reference task's CloudFormation and CDK checks become Terraform-provider checks. Check, with the provider version pinned in `infra/terraform/*/.terraform.lock.hcl` (or the newest `hashicorp/aws` 6.x if it must move):
> 1. `aws_bedrockagentcore_agent_runtime` and `aws_bedrockagentcore_agent_runtime_endpoint` exist and support a custom JWT authorizer and a request header allowlist. Fallback: `awscc_bedrockagentcore_runtime`; last resort `terraform_data` + AWS CLI (unit 83).
> 2. `aws_appsync_api` (Event API) and `aws_appsync_channel_namespace` with `code_handlers` exist. Fallback: the `awscc` equivalents (unit 84).
> 3. A Terraform resource for CloudWatch Transaction Search (`aws_xray_trace_segment_destination` or similar). Fallback: the AWS CLI call in `apply.sh` (unit 88).
> 4. AgentCore Runtime, AppSync Events, and Haiku 4.5 / Sonnet 5.5 on Bedrock are available in **us-east-1**.
>
> Each result, and the fallback it selects, goes to `progress-tracker.md` → Architecture Decisions.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- `context/architecture-context.md` → Platform Facts · deployment §2

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Capacity limits · deployment §8

Each value is filled in during plan task 1 from Service Quotas and documentation, plus single-user measurements after the first deploy. The README labels each value "quota" or "measured".

| Component | What limits it |
|---|---|
| AgentCore Runtime | One microVM per session; the concurrent-session quota; cold-start time (measured). Turn budget 20 s (agent-core §8). |
| Bedrock | On-demand token and request quotas per minute for Haiku 4.5 and Sonnet 5.5 in us-east-1. Expected to be the first ceiling under load. |
| Jev (TypeSafe) | Alpha endpoint, unpublished rate limit. Measured where possible; stated as a risk. |
| DynamoDB | On-demand. `decision_records` is partitioned by session, so there's no hot key at demo scale. |
| DuckDB over S3 | Per-turn read latency, measured. The fallback is the 90-day agent export (agent-core §7.1). |
| AppSync Events | Connection and publish quotas, far above demo needs |
| Web (ECS Fargate Spot) | One 0.5 vCPU / 1 GB task; Spot interruptions (about a minute to replace). No request timeout while reached directly; the demo-day ALB's idle timeout (60 s default) is above the 20 s turn. |
| Identity HTTP API | Stage throttling 10 rps, burst 20 |

No load test is run. The README states capacity from quotas and measured single-user latency, labeled as such.

## Implementation

### Files

- Modify: `docs/superpowers/plans/2026-10-01-deployment.md` (append "Task 1 results")

### Interfaces

- Produces: facts that Tasks 3, 5, 7, 9, 12 and 13 read. Each later task names the step it depends on.

### Notes

- Record the results in `progress-tracker.md` (Session Notes, plus Architecture Decisions where a conditional note in units 81–89 applies), not in the plan.

## Scope Limits

- read-only checks and a written record. Nothing here creates AWS resources.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- "Task 1 results" at the end of this file has a yes/no plus evidence for every step, and names which conditional notes in later tasks apply.
- The reference task's tests exist and pass:
  (no automated tests in this task)
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 1 (Platform checks), lines 152–277
