# 13 · Jev Client with Strict Validation

**Subsystem:** Agent core · **Depends on:** 12 · **Reference:** agent-core plan, Task 2 · **[live]**

## Goal

Build the TypeSafe Jev client: typed answers, strict validation, one retry on timeouts and 5xx only, and a live smoke test with synthetic data.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `feature-specs/19-jev-decisions-routing.md` → Jev failures · agent-core §4.4
- `context/project-overview.md` → Dataset Facts → agent-core §2 (the Jev constraints bullet)

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/decisions/__init__.py`, `agent/src/bankagent/decisions/jev.py`, `agent/tests/test_jev.py`, `agent/scripts/smoke_jev.py`, `agent/docs/smoke-results.md`

### Interfaces

- Consumes: nothing.
- Produces:
  - `JevClient(api_key, url=..., model="jev-1.13.0", timeout=3.0, transport=None)` with `.decide(state, questions: dict) -> JevResult`;
  - `JevResult(answers: dict[str, ChoiceAnswer | NoulAnswer], usage: dict, latency_ms: int, state_hash: str, model: str)`;
  - `ChoiceAnswer(label, probabilities, confidence)` with `.p`, `.margin` and `.top(n, exclude=frozenset()) -> list[str]`;
  - `NoulAnswer(p)`;
  - `JevError`, `validate_answers(questions, body) -> dict`, `state_hash(state) -> str`.

## Scope Limits

- `decisions/jev.py`, its tests and the smoke script. No question sets or routing (unit 19).
- The smoke test uses synthetic data only, and runs once the owner approves.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  `test_parses_typed_answers_and_sends_model_and_auth`, `test_missing_answer_is_error`, `test_label_outside_criteria_is_error`, `test_noul_out_of_range_is_error`, `test_retries_once_on_5xx_then_succeeds`, `test_two_5xx_fail_after_one_retry`, `test_4xx_is_not_retried`, `test_timeout_is_retried_once`, `test_empty_key_rejected`
- The smoke result is recorded in `agent/docs/smoke-results.md`.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 2 (Jev client with strict validation and a live smoke test), lines 318–657
