# Operations: dashboard, alarms and one drill

## Where to look

- **Dashboard** `lb-demo-ops` (CloudWatch, us-east-1; `infra/terraform/agent/dashboard.tf`):
  - Turn latency p50/p95/max, with the 15 s turn budget and the web app's 25 s timeout marked.
  - Turns per 5 minutes.
  - Failure metrics.
  - Abuse and data freshness.
  - The state of every alarm.
  - Web load-balancer 5xx counts and p95 response time.
- **Latency source:** the agent writes one plain line per turn, `turn_end <ms>` (agent time, from accepting the
  message to the reply). A metric filter turns it into `LBDemo/Agent TurnDurationMs`.
- **Alarms** (`infra/terraform/agent/alarms.tf`): six alarms on the agent's own log lines, all sending to the SNS topic
  `lb-demo-agent-alarms` (email), plus the monthly AWS Budget.

| Alarm | Fires on | Means |
|---|---|---|
| TurnFailed | ≥ 3 in 5 min | uncaught errors in a turn |
| TemplateFallback | ≥ 5 in 15 min | the reply model or Jev is failing (stale Bedrock token, Jev outage) |
| AuditWriteFailed | ≥ 1 in 5 min | a decision record could not be written, so the trace has a hole |
| TurnSlow | ≥ 3 in 15 min | turns over 20 s (the web app gives up at 25 s) |
| StalePointer | ≥ 1 in 1 h | the serving export is older than 2 days (daily pipeline stopped) |
| TurnCapReached | ≥ 20 in 1 h | sessions hitting the 30-turn cap (possible abuse of the public demo identities) |

## Drill, 2026-10-06

The question a judge asks: *does an alarm actually reach a person?* We forced one end to end.

- **Method.** One synthetic line containing the exact watched text was written to the live runtime log group, in a
  separate stream named `alarm-drill-2026-10-06`:
  `ALARM DRILL 2026-10-06 (synthetic line, no real failure): decision record write failed`. Everything after the line
  is the production path: metric filter → metric → alarm → SNS topic → email.
- **Timeline (UTC).**

  | Time | Event | Source |
  |---|---|---|
  | 01:38:45 | line written | `logs put-log-events` |
  | 01:34–01:39 window | `AuditWriteFailed` = 1 | metric datapoint |
  | 01:39:49 | `lb-demo-agent-AuditWriteFailed` went OK → ALARM | alarm history, StateUpdate |
  | 01:39:49 | "Successfully executed action arn:aws:sns:…:lb-demo-agent-alarms" | alarm history, Action |

  From log line to SNS notification took **64 s**. The alarm returns to OK in the next clean 5-minute period, and the
  OK transition also emails (`ok_actions`).
- **What it does not prove.** It doesn't show that a real write failure produces the line; the line comes from
  `graph/nodes.py` (`logger.exception("decision record write failed")`), and that path is covered by tests, not by
  this drill. It also doesn't show that someone reads the email at night: the topic has one subscriber (a team member),
  not an on-call rotation.

## Reproduce

```bash
G=/aws/bedrock-agentcore/runtimes/lb_demo_agent-r9JuK9Hdui-live; ST=alarm-drill-$(date -u +%F)
aws logs create-log-stream --log-group-name $G --log-stream-name $ST
aws logs put-log-events --log-group-name $G --log-stream-name $ST --log-events \
  "[{\"timestamp\":$(($(date +%s)*1000)),\"message\":\"ALARM DRILL (synthetic): decision record write failed\"}]"
aws cloudwatch describe-alarm-history --alarm-name lb-demo-agent-AuditWriteFailed --max-items 4
```
