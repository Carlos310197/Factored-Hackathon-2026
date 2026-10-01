# 15 · Dispute Policy (labeled synthetic)

**Subsystem:** Agent core · **Depends on:** 12 · **Reference:** agent-core plan, Task 4

## Goal

Encode the labeled synthetic dispute policy as a versioned YAML file plus pure evaluation functions that return a pass/fail per rule.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Dispute policy (`policy/dispute_policy.yaml`, labeled synthetic, versioned) · agent-core §5

No money moves. An **automated resolution** for a dispute means a valid case, confirmed by the customer and filed in our store, verified by read-back, with a case number returned.

| Rule | Value |
|---|---|
| Ownership | The transaction belongs to the session's customer; otherwise `not_found` (the same response as a missing transaction). |
| Status | Only `Approved` can be disputed. `Declined` → decline explanation; `Pending` → "wait until it posts"; `Reversed` → already refunded. |
| Types | `Purchase`, `Withdrawal`, `Payment`, `Transfer`. `Deposit` and `Adjustment` can't be disputed. |
| Time window | Transaction date within 60 days before `max_process_date` |
| Duplicates | No existing dispute for the `transaction_id` (enforced by conditional write, §7.2) |
| Reasons | `duplicate_charge`, `wrong_amount`, `not_received`, `cancelled_but_charged`, `unauthorized` |
| Automated intake | All rules pass, reason ≠ `unauthorized`, and `amount_usd` ≤ 500 → file with `route=automated`, `status=submitted` after confirmation |
| Human review | Reason `unauthorized`, `is_fraud = true`, `fraud_score` > 30, `amount_usd` > 500, or an escalation signal (§4.3) → record the draft with `route=human_review`, `status=pending_review`, and hand off |

`fraud_score` is on a 0–100 scale. In a 30-day sample, every non-fraud transaction scored ≤ 30 (max 30.0, median 15.0), while `is_fraud = true` transactions had a median of 52.1. The cutoff 30 separates them; spec 2 re-checks it on the full history.

`create_dispute` re-runs `policy.evaluate()` inside the tool, so no graph node is trusted blindly. Each rule's result goes into the decision record and, on handoff, into `policy_checks`.

## Implementation

### Files

- Create: `agent/src/bankagent/policy/__init__.py`, `agent/src/bankagent/policy/dispute_policy.yaml`, `agent/src/bankagent/policy/dispute.py`, `agent/tests/test_policy.py`

### Interfaces

- Consumes: nothing.
- Produces:
  - `DisputePolicy.load(path=DEFAULT_PATH)`;
  - `.evaluate(txn: dict, reason: str, as_of: date, already_disputed: bool, escalation: bool = False) -> PolicyResult`;
  - `PolicyResult(outcome: "automated"|"human_review"|"not_disputable", rules: tuple[Rule, ...], redirect: str | None, version: str)` with `.triggers() -> list[str]`;
  - `Rule(name, passed, detail)`.
- Redirect values: `explain_decline`, `wait_pending`, `already_reversed`, `not_disputable_type`, `out_of_window`, `already_disputed`, `not_disputable`.
- Trigger codes: `unauthorized_reason`, `fraud_flag`, `fraud_score_high`, `amount_over_limit`, `amount_unknown`, `escalation_signal`.
- `txn` keys used: `transaction_status`, `transaction_type`, `process_date` (ISO date string or date), `amount`, `currency`, `amount_usd`, `is_fraud`, `fraud_score`.

## Scope Limits

- Pure code and the YAML file. No I/O, no tools.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_version_is_labeled_synthetic`, `test_happy_path_is_automated`, `test_non_approved_status_redirects`, `test_non_disputable_types`, `test_window_boundaries`, `test_already_disputed`, `test_human_review_triggers`, `test_fraud_score_30_is_still_automated`, `test_amount_500_is_still_automated`, `test_escalation_signal_forces_human_review`, `test_usd_amount_used_when_amount_usd_missing`, `test_unknown_usd_amount_goes_to_human_review`, `test_is_fraud_string_true_counts`, `test_unknown_reason_is_error`
- **USD transactions with an empty `amount_usd`** (the raw data leaves it blank for USD rows): the policy must use `amount` for USD and send non-USD rows with an unknown `amount_usd` to human review, never to automation. Pinned in Task 4 (`test_usd_amount_used_when_amount_usd_missing`, `test_unknown_usd_amount_goes_to_human_review`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 4 (Dispute policy (labeled synthetic, pure code)), lines 1007–1251
