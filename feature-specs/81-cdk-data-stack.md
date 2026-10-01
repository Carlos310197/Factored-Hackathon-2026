# 81 · CDK Scaffold, Config, cdk-nag and `LbDemo-Data`

**Subsystem:** Deployment · **Depends on:** 77, 78 · **Reference:** deployment plan, Task 5

## Goal

Create the Python CDK app with shared config and the nag helper, plus the Data stack: six retained tables from the agent's specs, and a TLS-only policy on the existing bucket.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #3 and #5 in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `infra/pyproject.toml`, `infra/cdk.json`, `infra/app.py`, `infra/lb_infra/__init__.py` (empty), `infra/lb_infra/config.py`, `infra/lb_infra/specs.py`, `infra/lb_infra/nag.py`, `infra/lb_infra/assembly.py`, `infra/lb_infra/stacks/__init__.py` (empty), `infra/lb_infra/stacks/data.py`, `infra/tests/conftest.py`
- Modify: `.gitignore` (+ `infra/cdk.out/`, `infra/*-outputs.json`, `infra/diff.txt`)
- Test: `infra/tests/test_data.py`

### Interfaces

- Consumes: `TABLE_SPECS` and `STREAM_TABLES` from `agent/src/bankagent/store/tables.py` (loaded by file path); the Task 1 results (bucket name, repo name).
- Produces:
  - constants in `lb_infra.config`: `PREFIX = "lb-demo"`, `REGION`, `AUDIENCE = "bankagent"`, `STAFF_AUDIENCE = "bankagent-staff"`, `RUNTIME_NAME = "lb_demo_agent"`, `ENDPOINT_NAME = "live"`, `SECRETS`, `DEMO_USERS_KEY`, `MESSAGE_ID_HEADER`, `REPO`;
  - `Config(github_repo, serving_bucket, git_sha="local", chat_async="0")` and `Config.from_context(node)`;
  - `table_name(name) -> str`;
  - `load_table_specs() -> tuple[dict, tuple[str, ...]]`;
  - `nag.apply(app)` and `nag.suppress(stack, ids)`;
  - `build_all(app, cfg, env) -> dict[str, Stack]` (keys `data`, plus one key per stack added by later tasks);
  - `DataStack.tables: dict[str, dynamodb.Table]` and `DataStack.bucket: s3.IBucket`;
  - pytest fixtures `stacks`, `templates`, `CFG` and `ENV` in `tests/conftest.py`.

## Scope Limits

- the uv project, `app.py`, the shared configuration, the table-spec loader, the nag helper, and the Data stack. No other stack.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_data.py -v` passes, and `npx aws-cdk@2 synth -q` succeeds.
- The reference task's tests exist and pass:
  `test_six_tables_retained_on_demand_with_pitr`, `test_ttl_and_streams`, `test_keys_and_indexes_match_the_agent_specs`, `test_data_stack_is_termination_protected`, `test_serving_bucket_is_referenced_not_created_and_denies_plain_http`, `test_context_placeholders_are_refused`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 5 (CDK scaffold, configuration, cdk-nag and the `LbDemo-Data` stack), lines 1123–1481
