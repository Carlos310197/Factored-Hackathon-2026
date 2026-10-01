# 45 · Fault Injection, Test Tokens and the Conversation Runner

**Subsystem:** Evaluation · **Depends on:** 44, 21 · **Reference:** evaluation plan, Task 6

## Goal

Drive one conversation between the persona and the in-process agent, inject faults through the agent's clients, and capture transcript, records and store snapshots.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Harness (`eval/run.py`) · evaluation §4.5

- Calls the agent's `handle_turn()` in-process (agent-core §9.1) against DynamoDB Local and the local serving set, with live Claude and Jev. Each conversation gets a fresh session through the identity service.
- Faults are injected through the injectable clients (Jev raising, the serving reader raising, a DynamoDB client returning throttling errors). Expired sessions use the identity service's short-TTL token.
- Each conversation stores: transcript, decision records, store snapshot before and after, per-turn latency, token usage per provider.
- 120 goals × 3 repetitions = 360 conversations, 8 in parallel. Results go to `eval/runs/<run_id>/conversations.jsonl`; the run is resumable and skips finished `(goal_id, rep)` pairs.

## Implementation

### Files

- Create: `eval/src/evalkit/faults.py`, `eval/src/evalkit/conversation.py`, `eval/tests/test_conversation.py`

### Interfaces

- Consumes:
  - `bankagent.decisions.jev.JevError`, `bankagent.data.serving.ServingError`, `bankagent.tools.write.WriteTools(store, policy)`;
  - `bankagent.auth.tokens.generate_keypair() -> (private_pem, public_pem)`, `jwks_from_public(public_pem, kid)`, `issue_token(private_pem, kid, issuer, audience, customer_id, session_id, scopes, lang, ttl_s=900, now=None)`, `verify_token(token, jwks, issuer, audience)` (raises `AuthError("expired")`);
  - agent store shape: `store.disputes.list_for_customer(cid)`, `store.handoffs.list_by_status(status)`, `store.log.list(session_id)`;
  - `PersonaTurn`, `PersonaError`, `check_message` (Task 5).
- Produces:
  - `evalkit.faults`: `FAULTS = ("jev_down", "serving_down", "dynamo_throttle")`, `FailingProxy`, `apply_fault(deps, fault)`;
  - `evalkit.conversation`: `SCOPES`, `HANDOFF_STATUSES`, `TokenIssuer(private_pem, public_pem, kid, issuer, audience)` with `.generate(issuer, audience)`, `.jwks`, `.issue(customer_id, session_id, lang, expired=False)`; `snapshot(store, customer_id, session_id) -> {"disputes", "handoffs", "records", "customer_case_ids"}`; `agent_text(reply) -> str`; `run_conversation(card, rep, *, handle_fn, rt, store, persona, tokens, session_id=None, clock=time.monotonic) -> dict`.
- Conversation record: `{"goal_id", "rep", "session_id", "turns": [{"i", "customer", "reply", "latency_ms", "token_expired"}], "end_reason": "done"|"max_turns"|"expired"|"persona_discarded"|"harness_error", "violations", "persona_usage", "before", "after", "error"?}`.

## Scope Limits

- `faults.py` and `conversation.py`. Faults never touch the real store.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_turns_latency_and_done`, `test_persona_violation_discards`, `test_expired_fault_sends_an_expired_token_on_turn_two`, `test_max_turns`, `test_errors_become_harness_errors`, `test_snapshot_filters_by_session_but_keeps_customer_case_ids`, `test_agent_text_includes_options`, `test_jev_down_fault_patches_deps`, `test_dynamo_fault_leaves_the_real_store_untouched`, `test_unknown_fault_is_refused`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 6 (Fault injection, test tokens and the conversation runner), lines 2231–2546
