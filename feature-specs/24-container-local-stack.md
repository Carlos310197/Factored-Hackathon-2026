# 24 · Container Image, Local Stack and Terminal Chat

**Subsystem:** Agent core · **Depends on:** 22, 23 · **Reference:** agent-core plan, Task 13

## Goal

Package the agent as an ARM64 image, run agent + IdP + DynamoDB Local with compose, and chat from a terminal client.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/Dockerfile`, `agent/.dockerignore`, `agent/scripts/chat.py`, `agent/tests/test_container_contract.py`
- Modify: `agent/docker-compose.yml` (replace the Task 6 version)

### Interfaces

- Consumes: `bankagent.app` (Task 11), `bankagent.identity.app` (Task 3), `scripts/create_tables.py` (Task 6), `agent/.serving` and `config/demo_users.yaml` (Task 12).
- Produces:
  - an ARM64 image serving `/ping` + `/invocations` on 8080 (the default command);
  - the same image runs the IdP via `python -m bankagent.identity.app` on 8081;
  - `docker compose up` brings up `dynamodb`, `init-tables`, `identity` and `agent`;
  - `scripts/chat.py`.

## Scope Limits

- Image, compose, chat client and the container contract test. The contract test makes no model calls.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_ping_is_healthy`, `test_invocation_without_token_asks_to_log_in`, `test_identity_publishes_discovery_and_jwks`, `test_valid_token_with_empty_message_is_rejected_before_any_model_call`
- `docker compose up` starts the stack, and the contract test (marker `container`) passes against it.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 13 (Container image, local stack and terminal chat client), lines 5600–5791
