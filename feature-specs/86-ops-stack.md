# 86 · `LbDemo-Ops`: Alarms and the Dashboard

**Subsystem:** Deployment · **Depends on:** 85 · **Reference:** deployment plan, Task 10

## Goal

Create the per-metric alarms, the `DemoUnhealthy` composite, and the five-row `lb-demo-ops` dashboard, with no notifications.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
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
| Web errors | Amplify `5xxErrors` ≥ 5 in 5 minutes |

A composite alarm, **`DemoUnhealthy`**, is in alarm when any of the above is. It's the one status to check before a demo.

### Dashboard `lb-demo-ops` · deployment §6.4

One page, five rows:

1. **Outcomes:** turns by route, handoffs by priority, injection blocks; split by language.
2. **Latency:** turn p50 and p95, Jev p95, Bedrock p95 per role.
3. **Dependencies:** Jev errors, Bedrock errors, template fallbacks.
4. **Realtime:** publisher invocations and errors, iterator age, DLQ depth, AppSync connections.
5. **Platform:** identity 4xx and 5xx, DynamoDB throttles and consumed capacity, Amplify requests and 5xx, an alarm-status widget with every §6.3 alarm, and `DemoUnhealthy`.

This is the operator view. Quality metrics stay in the evaluation report. The UI spec's "no metrics dashboard" still holds: this dashboard lives in CloudWatch, not in the app.

## Implementation

### Files

- Create: `infra/lb_infra/stacks/ops.py`
- Modify: `infra/lb_infra/assembly.py`
- Test: `infra/tests/test_ops.py`

### Interfaces

- Consumes:
  - the metrics from Task 3 (namespace `LatamBank`: `TurnLatencyMs`, `TurnCount{Route}`, `HandoffCount{Priority}`, `JevErrorCount`, `JevLatencyMs`, `LlmErrorCount{Role}`, `LlmLatencyMs{Role}`, `TemplateFallbackCount`, `InjectionBlockedCount`, each also with `Language`);
  - `DataStack.tables`, `IdentityStack.api` and `.fn`, `RealtimeStack.dlq`, `.publisher` and `.api`, `WebStack.app_id`.
- Produces:
  - `OpsStack.alarms: list[cw.Alarm]` (14);
  - `OpsStack.composite`;
  - `OpsStack.rows: tuple[str, ...]`;
  - the `build_all` key `ops`.

## Scope Limits

- CloudWatch alarms, the composite alarm and one dashboard. No SNS topic and no alarm actions.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_ops.py -v` passes.
- The reference task's tests exist and pass:
  `test_every_alarm_exists_quietly`, `test_thresholds`, `test_composite_covers_all_alarms_without_actions`, `test_dashboard_has_five_rows_and_no_sns_anywhere`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 10 (`LbDemo-Ops`: alarms and the dashboard), lines 2326–2537
