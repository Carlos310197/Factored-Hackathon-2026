# 57 · Trace Payloads: Thresholds, Aliases and the Confirmation Summary

**Subsystem:** UI · **Depends on:** 56 · **Reference:** ui plan, Task 5

## Goal

Add the flat thresholds and alias map to the understand record, and the confirmation `summary` built from the same draft that gets filed.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- UI plan #1 and #3 in `progress-tracker.md` → Architecture Decisions
- `context/architecture-context.md` → Invocation contract (the `summary` field)

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/decisions/trace_payload.py`
- Modify: `agent/src/bankagent/graph/nodes.py`
- Test: `agent/tests/test_trace_payloads.py`

### Interfaces

- Consumes: `Thresholds`, `load_thresholds` (agent-core Task 8).
- Produces:
  - `thresholds_map(t: Thresholds) -> dict[str, float]` with keys `intent`, `intent.margin`, `target_transaction`, `target_transaction.margin`, `confirmation`, `injection_attempt`, plus every key of `handoff_noul` and `offer_human_noul`.
  - `alias_view(aliases: dict[str, str], candidates: list[dict]) -> dict[str, dict]`, where each value is `{transaction_id, merchant, amount, currency, date}`.
  - `confirmation_payload(txn: dict, reason: str | None) -> dict`, shaped `{merchant, date, amount, currency, reason_code}`.
  - The understand `jev` record payload gains `thresholds` and `aliases`. The reply dict gains `summary` when `awaiting == "confirmation"`.

## Scope Limits

- a new pure module, plus two small edits in `graph/nodes.py`.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_trace_payloads.py -v` passes, and `uv run pytest -q` still passes.
- The reference task's tests exist and pass:
  `test_thresholds_map_is_flat_and_complete`, `test_alias_view_keeps_only_known_candidates`, `test_confirmation_payload_uses_the_same_draft_fields`, `test_confirmation_payload_falls_back_to_timestamp_date`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 5 (Trace payloads: thresholds and aliases on the understand record, `summary` on confirmation replies), lines 1073–1221
