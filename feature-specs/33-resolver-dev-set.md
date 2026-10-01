# 33 · Resolver Dev-Set Builder

**Subsystem:** Transaction resolver · **Depends on:** 29, 30 · **Reference:** resolver plan, Task 8

## Goal

Build the 300-message real-text dev set: simulator picks, the Claude dev writer writes the message, and the real `extract` processes it.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Dev set (300 cases: 150 ES, 150 PT) · resolver §5.3

1. `make_dev_set.py` draws dev-split cases through the simulator: history, target, style.
2. Claude (the `compose` model) writes a customer message in ES or PT from the target transaction's fields and the style instructions. It is never shown the other candidates.
3. The real `extract` processes the message, and its output is cached.
4. The label (target `transaction_id` or `not_in_list`) is known by construction.
5. Carlos reviews 30 messages for realism, and any that are unusable are regenerated. The regeneration count is reported.
6. Stored in `resolver/data/dev_v1.jsonl`, committed. Transaction fields only, no customer PII (the curated marts contain none).

Sending curated transaction fields to Bedrock falls under the same open data-use approval as the agent itself (agent-core §12).

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/devset.py`, `agent/tests/test_resolver_devset.py`

### Interfaces

- Consumes: `call_json`, `LLMError`, `RoleConfig`, `extract` (agent-core and Task 4); `simulate` (Task 3); `public`, `country_of` (Task 5); `ScriptedLLM` (Task 5).
- Produces:
  - `WRITER_SYSTEM`, `WRITER_SCHEMA`, `details_en(case) -> list[str]`, `write_message(client, cfg, case, lang, flavor) -> LLMCall`;
  - `build_dev_set(histories, sim_cfg, seed, n, client, models, set_name="dev") -> (rows, skipped)`. Each row is `{case_id, set, lang, flavor, slice, anchor, country, target_id, target, candidates, style, details_en, message, extraction: {mentions, language_detected, english_gloss}, versions}`.

## Scope Limits

- The builder and its tests (stubbed LLM). Building the real set is unit 38.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_dev_rows_are_balanced_labeled_and_private`, `test_writer_sees_only_the_details`, `test_llm_failures_are_skipped_not_fatal`, `test_details_render_the_style`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 8 (Dev-set builder), lines 2642–2818
