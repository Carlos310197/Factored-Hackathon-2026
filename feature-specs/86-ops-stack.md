# 86 · Terraform `ops` Root: Alarms and the Dashboard

**Subsystem:** Deployment · **Depends on:** 85 · **Reference:** deployment plan, Task 10 (intent and test cases only)

> *(Rewritten 2026-10-04: everything is Terraform.)* Use the reference task only for thresholds, widget content and test intent. Conventions: `context/code-standards.md` → Deployment → Terraform.

## Goal

Create the per-metric alarms, the `DemoUnhealthy` composite, and the five-row `lb-demo-ops` dashboard, with no notifications.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment (Terraform conventions)
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #6 and #7 in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Alarms · deployment §6.3

There are no notifications; alarm state is read from the dashboard. Thresholds are sized for demo traffic. Missing data counts as `notBreaching`, so a quiet stack stays green.

| Alarm | Condition |
|---|---|
| Turn latency | p95 `TurnLatencyMs` > 15 s in 3 of 5 one-minute periods |
| Safe-fallback rate | `safe_fallback` / `TurnCount` > 20% over 10 minutes, with at least 5 turns |
| Jev failing | `JevErrorCount` ≥ 5 in 5 minutes |
| Bedrock failing | `LlmErrorCount` ≥ 5 in 5 minutes |
| Realtime DLQ | `ApproximateNumberOfMessagesVisible` > 0 |
| Publisher lag | stream `IteratorAge` > 60 s |
| DynamoDB throttling | `ThrottledRequests` > 0, summed across the six tables |
| Identity errors | HTTP API 5xx ≥ 3 in 5 minutes, or Lambda `Errors` ≥ 3 in 5 minutes |
| Web errors | ECS service `latam-bank-web` running task count < 1 for 5 minutes (Container Insights); once the demo-day ALB exists, also its `HTTPCode_Target_5XX_Count` ≥ 5 in 5 minutes |

A composite alarm, **`DemoUnhealthy`**, is in alarm when any of the above is. It's the one status to check before a demo.

### Dashboard `lb-demo-ops` · deployment §6.4

One page, five rows:

1. **Outcomes:** turns by route, handoffs by priority, injection blocks; split by language.
2. **Latency:** turn p50 and p95, Jev p95, Bedrock p95 per role.
3. **Dependencies:** Jev errors, Bedrock errors, template fallbacks.
4. **Realtime:** publisher invocations and errors, iterator age, DLQ depth, AppSync connections.
5. **Platform:** identity 4xx and 5xx, DynamoDB throttles and consumed capacity, the web service's running tasks, CPU and memory (plus ALB requests and 5xx once it exists), an alarm-status widget with every §6.3 alarm, and `DemoUnhealthy`.

This is the operator view. Quality metrics stay in the evaluation report. The UI spec's "no metrics dashboard" still holds: this dashboard lives in CloudWatch, not in the app.

## Implementation

### Files

- Create: `infra/terraform/ops/main.tf` (backend key `ops/terraform.tfstate`, provider, remote state of `data`, `identity`, `agent`, `realtime`, `app`), `infra/terraform/ops/alarms.tf`, `infra/terraform/ops/dashboard.tf`, `infra/terraform/ops/outputs.tf`, `.terraform.lock.hcl`
- Modify: `infra/terraform/app/ecs.tf` (Container Insights on the `latam-bank` cluster: `setting { name = "containerInsights", value = "enabled" }`), `infra/terraform/app/tests/app.tftest.hcl`
- Test: `infra/terraform/ops/tests/ops.tftest.hcl`

### Interfaces

- Consumes:
  - the metrics from unit 79 (namespace `LatamBank`: `TurnLatencyMs`, `TurnCount{Route}`, `HandoffCount{Priority}`, `JevErrorCount`, `JevLatencyMs`, `LlmErrorCount{Role}`, `LlmLatencyMs{Role}`, `TemplateFallbackCount`, `InjectionBlockedCount`, each also with `Language`; alarms use the language-free series, deployment plan #7);
  - remote state: `data.table_names`, `identity.api_id` and `function_name`, `realtime.dlq_name`, `publisher_name` and `api_arn`, `app.cluster` and `service`.
- Produces:
  - `aws_cloudwatch_metric_alarm` resources for every §6.3 row (the six DynamoDB throttle alarms per deployment plan #6), all with `actions_enabled = false` and `treat_missing_data = "notBreaching"`;
  - `aws_cloudwatch_composite_alarm` `lb-demo-DemoUnhealthy` over all of them, no actions;
  - `aws_cloudwatch_dashboard` `lb-demo-ops` with five rows, its body built with `jsonencode`;
  - outputs `alarm_names`, `composite_alarm_name`, `dashboard_name`.

## Scope Limits

- CloudWatch alarms, the composite alarm and one dashboard (plus Container Insights on the cluster). No SNS topic and no alarm actions.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- Tests first (CLAUDE.md → Repo Rules).
- `terraform fmt -check && terraform init -backend=false && terraform validate && terraform test` passes in `infra/terraform/ops/` and `infra/terraform/app/`.
- `ops.tftest.hcl` runs: `every_alarm_exists_quietly`, `thresholds`, `composite_covers_all_alarms_without_actions`, `dashboard_has_five_rows_and_no_sns_anywhere`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for thresholds, widgets and test intent:

`docs/reference/plans/2026-10-01-deployment.md`: Task 10 (`LbDemo-Ops`: alarms and the dashboard), lines 2326–2537
