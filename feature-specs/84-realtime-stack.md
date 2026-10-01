# 84 · `LbDemo-Realtime`: AppSync Events from Python

**Subsystem:** Deployment · **Depends on:** 81, 59, 60 · **Reference:** deployment plan, Task 8

## Goal

Define the Event API, namespaces, authorizer and publisher in the Python CDK app, reusing the UI handlers, and retire the TypeScript CDK app.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `infra/lb_infra/stacks/realtime.py`
- Modify: `infra/lb_infra/assembly.py`, `infra/realtime/package.json`, `infra/realtime/tsconfig.json`, `docs/superpowers/plans/2026-09-30-ui.md` (a note under "Plan status")
- Delete: `infra/realtime/bin/app.ts`, `infra/realtime/lib/realtime-stack.ts`, `infra/realtime/cdk.json`, `infra/realtime/test/stack.test.ts`, `infra/realtime/scripts/stream-arns.sh`
- Test: `infra/tests/test_realtime.py`

### Interfaces

- Consumes:
  - `infra/realtime/authorizer/index.ts` (env `IDP_ISSUER`, `IDP_JWKS_URL`);
  - `infra/realtime/publisher/index.ts` (env `EVENTS_HTTP_DOMAIN`);
  - `infra/realtime/handlers/namespace.js` (UI plan Tasks 7–8);
  - `DataStack.tables`, `IdentityStack.issuer`.
- Produces:
  - `RealtimeStack.api: appsync.EventApi`, `.publisher`, `.authorizer` and `.dlq: sqs.Queue`;
  - outputs `HttpDomain` and `RealtimeDomain`;
  - the `build_all` key `realtime`.

### Notes

- Step 5 adds a note to the UI plan. Record that note in `progress-tracker.md` → Architecture Decisions instead (the plans are frozen).

## Scope Limits

- the Python stack; deleting the UI plan's TypeScript CDK app files; a note in the UI plan. No handler code changes.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_realtime.py -v` passes, and `cd realtime && npm test` still passes.
- The reference task's tests exist and pass:
  `test_event_api_with_three_namespaces`, `test_publish_is_iam_only_and_subscribe_is_lambda`, `test_three_stream_sources_with_bisect_retries_and_dlq`, `test_publisher_can_publish_and_authorizer_knows_the_issuer`, `test_dlq_retains_14_days_and_requires_tls`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 8 (`LbDemo-Realtime`: AppSync Events from Python, reusing the UI plan's handlers), lines 1866–2052
