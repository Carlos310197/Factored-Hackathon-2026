# 12 · Agent Project Scaffold, Settings and Session Context

**Subsystem:** Agent core · **Depends on:** none · **Reference:** agent-core plan, Task 1

## Goal

Create the `agent/` uv project with pinned libraries, the settings object, the session context every tool takes, and id helpers.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/pyproject.toml`, `agent/src/bankagent/__init__.py`, `agent/src/bankagent/settings.py`, `agent/src/bankagent/context.py`, `agent/src/bankagent/ids.py`, `agent/tests/__init__.py`, `agent/tests/conftest.py`, `agent/tests/test_scaffold.py`

### Interfaces

- Produces:
  - `Settings.from_env(env: Mapping[str,str] = os.environ) -> Settings` with fields `aws_region, serving_uri, table_prefix, dynamodb_endpoint, jev_api_key, jev_url, jev_model, issuer, audience, jwks_url`;
  - `SessionContext(customer_id: str, session_id: str, scopes: frozenset[str], lang: str, expires_at: int)` with `.require(scope)` raising `PermissionDenied`;
  - constants `SCOPE_READ = "inquiry:read"`, `SCOPE_DISPUTE = "dispute:create"`;
  - `new_id(prefix: str) -> str` (time-sortable, e.g. `DSP-1759140000000A1B2C3D4`).

### Notes

- Agent-core plan #1–#4 in `progress-tracker.md` → Architecture Decisions were verified against these pinned versions.

## Scope Limits

- Scaffold only: `settings.py`, `context.py`, `ids.py` and the test setup.
- Verify that the pinned library APIs import (agent-core plan #1–#4 rely on those versions).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_settings_defaults`, `test_settings_requires_serving_uri`, `test_session_context_require_scope`, `test_new_id_prefix_and_uniqueness`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 1 (Project scaffold, settings and session context), lines 101–314
