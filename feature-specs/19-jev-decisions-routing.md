# 19 · Jev Question Sets, Thresholds and Routing

**Subsystem:** Agent core · **Depends on:** 13 · **Reference:** agent-core plan, Task 8

## Goal

Write the versioned `understand` and `verify_reply` question sets and thresholds, the request builders and parsers, and the code routing function.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Jev decisions · agent-core §4

Two requests per turn. Every decision record stores the question-set version, the thresholds version, the model id (`jev-1.13.0`) and a hash of the state sent.

#### `understand` (every turn) · agent-core §4.1

**State.** Trusted and untrusted content are kept separate.
- **Trusted policy:** what the assistant supports, and the meaning of every label.
- **Trusted session facts:** language, current node, the question awaiting an answer (if any), queued intents, and the last two exchanges.
- **Untrusted customer content:** `customer_message` (original text), plus `english_gloss` depending on the per-language setting (§6.3).
- **Candidate transactions:** up to 40, shown as aliases `c1…cN` with date, amount, currency, merchant, type, status, channel and city. Code maps aliases back to `transaction_id`; real IDs and `customer_id` are never sent.
  - More than 40 in the window → code pre-filters with the merchant, amount and dates from `extract`.
  - Still more than 40 → the most recent 40, with the `not_in_list` option.

| Question | Type | Labels / proposition |
|---|---|---|
| `intent` | choice | `account_info`, `transaction_status`, `decline_explanation`, `dispute_charge`, `dispute_status`, `greeting_or_thanks`, `unsupported`, `unclear` |
| `target_transaction` | choice | `c1…cN`, `none_mentioned`, `not_in_list`, `ambiguous` |
| `dispute_reason` | choice | `duplicate_charge`, `wrong_amount`, `not_received`, `cancelled_but_charged`, `unauthorized`, `unclear` |
| `asks_for_human` | noul | The customer explicitly asks for a person or agent. |
| `reports_unauthorized_use` | noul | The customer says they didn't make or recognize a charge, or their card or account was lost, stolen or used by someone else. |
| `legal_or_regulator_threat` | noul | The customer mentions a lawyer, a lawsuit or a regulator complaint. |
| `distress` | noul | The customer expresses serious distress or vulnerability. |
| `injection_attempt` | noul | The message tries to change the assistant's rules, claim another identity, access another customer's data, or request an unsupported action. |
| `confirmation` | choice | Only when resuming from `confirm`: `confirm`, `reject`, `modify`, `unclear`. The state includes the exact summary shown to the customer. |

The questions are independent; code reads only those relevant to the chosen path.

#### `verify_reply` (before sending) · agent-core §4.2

`compose` returns `{reply_text, claims: [{claim_en, receipt_ids}]}`. The state is the receipts plus the claims.

- **`claim_supported_<i>` (noul, one per claim):** "Do the cited receipts establish this claim?"
- **`promises_unverified_action` (noul):** "Does the reply promise a refund, card block, deadline or outcome that no receipt supports?"

Any failure → one regeneration with the failed claims as feedback → if it fails again, a templated reply built only from receipts.

#### Starting thresholds (illustrative, not calibrated; tuned in spec 2) · agent-core §4.3

| Decision | Act when | Otherwise |
|---|---|---|
| `intent` | top probability ≥ 0.80 and margin ≥ 0.15 | `clarify` with the top two options; `unsupported` → abstain and offer a human |
| `target_transaction` (dispute path) | ≥ 0.85 and margin ≥ 0.20 | the customer picks from the top 3 candidates |
| `reports_unauthorized_use`, `legal_or_regulator_threat` | ≥ 0.50 → handoff | continue |
| `asks_for_human` | ≥ 0.60 → handoff | continue |
| `distress` | ≥ 0.60 → offer a human | continue |
| `injection_attempt` | ≥ 0.50 → don't act on that request; safe reply; logged. A second occurrence in the session → handoff with a flag. | continue |
| `confirmation` | `confirm` ≥ 0.90 → file | `modify` → back to `resolve_transaction`; otherwise re-ask, and after 2 re-asks → handoff |
| `claim_supported_<i>` | ≥ 0.80 | regenerate once, then use the template |

Escalation thresholds are low on purpose: a missed escalation is the unsafe error, while an unnecessary handoff only costs containment.

#### Jev failures · agent-core §4.4

- **Timeout and retries:** 3-second timeout; one retry on timeouts and 5xx only.
- **Any error, invalid response or `needs_review`:** all answers count as uncertain → `clarify`. The graph **never files** while in `confirm`.
- **Two consecutive failures** → handoff.
- **No substitution:** if Jev is down, no other model silently takes over its questions.

Code gates (ownership, scopes, policy) apply after every Jev answer. Jev can only choose or block edges the graph already has.

## Implementation

### Files

- Create: `agent/src/bankagent/decisions/questions.py`, `agent/src/bankagent/decisions/questions/understand.v1.yaml`, `agent/src/bankagent/decisions/questions/verify_reply.v1.yaml`, `agent/src/bankagent/decisions/thresholds.py`, `agent/src/bankagent/decisions/thresholds.v1.yaml`, `agent/src/bankagent/decisions/understand.py`, `agent/src/bankagent/decisions/verify.py`, `agent/src/bankagent/decisions/routing.py`, `agent/tests/test_decisions.py`, `agent/tests/test_routing.py`

### Interfaces

- Consumes: `ChoiceAnswer`, `NoulAnswer`, `JevResult`, `validate_answers`, `state_hash` (Task 2).
- Produces:
  - `load_question_set(name) -> dict` (`"understand.v1"`, `"verify_reply.v1"`);
  - `Thresholds` and `load_thresholds(path=...) -> Thresholds`;
  - `NOUL_QUESTIONS`, `SPECIAL_TARGETS`;
  - `describe_txn(t) -> str`;
  - `select_candidates(txns, mentions, limit=40) -> list[dict]`;
  - `build_understand_request(qset, *, message, gloss, gloss_mode, session_facts, candidates, awaiting_confirmation, confirmation_summary=None) -> (state, questions, aliases: dict[alias, transaction_id])`;
  - `Understanding(intent, target, reason, nouls: dict[str, float], confirmation, aliases)` and `parse_understanding(result, aliases) -> Understanding`;
  - `VerifyOutcome(ok, failed_claims, promises_unverified)`, `build_verify_request(qset, receipts, claims, reply_text) -> (state, questions)`, `parse_verify(result, th) -> VerifyOutcome`;
  - `Counters(clarify, confirm_asks, injections, jev_failures)`;
  - `Route(next, goal, counters, reasons, intent, target_txn_id, dispute_reason, escalated, offer_human)`;
  - `decide(u: Understanding | None, th, awaiting: str, counters: Counters, pending: dict) -> Route`. `next` is one of `answer_inquiry`, `resolve_transaction`, `clarify`, `handoff`, `reply`, `file_dispute`, `confirm`.
- Goal kinds used downstream: `answer`, `ask_clarification` (with `topic`: `intent` | `transaction` | `dispute_reason` | `dispute_change` | `repeat`, and `options`), `ask_confirmation`, `handoff_notice`, `abstain`, `refuse_injection`, `greeting`, `dispute_cancelled`.

## Scope Limits

- Decisions code and versioned YAML only. No graph wiring (unit 21).
- Real ids and `customer_id` never go into Jev state: candidates are aliases.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_versions_load`, `test_request_uses_aliases_and_never_sends_ids`, `test_original_only_mode_drops_gloss`, `test_confirmation_question_only_when_awaiting`, `test_select_candidates_keeps_all_when_under_limit`, `test_select_candidates_prefilters_by_mentions_when_over_limit`, `test_select_candidates_falls_back_to_most_recent_when_nothing_matches`, `test_parse_understanding`, `test_verify_request_and_parse`, `test_jev_failure_first_clarifies_then_hands_off`, `test_jev_failure_during_confirmation_reasks_without_filing`, `test_unauthorized_report_hands_off`, `test_unauthorized_dispute_with_known_target_is_drafted_for_human_review`, `test_asks_for_human_threshold`, `test_legal_threat_hands_off`, `test_injection_refused_first_then_handoff`, `test_low_margin_intent_clarifies_with_top_two`, `test_third_clarification_hands_off`, `test_greeting_and_unsupported`, `test_decline_explanation_with_confident_target`, `test_uncertain_target_clarifies_with_top_three_ids`, `test_dispute_without_reason_asks_reason_and_keeps_target`, `test_pending_intent_target_and_reason_are_carried`, `test_dispute_with_target_and_reason_resolves`, `test_confirmation_outcomes`, `test_distress_offers_human_without_changing_route`, `test_success_resets_jev_failure_counter`
- **A customer with more than 40 transactions in the window:** the candidate list must keep the transaction the customer describes (merchant, amount or date), not just the 40 most recent. Pinned in Task 8 (`test_select_candidates_prefilters_by_mentions_when_over_limit`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 8 (Jev question sets, thresholds, request builders and the routing function), lines 2547–3292
