# 22 · Runtime Wiring and the AgentCore Entrypoint

**Subsystem:** Agent core · **Depends on:** 21 · **Reference:** agent-core plan, Task 11

## Goal

Build the real runtime from settings, and the AgentCore entrypoint that re-verifies the JWT, builds `SessionContext` and answers `/ping` and `/invocations`.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `context/architecture-context.md` → Interfaces Between Subsystems → To spec 3 · agent-core §9.2
- Agent-core plan #2 and #3 in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/runtime.py`, `agent/src/bankagent/app.py`, `agent/tests/test_app.py`

### Interfaces

- Consumes:
  - `Settings` (Task 1);
  - `verify_token`, `AuthError`, `JwksCache` (Task 3);
  - `AgentService`, `Deps` (Task 10);
  - every concrete client (Tasks 2, 5, 6, 7, 8, 9).
- Produces:
  - `Runtime(settings, service, jwks)` and `build_runtime(settings) -> Runtime` (DynamoDBSaver checkpointer with a 30-day TTL);
  - `handle(payload: dict, headers: dict, rt) -> dict` (pure, testable);
  - the AgentCore app `bankagent.app:app`, with `@app.entrypoint invoke(payload, context)`, `/ping` and `/invocations` on port 8080.
- Error replies carry `error` ∈ `auth_required | session_expired | invalid_message | identity_unavailable` and never call the service.

## Scope Limits

- `runtime.py`, `app.py` and their tests. The UI's gate, idempotency and contract fields are unit 56.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_no_token_asks_to_log_in`, `test_bearer_header_any_case_and_payload_fallback`, `test_expired_token_reports_session_expired_in_requested_language`, `test_tampered_token_rejected`, `test_invalid_messages_rejected_without_service_call`, `test_payload_customer_id_is_ignored`, `test_identity_outage_is_reported_not_raised`, `test_http_contract_ping_and_invocations`, `test_build_runtime_wires_real_components`
- **An empty, oversized or non-string message, or a payload trying to set `customer_id`:** the entrypoint rejects it with a template, makes no model call, and ignores any `customer_id` in the payload. Pinned in Task 11 (`test_invalid_messages_rejected_without_service_call`, `test_payload_customer_id_is_ignored`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 11 (Runtime wiring and the AgentCore entrypoint), lines 4975–5236
