# 56 · Entrypoint: Control Gate, Idempotent Turns, Message Log, `turn_end`

**Subsystem:** UI · **Depends on:** 54, 22 · **Reference:** ui plan, Task 4

## Goal

Make turns idempotent per message id, log both messages, skip the graph while a human holds the session, end each turn with a `turn_end` record, and return the revised contract.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/architecture-context.md` → Invocation contract (agent ↔ BFF)
- UI plan #2 and #4 in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From ui §4:*

3. **Idempotent turns.**
   - The BFF sends `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Message-Id`.
   - If the conditional put fails, `app.py` returns the stored reply for that message instead of running the turn again.

6. **`turn_end` record.** After the reply is sent (or the turn fails), `app.py` appends one last decision record, `kind: turn_end`, with `{turn_id, route, duration_ms}`. The publisher maps it to `turn_complete`.

## Implementation

### Files

- Modify: `agent/src/bankagent/app.py`, `agent/src/bankagent/service.py`, `agent/tests/test_app.py`
- Create: `agent/tests/ui_fakes.py`
- Test: `agent/tests/test_app_ui.py`

### Interfaces

- Consumes: `SessionRepo`, `MessageLog` (Task 2); `handle`, `_bearer`, `_error` (agent-core Task 11); `AgentService.handle_turn` (agent-core Task 10).
- Produces:
  - `AgentService.handle_turn(ctx, message, turn_id: str | None = None) -> dict` always includes `turn_id`.
  - `handle(payload, headers, rt)`:
    - reads the bearer token from headers only, with no payload fallback;
    - reads the message id from header `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Message-Id` (case-insensitive), falling back to `payload["client_message_id"]`;
    - on a duplicate id, returns the stored reply, or `error: "duplicate_in_progress"`;
    - while `control ≠ agent`, logs the customer message and returns `awaiting: "human"` without calling the service;
    - otherwise logs the customer message (with `turn_id`), runs the turn, logs the assistant message with `meta = {awaiting, options, refs, summary, data_as_of}`, and appends the decision record `kind: "turn_end"`, node `turn`, payload `{duration_ms, awaiting}`.
  - Response: `{reply_text, language, awaiting, options, refs, data_as_of, turn_id, summary?}`.

## Scope Limits

- `app.py` and `service.py` (plus test updates). No graph node changes; those are Task 5.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_app.py tests/test_app_ui.py -v` passes, and the whole suite still passes.
- The reference task's tests exist and pass:
  `test_turn_logs_both_messages_turn_end_and_returns_turn_id`, `test_same_message_id_returns_stored_reply_without_second_turn`, `test_duplicate_while_running_reports_in_progress`, `test_human_control_skips_the_graph_and_logs_the_message`, `test_payload_token_is_no_longer_accepted`, `test_invalid_message_id_is_replaced_not_trusted`, `test_session_is_created_with_token_identity`, `test_bearer_header_any_case`
- **A double-tapped Send, or a retry after a network drop, with the same `client_message_id`.** Expected: one turn runs and both requests get the same reply, never a second turn or a duplicate bubble. Pinned in Task 4 (`test_same_message_id_returns_stored_reply_without_second_turn`) and Task 16 (`dedupes a reply that arrives by POST and by push`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 4 (Entrypoint: control gate, idempotent turns, message log, `turn_end`, contract fields), lines 756–1069
