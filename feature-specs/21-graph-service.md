# 21 · LangGraph Workflow and the Agent Service

**Subsystem:** Agent core · **Depends on:** 14–20 · **Reference:** agent-core plan, Task 10

## Goal

Wire the nodes into the LangGraph state machine with interrupts for clarification and confirmation, and expose `handle_turn()` as the agent service.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `context/architecture-context.md` → Agent Core (one turn); Failure Handling · agent-core §8
- `feature-specs/19-jev-decisions-routing.md` (routing outcomes and thresholds)

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/graph/__init__.py`, `agent/src/bankagent/graph/state.py`, `agent/src/bankagent/graph/deps.py`, `agent/src/bankagent/graph/nodes.py`, `agent/src/bankagent/graph/build.py`, `agent/src/bankagent/service.py`, `agent/tests/harness.py`, `agent/tests/test_graph_paths.py`, `agent/tests/test_graph_failures.py`
- Modify: `agent/tests/fakes.py` (append `FakeJev`), `agent/tests/conftest.py` (append `ddb_store`)

### Interfaces

- Consumes everything from Tasks 1–9:
  - `ReadTools`, `WriteTools` and their exceptions;
  - `Store`, `DisputePolicy`;
  - `build_understand_request`, `parse_understanding`, `select_candidates`, `describe_txn`;
  - `build_verify_request`, `parse_verify`;
  - `decide`, `Counters`;
  - `extract`, `compose`, `open_questions`, `LLMError`;
  - templates, `build_packet`, `unknown_ids`, `new_id`.
- Produces:
  - `Deps(read, write, store, policy, jev, llm_client, models, thresholds, understand_qs, verify_qs, gloss_mode={"es": "original_plus_gloss", "pt": "original_plus_gloss"}, clock=time.monotonic)`;
  - `build_graph(deps, checkpointer)`;
  - `AgentService(deps, checkpointer, turn_budget_s=20.0, recursion_limit=25)` with `.handle_turn(ctx, message) -> dict` (reply contract `{reply_text, language, awaiting, options, refs, data_as_of}`) and `.state(ctx) -> dict`;
  - `run_conversation(service, ctx, messages) -> list[dict]`.
- Identity per turn: nodes read `SessionContext` from `config["configurable"]["ctx"]`, which the service sets from the verified token on every turn. Identity is never read from the checkpoint.
- Test harness: `tests/harness.py::make_harness(store, serving_uri, specs, llm=None, verify=True, clock=None, recursion_limit=25, turn_budget_s=20.0) -> Harness` with `.turn(message, ctx=CTX_ES)`, `.state(ctx=CTX_ES)`, `.log_kinds(ctx=CTX_ES)`, plus `.jev`, `.llm`, `.store`. Constants `CTX_ES`, `CTX_ES2`, `CTX_PT`, `CTX_READ_ONLY`.

## Scope Limits

- Graph, service and scenario tests (stubbed Claude and Jev, DynamoDB Local). No entrypoint (unit 22).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_account_inquiry_es`, `test_decline_explanation_pt`, `test_dispute_confirm_file_verify`, `test_ambiguous_intent_clarifies_then_answers`, `test_unsupported_request_abstains`, `test_unrecognized_charge_drafts_dispute_and_hands_off`, `test_over_limit_dispute_goes_to_human_review_without_confirmation`, `test_legal_threat_hands_off_with_high_priority`, `test_dispute_of_declined_payment_explains_the_decline`, `test_second_request_is_queued_and_offered`, `test_other_language_replies_in_session_language`, `test_session_keeps_its_run_id_when_pointer_moves`, `test_jev_down_once_clarifies_twice_hands_off`, `test_jev_down_during_confirmation_never_files`, `test_unclear_confirmation_three_times_hands_off_without_filing`, `test_modify_during_confirmation_asks_what_to_change`, `test_duplicate_dispute_is_not_filed_twice`, `test_injection_refused_then_handed_off`, `test_compose_failure_uses_template`, `test_unverified_claims_regenerate_once_then_template`, `test_verify_outage_uses_template`, `test_foreign_id_in_reply_is_blocked`, `test_serving_unavailable_offers_human`, `test_missing_dispute_scope_abstains_without_filing`, `test_turn_budget_exhausted_uses_template_without_compose`, `test_extract_failure_still_answers_from_original_text`, `test_recursion_limit_returns_safe_reply`
- **A message in English or another unsupported language:** the reply must be in the session language, never in the language of the message. Pinned in Task 10 (`test_other_language_replies_in_session_language`).
- **The serving pointer moves to a new run mid-session:** the session keeps answering from the `run_id` it started with. Pinned in Task 10 (`test_session_keeps_its_run_id_when_pointer_moves`).
- Scenario tests cover the agent-core §10 graph scenarios in both languages.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 10 (LangGraph workflow and the agent service), lines 3953–4971
