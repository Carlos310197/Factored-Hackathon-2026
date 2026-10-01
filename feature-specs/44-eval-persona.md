# 44 · Persona Client and Rule Checks

**Subsystem:** Evaluation · **Depends on:** 43 · **Reference:** evaluation plan, Task 5

## Goal

Implement the OpenCode-served simulated customer and the rule checks that discard runs where it breaks character.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Persona (`eval/persona.py`) · evaluation §4.4

- Provider and model id configured in `eval/config.yaml` (an OpenCode-served model); temperature fixed; the id is recorded on every run.
- Input: the goal card (without `expected`) and the conversation so far. Output: the next customer message in the goal's language, or `[DONE]`.
- Rule checks after each message: no English in an ES/PT goal (except the English-message goal), no ids, stays under 600 characters. A run where the persona breaks character is discarded, counted and reported; it is not silently retried.

## Implementation

### Files

- Create: `eval/src/evalkit/persona.py`, `eval/tests/test_persona.py`

### Interfaces

- Consumes: `GoalCard` (Task 4).
- Produces:
  - `DONE = "[DONE]"`, `ID_RE`, `PersonaError`, `PersonaTurn(text: str | None, done: bool, usage: dict, latency_ms: int)`;
  - `system_prompt(card) -> str`; `check_message(card, text) -> list[str]` (violations among `too_long`, `id_leak`, `out_of_character`, `wrong_language`);
  - `PersonaClient(base_url, api_key, model, temperature, timeout_s=30.0, http=None)` with `.next(card, history: list[{"customer", "agent"}]) -> PersonaTurn` and `PersonaClient.from_config(persona_cfg)`;
  - smoke entry `python -m evalkit.persona --smoke --live`.

## Scope Limits

- `persona.py` and its tests, with a mocked HTTP endpoint. No live calls.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_message_and_usage`, `test_history_roles_are_mirrored`, `test_done_is_detected`, `test_one_retry_on_5xx_then_success`, `test_client_errors_and_empty_messages_raise`, `test_system_prompt_hides_labels_and_sets_language`, `test_rule_checks`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 5 (Persona client and rule checks), lines 1963–2227
