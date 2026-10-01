# 54 · Agent: `sessions` and `conversation_messages` Tables and Streams

**Subsystem:** UI · **Depends on:** 17 · **Reference:** ui plan, Task 2

## Goal

Add the two new agent tables with their repositories, and turn on Streams for the tables the UI listens to.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/architecture-context.md` → Agent state · agent-core §7.2

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Change requests to the agent core (this unit)

*From ui §4 (items 1, 2 and 4; the rest are units 55, 56, 58 and 64):*

All additive. They are tracked like the pipeline's sort-order request (agent-core §9.3).

1. **`sessions` table.**
   - Fields: PK `session_id`; `customer_id`, `language`, `control` (`agent` | `human:<agent_id>`), `created_at`.
   - Written when a session starts; `control` changes only through the BFF's takeover and return transactions.
   - `app.py` reads it before running the graph, and returns `awaiting: human` without running it when a human holds the session.
2. **`conversation_messages` table.**
   - Keys: PK `session_id`, SK `ts#seq`. Fields: `message_id`, `role`, `text`, `parts`, `turn_id?`, `author?`.
   - 90-day TTL, matching `decision_records`. Streams on.
   - `app.py` writes the customer message (a conditional put on `message_id`, which makes it idempotent) and each assistant reply. The BFF writes agent and system messages.
   - `transcript_ref` in `handoff.v1` resolves to this partition.

4. **Streams on** `handoffs` and `decision_records`.

## Implementation

### Files

- Modify: `agent/src/bankagent/store/tables.py`, `agent/src/bankagent/store/repos.py`, `agent/tests/test_store.py` (the table-list assertion)
- Test: `agent/tests/test_store_ui.py`

### Interfaces

- Consumes: `_conditional_put`, `AlreadyExists`, `to_dynamo`/`from_dynamo`, `Store` (agent-core Task 6); `new_id` (agent-core Task 1).
- Produces:
  - `SessionRepo(table, clock=time.time)`: `.ensure(session_id, customer_id, lang) -> dict`, `.get(session_id) -> dict | None`, `.control(session_id) -> str` (default `"agent"`).
  - `MessageLog(table, clock=time.time)`:
    - `.claim(session_id, message_id) -> dict | None` returns `None` when the id is new (and marks it as running), otherwise the existing marker;
    - `.store_reply(session_id, message_id, reply: dict) -> None`;
    - `.append(session_id, role, text, *, message_id=None, turn_id=None, author=None, meta=None) -> dict`;
    - `.list(session_id, after: str | None = None) -> list[dict]`.
  - `Store` gains `sessions: SessionRepo | None = None` and `messages: MessageLog | None = None`, both filled by `Store.connect`.
  - Message item fields: `session_id, sk ("<iso-ts-µs>#<message_id>"), kind="message", message_id, role (customer|assistant|agent|system), text, turn_id?, author?, meta?, ts, ttl`.
  - Streams (`NEW_IMAGE`) are on `handoffs`, `decision_records` and `conversation_messages`.

### Notes

- Idempotency markers live in `conversation_messages` (UI plan #4).
- `sessions` also gets a 90-day TTL later (deployment plan #8, unit 78).

## Scope Limits

- storage only. No entrypoint or graph changes.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_store.py tests/test_store_ui.py -v` passes, and the whole suite still passes.
- The reference task's tests exist and pass:
  `test_new_tables_exist_and_streams_are_on`, `test_session_ensure_is_idempotent_and_control_defaults_to_agent`, `test_claim_marks_new_ids_and_returns_existing_marker`, `test_append_and_list_in_order_after_cursor_without_markers`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 2 (`sessions` and `conversation_messages` tables, Streams, and their repositories), lines 189–460
