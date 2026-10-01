# 85 · `LbDemo-Web`: Amplify Hosting, Build Tag and Trace Link

**Subsystem:** Deployment · **Depends on:** 81, 83, 84, 75 · **Reference:** deployment plan, Task 9

## Goal

Define the Amplify app and branch (auto-build off) with its DynamoDB-only compute role, and add the build tag and CloudWatch trace link to the web app.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #1 and #2 in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `infra/lb_infra/stacks/web.py`, `web/lib/trace/xray.ts`, `web/components/staff/BuildTag.tsx`, `web/app/agent/layout.tsx`, `web/app/trace/layout.tsx`, `web/app/demo/layout.tsx`
- Modify: `infra/lb_infra/assembly.py`, `amplify.yml`, `web/lib/server/records.ts`, `web/lib/trace/viewModel.ts`, `web/components/trace/TraceTurn.tsx`
- Test: `infra/tests/test_web.py`, `web/tests/unit/xray.test.ts`

### Interfaces

- Consumes:
  - `DataStack.tables`, `IdentityStack.issuer`, `AgentStack.invoke_url`, `RealtimeStack.api`;
  - the web env schema in `web/lib/server/env.ts` (UI Task 11);
  - `buildTrace`/`TraceTurn` (UI Task 15);
  - `TraceTurnView` (UI Task 21).
- Produces:
  - `WebStack.app_id: str`;
  - outputs `AppId` and `AppUrl`;
  - `web_env(cfg, identity, agent, realtime) -> dict[str, str]`;
  - `xrayTraceUrl(traceId: string, region?: string): string | null`;
  - `TraceTurn.traceUrl?: string`;
  - the `build_all` key `web`.

## Scope Limits

- the Web stack; `amplify.yml`; three small additions to `web/` (an X-Ray link helper, the trace link, a build tag on staff pages). No other UI changes.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_web.py -v` passes, and `cd ../web && npm test` passes.
- The reference task's tests exist and pass:
  `test_amplify_app_is_ssr_with_compute_role_and_token_from_secrets_manager`, `test_main_branch_never_auto_builds_and_gets_the_stack_outputs`, `test_compute_role_is_dynamodb_only`, `builds the CloudWatch X-Ray console link`, `rejects anything that isn't an X-Ray trace id`, `links a turn when one of its records carries trace_id`, `has no link without trace_id`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 9 (`LbDemo-Web`: Amplify Hosting, plus the build tag and trace link in the web app), lines 2056–2322
