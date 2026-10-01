# 83 · `LbDemo-Agent`: the AgentCore Runtime

**Subsystem:** Deployment · **Depends on:** 82, 79 · **Reference:** deployment plan, Task 7

## Goal

Define the ARM64 image asset, the least-privilege execution role, the runtime with its JWT authorizer, and the `live` endpoint.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #11 (Bedrock signing service from unit 77) in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `infra/lb_infra/stacks/agent.py`
- Modify: `infra/lb_infra/config.py` (+ `BEDROCK_ACTIONS`, `bedrock_resources`, `OTEL_ENV`), `infra/lb_infra/assembly.py`
- Test: `infra/tests/test_agent.py`

### Interfaces

- Consumes: `DataStack.tables`, `IdentityStack.issuer`, `agent/Dockerfile` (Task 3), and the Task 1 results (Steps 1, 2, 3 and 7).
- Produces:
  - `AgentStack.runtime_id: str`;
  - `AgentStack.invoke_url: str` (`https://bedrock-agentcore.us-east-2.amazonaws.com/runtimes/<url-encoded ARN>/invocations?qualifier=live`);
  - `AgentStack.role: iam.Role`;
  - outputs `RuntimeId`, `RuntimeArn` and `InvokeUrl`;
  - the `build_all` key `agent`.

## Scope Limits

- the image asset, the execution role, the runtime, the `live` endpoint and log retention.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_agent.py -v` passes.
- The reference task's tests exist and pass:
  `test_runtime_shape`, `test_runtime_environment_has_no_secret_values`, `test_live_endpoint_tracks_the_new_version`, `test_execution_role_trusts_agentcore_in_this_account`, `test_least_privilege_data_access`, `test_invoke_url_uses_the_live_qualifier`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 7 (`LbDemo-Agent`: the AgentCore Runtime), lines 1623–1862
