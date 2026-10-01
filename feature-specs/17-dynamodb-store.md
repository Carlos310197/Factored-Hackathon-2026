# 17 · DynamoDB Tables and Repositories

**Subsystem:** Agent core · **Depends on:** 12 · **Reference:** agent-core plan, Task 6

## Goal

Define the agent's four tables and the repositories for disputes, handoffs and decision records, with a local DynamoDB compose file.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `context/architecture-context.md` → Agent state · agent-core §7.2 and §7.4

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/store/__init__.py`, `agent/src/bankagent/store/codec.py`, `agent/src/bankagent/store/tables.py`, `agent/src/bankagent/store/repos.py`, `agent/scripts/create_tables.py`, `agent/docker-compose.yml`, `agent/tests/test_store.py`

### Interfaces

- Consumes: nothing from earlier tasks.
- Produces:
  - `to_dynamo(v)`, `from_dynamo(v)`;
  - `TABLE_SPECS`, `table_name(prefix, name) -> str`, `create_tables(client, prefix) -> list[str]` (idempotent);
  - `AlreadyExists`;
  - `DisputeRepo(table)`: `put_new(item)` (conditional on `transaction_id`), `get(transaction_id)` (strongly consistent), `list_for_customer(customer_id)` (newest first);
  - `HandoffRepo(table)`: `put(item)`, `get(handoff_id)`, `list_by_status(status)`;
  - `DecisionLog(table, clock=time.time)`: `append(session_id, turn_id, node, kind, payload, versions=None, latency_ms=None)`, `list(session_id)`;
  - `Store(disputes, handoffs, log)` with `Store.connect(prefix, region, endpoint=None)`.

## Scope Limits

- Store code, the table-creation script and the DynamoDB Local compose file. No tools.
- The checkpoints table uses `PK`/`SK` and a `ttl` attribute (agent-core plan #4).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_create_tables_idempotent_with_expected_keys`, `test_dispute_conditional_put_and_consistent_get`, `test_list_for_customer_newest_first`, `test_handoffs_by_status`, `test_decision_log_sequence_ttl_and_floats`, `test_codec_roundtrip_drops_nulls`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 6 (DynamoDB tables and repositories), lines 1736–2064
