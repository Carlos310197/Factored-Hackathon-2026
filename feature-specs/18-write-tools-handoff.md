# 18 · Write Tools, Handoff Packet and the Reply Id Guard

**Subsystem:** Agent core · **Depends on:** 15, 16, 17 · **Reference:** agent-core plan, Task 7

## Goal

File disputes with read-back verification, build and write `handoff.v1` packets, and block replies that mention ids not belonging to the session.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `feature-specs/16-serving-read-tools.md` → Tools · agent-core §7.1
- `context/architecture-context.md` → Agent state (handoff packet, DynamoDB tables); Access Controls and Secrets → Prompt-injection defense · agent-core §6.4

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/tools/write.py`, `agent/src/bankagent/handoff/__init__.py`, `agent/src/bankagent/handoff/packet.py`, `agent/src/bankagent/guards.py`, `agent/tests/test_write_tools.py`, `agent/tests/test_handoff_and_guards.py`

### Interfaces

- Consumes:
  - `ToolResult`, `NotFound`, `ReadTools` (Task 5);
  - `Store`, `AlreadyExists` (Task 6);
  - `DisputePolicy` (Task 4);
  - `SCOPE_DISPUTE`, `new_id` (Task 1).
- Produces:
  - `WriteTools(store, policy, now=...)` with:
    - `create_dispute(ctx, txn, reason, statement, as_of, escalation, session_id, turn_id, language) -> ToolResult` (source `"disputes"`; data holds `VERIFIED_FIELDS`, `created_at` and `policy_rules`);
    - `verify_dispute(ctx, expected: dict, as_of) -> ToolResult` (source `"disputes.verify"`; data `{verified, mismatches, dispute_id, status, created_at, record_hash}`);
    - `list_disputes(ctx, as_of) -> ToolResult` (source `"disputes"`, data list);
    - `create_handoff(ctx, packet: dict, as_of: str) -> ToolResult` (source `"handoffs"`).
  - Exceptions: `AlreadyDisputed(existing)`, `PolicyRejected(result)`, `WriteFailed`, `HandoffFailed`.
  - `HandoffPacket` (pydantic, `schema_version="handoff.v1"`), `priority_for(codes) -> str`, and `build_packet(*, session_id, customer_id, language, data_as_of, reason_codes, customer_request, receipts, actions, decisions, policy_checks, open_questions, now) -> HandoffPacket`.
  - `unknown_ids(text, allowed: set[str]) -> set[str]`.

## Scope Limits

- `tools/write.py`, `handoff/packet.py`, `guards.py`. `create_dispute` re-runs `policy.evaluate()` inside the tool.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_automated_dispute_written_then_verified`, `test_second_dispute_on_same_transaction`, `test_over_limit_is_recorded_for_human_review`, `test_escalation_forces_human_review`, `test_declined_rejected_by_policy_and_not_written`, `test_requires_dispute_scope`, `test_foreign_transaction_is_not_found`, `test_unknown_write_outcome_resolved_by_read_back`, `test_unknown_write_outcome_twice_without_record_fails`, `test_verify_detects_mismatch`, `test_list_disputes_scoped_to_customer`, `test_packet_shape_and_priority`, `test_priority_for`, `test_packet_rejects_more_than_three_open_questions`, `test_create_handoff_writes_and_reads_back`, `test_unknown_ids_flags_foreign_and_customer_ids`, `test_unknown_ids_ignores_plain_text`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 7 (Write tools, handoff packet and the reply id guard), lines 2068–2543
