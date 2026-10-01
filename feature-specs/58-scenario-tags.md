# 58 · Tag Demo Identities with Their Scenarios

**Subsystem:** UI · **Depends on:** 23, 55 · **Reference:** ui plan, Task 6

## Goal

Tag each demo identity with the definition-of-done scenarios its real data supports, and add the staff identities.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From ui §4:*

9. **Scenario identities.** The existing ~20 demo users are tagged with the scenarios their data supports (§9.3), chosen from the curated data by a script in the plan.

## Implementation

### Files

- Create: `agent/scripts/tag_scenarios.py`
- Test: `agent/tests/test_tag_scenarios.py`

### Interfaces

- Consumes: `config/demo_users.yaml` (agent-core Task 12, extended in Task 3); the local serving set `<root>/latest.json` + `<root>/<run_id>/fct_transaction/*.parquet` (agent-core Task 12).
- Produces:
  - `SCENARIOS` (8 names);
  - `customer_facts(root: Path) -> dict[str, dict]`;
  - `assign(users: list[dict], facts: dict[str, dict]) -> tuple[list[dict], list[str]]` (the updated users and the missing scenarios);
  - a CLI that rewrites `config/demo_users.yaml` in place.

### Notes

- Scenario gaps are reported as `MISSING`, never fabricated (ui §14).

## Scope Limits

- a dev script plus its test. It never invents data: a scenario with no matching customer is reported as missing.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_tag_scenarios.py -v` passes. A run against the local serving set prints each scenario with its username, or `MISSING`.
- The reference task's tests exist and pass:
  `test_customer_facts_uses_the_60_day_window`, `test_assign_prefers_pt_for_decline_and_reports_missing`, `test_assign_reports_missing_when_no_customer_qualifies`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 6 (Tag demo identities with the scenarios their data supports), lines 1225–1435
