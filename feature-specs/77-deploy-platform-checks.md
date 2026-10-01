# 77 · Deployment Platform Checks

**Subsystem:** Deployment · **Depends on:** none · **Reference:** deployment plan, Task 1 · **[live]**

## Goal

Check the CloudFormation, CDK, Bedrock-signing, bucket, GitHub-runner, quota and observability facts that later units depend on, and fill the capacity table's quota values.

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
| Bedrock | On-demand token and request quotas per minute for Haiku 4.5 and Sonnet 5.5 in us-east-2. Expected to be the first ceiling under load. |
| Jev (TypeSafe) | Alpha endpoint, unpublished rate limit. Measured where possible; stated as a risk. |
| DynamoDB | On-demand. `decision_records` is partitioned by session, so there's no hot key at demo scale. |
| DuckDB over S3 | Per-turn read latency, measured. The fallback is the 90-day agent export (agent-core §7.1). |
| AppSync Events | Connection and publish quotas, far above demo needs |
| Amplify SSR | Request timeout vs the 20 s turn. The fallback is 202-plus-push (UI §10). |
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
