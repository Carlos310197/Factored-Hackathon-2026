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
  `lb-demo-agent-alarms` (email), plus the monthly AWS Budget (80 % actual / 100 % forecast).

| Alarm | Fires on | Means |
|---|---|---|
| TurnFailed | ≥ 3 in 5 min | uncaught errors in a turn |
| TemplateFallback | ≥ 5 in 15 min | the reply model or Jev is failing (stale Bedrock token, Jev outage) |
| AuditWriteFailed | ≥ 1 in 5 min | a decision record could not be written, so the trace has a hole |
| TurnSlow | ≥ 3 in 15 min | turns over 20 s (the web app gives up at 25 s) |
| StalePointer | ≥ 1 in 1 h | the serving export is older than 2 days (daily pipeline stopped) |
| TurnCapReached | ≥ 20 in 1 h | sessions hitting the 30-turn cap (possible abuse of the public demo identities) |

## Tracing one request

Every customer message carries a `client_message_id` from the browser. The same id appears at each hop:

| Hop | What is written | Where |
|---|---|---|
| Web BFF `/api/chat` | `{"event":"chat","status":…,"ms":…,"sid":…,"client_message_id":…,"turn_id":…}`, one per call, including 401s | web log group (ECS) |
| Agent, every request | `request <outcome> <session> <message_id>`: `turn`, `duplicate`, `human_control`, `invalid_message`, `auth_required`, `session_expired`, `identity_unavailable`, `turn_failed`, `warmup_ok`, `warmup_failed`; counted by the `Requests` metric (dimension `Outcome`) | runtime log group |
| Agent, each turn | `turn_end <ms>` (latency metric) and the decision records for the turn (tools, models, Jev answers, policy rules, guards) | runtime log group, `lb-demo-decision_records` |
| Conversation | customer and assistant messages with `turn_id` | `lb-demo-conversation_messages` |

So `sid` + `client_message_id` lead to the `turn_id`, and the `turn_id` leads to the full trace at `/trace/<session>`.
Not wired: distributed tracing (OpenTelemetry spans have no exporter, so there is no X-Ray trace), and load-balancer or
CloudFront access logs. Both are listed for before production.

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

## Rollback rehearsal, 2026-10-06

The `live` endpoint pins one runtime version; rolling back means pointing it at the previous one. Rehearsed once on
the production runtime, right after deploying v13 (the egress fix):

| Time (UTC) | Step | Result |
|---|---|---|
| 02:50:30 | `aws bedrock-agentcore-control update-agent-runtime-endpoint --agent-runtime-id lb_demo_agent-r9JuK9Hdui --endpoint-name live --agent-runtime-version 12` | live v12, `READY` after **7 s** |
| ~02:50:45 | a fresh customer conversation through the public app (demo17, balance question) | HTTP 200 in 12.0 s (cold microVM right after the switch), model-written reply |
| 02:51:26 | same command with `--agent-runtime-version 13` | live v13, `READY` after **8 s** |
| 02:51:40 | `terraform plan` in `infra/terraform/agent` | "No changes": the roll-forward left no drift |

So a bad agent release is undone in under 10 seconds without a rebuild, as long as the previous version still exists
(AgentCore keeps them). The web app rolls back the same way: point `/fh26/web/image` at the previous tag and apply the
`app` root (a new ECS task revision, ~2 minutes); that path was exercised by every deploy tonight, not rehearsed as a rollback.
Not proven: the first conversation after a switch is cold (12 s here).

## Load test, 2026-10-06

`scripts/load_test.py` (stdlib only): 10 fresh customers (`demo09`–`demo18`) sign in at the same moment (each sign-in
warms its own agent session), then each sends the same 3 messages with 8 s between them: a balance question, "¿Tengo
algún pago rechazado?" and "Gracias". Started 02:55:11 UTC against runtime v13.

| Measure | Value | Source |
|---|---|---|
| Turns answered | 30 / 30 (HTTP 200), 0 errors | script |
| Wall-clock duration | 51.7 s | script |
| End-to-end latency (browser → web → agent → reply) | p50 3.2 s, p95 6.9 s, max 7.8 s | script |
| Agent time per turn | p50 2.6 s, p95 5.7 s, max 7.1 s (n = 27 datapoints in the window) | `TurnDurationMs` |
| Failed / slow turns | 0 / 0 | `TurnFailed`, `TurnSlow` |
| Template fallbacks | 1 of 30 | `TemplateFallback` |
| Login warm-ups | all 10 succeeded (`warmup_ok`), none failed | `Requests` by `Outcome` |

Reproduce (costs real Bedrock and Jev calls): `python3 scripts/load_test.py https://d21y0qq5d8ixnr.cloudfront.net --users 10`.
That is the size of a judge panel testing at once. Not measured: the saturation point. The first expected limit is the
account's Lambda concurrency of 10, shared by the identity service and the realtime Lambdas.

## Reproduce

```bash
G=/aws/bedrock-agentcore/runtimes/lb_demo_agent-r9JuK9Hdui-live; ST=alarm-drill-$(date -u +%F)
aws logs create-log-stream --log-group-name $G --log-stream-name $ST
aws logs put-log-events --log-group-name $G --log-stream-name $ST --log-events \
  "[{\"timestamp\":$(($(date +%s)*1000)),\"message\":\"ALARM DRILL (synthetic): decision record write failed\"}]"
aws cloudwatch describe-alarm-history --alarm-name lb-demo-agent-AuditWriteFailed --max-items 4
```

## Capacity

| Component | Limit we know of | Source |
|---|---|---|
| Web app | 1 Fargate Spot task (0.5 vCPU / 1 GB) behind CloudFront (HTTPS) and an ALB that only CloudFront can reach; a Spot interruption means about 1–2 min of downtime while a new task starts, the URL stays the same | `infra/terraform/app/ecs.tf` |
| Agent runtime (AgentCore) | New sessions 25/s, data-plane calls 1,000/s (account quotas); each session runs in its own microVM | AWS Service Quotas, `bedrock-agentcore` |
| LLM (Bedrock Mantle) | Not visible: the on-demand quotas listed for gpt-oss and Ministral in our account read 0, and inference runs through the Mantle endpoint (and a role in a second account), whose throughput limits Service Quotas doesn't show | AWS Service Quotas, `bedrock` |
| Jev (TypeSafe) | No published rate limit; 3 s timeout per call, 2–3 calls per turn | `decisions/jev.py` |
| Identity (mock IdP) | API Gateway throttle 10 req/s (burst 20); the account's Lambda concurrency is 10 in total, shared with the realtime authorizer and publisher | `infra/terraform/identity/api.tf`, AWS account settings |
| DynamoDB | On-demand capacity, no provisioned limit | `infra/terraform/data/tables.tf` |
