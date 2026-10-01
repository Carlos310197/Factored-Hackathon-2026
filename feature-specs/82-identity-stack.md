# 82 · `LbDemo-Identity`: IdP Lambda Behind an HTTP API

**Subsystem:** Deployment · **Depends on:** 81, 80 · **Reference:** deployment plan, Task 6

## Goal

Deploy the identity Lambda behind a throttled HTTP API and output the issuer URL.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `infra/lb_infra/stacks/identity.py`
- Modify: `infra/lb_infra/assembly.py`
- Test: `infra/tests/test_identity.py`

### Interfaces

- Consumes: `DataStack.bucket`; `agent/Dockerfile.identity` and the handler `bankagent.identity.lambda_handler.handler` (Task 4).
- Produces:
  - `IdentityStack.issuer: str` (`https://<apiId>.execute-api.us-east-2.amazonaws.com`, no trailing slash);
  - `IdentityStack.api: apigwv2.HttpApi`;
  - `IdentityStack.fn: lambda_.DockerImageFunction`;
  - the output `Issuer`;
  - the `build_all` key `identity`.

## Scope Limits

- the Identity stack and its tests. The Lambda code comes from Task 4.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_identity.py -v` passes.
- The reference task's tests exist and pass:
  `test_lambda_is_arm64_image_with_idp_environment`, `test_http_api_proxies_everything_and_is_throttled`, `test_lambda_reads_only_its_secret_and_the_identities_object`, `test_logs_kept_30_days_and_issuer_output`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 6 (`LbDemo-Identity`: the IdP Lambda behind an HTTP API), lines 1485–1619
