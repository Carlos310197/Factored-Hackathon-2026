# 78 · Agent: Deployed Settings, Git SHA, Sessions TTL, Trace Id

**Subsystem:** Deployment · **Depends on:** 56 · **Reference:** deployment plan, Task 2

## Goal

Read the Jev key from Secrets Manager at startup without ever crash-looping, stamp the git SHA, give `sessions` a TTL, and keep `trace_id` on records.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #8 and #9 in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Modify: `agent/src/bankagent/settings.py`, `agent/src/bankagent/app.py`, `agent/src/bankagent/store/tables.py`, `agent/src/bankagent/store/repos.py`, `agent/tests/test_app_ui.py`
- Test: `agent/tests/test_deploy_settings.py`

### Interfaces

- Consumes: `Settings`, `Settings.from_env` (agent-core Task 1); `TABLE_SPECS`, `create_tables`, `Store`, `SessionRepo`, `DecisionLog` (agent-core Task 6, UI Task 2); `handle` (UI Task 4).
- Produces:
  - `Settings.git_sha: str` (default `"dev"`, from `GIT_SHA`);
  - `load_settings(env: Mapping[str, str] = os.environ, secrets_client=None) -> Settings`;
  - `DecisionLog.append(..., latency_ms=None, trace_id: str | None = None)`, which stores a top-level `trace_id` only when given;
  - `SessionRepo.TTL_DAYS = 90`, with `ensure()` writing `ttl`;
  - the `turn_end` payload `{duration_ms, awaiting, language}`.

### Notes

- Step 7 renames the local variable: `JEV_API_KEY` is the only name, local `.env` included.

## Scope Limits

- `settings.py`, `app.py` (only `runtime()` and the `turn_end` payload), `store/tables.py`, `store/repos.py`. No graph or observability code.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_deploy_settings.py tests/test_app_ui.py -v` passes, and `uv run pytest -q` passes.
- The reference task's tests exist and pass:
  `test_jev_key_read_from_secret_and_stripped`, `test_explicit_env_key_wins_over_secret`, `test_no_secret_id_means_no_secrets_call`, `test_missing_secret_leaves_key_empty_and_does_not_raise`, `test_git_sha_from_env_with_default`, `test_sessions_expire_after_90_days`, `test_decision_record_keeps_trace_id_only_when_given`, `test_turn_end_carries_the_reply_language`
- **The Jev secret is missing or access is denied when the agent starts.** Expected: the container starts with an empty key, a logged error, and Jev calls failing into clarify or handoff. Never a crash loop. Pinned in Task 2 (`test_missing_secret_leaves_key_empty_and_does_not_raise`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 2 (Deployed settings: Jev key from Secrets Manager, git SHA, sessions TTL, trace id on records), lines 285–507
