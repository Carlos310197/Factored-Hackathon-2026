# 29 · Agent-Core Changes I: Extract Hints, Dev Writer, understand.v2

**Subsystem:** Transaction resolver · **Depends on:** 28, 19, 20 · **Reference:** resolver plan, Task 4

## Goal

Extend `extract` with three hints (`extract.v2`), add the `dev_writer` Claude role, and let the understand request carry match scores (`understand.v2`).

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver
- Resolver plan #6 (dev writer, `extract.v2`) in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From resolver §3.2 (items 2, 4, 5 and 6 are unit 37):*

1. **`extract` schema:** `mentions` gains three nullable fields: `type_hint` (`purchase|withdrawal|transfer|payment|deposit`), `channel_hint` (`atm|pos|app|web|branch`), and `city`. This must land in agent-core Task 9 before the dev set is built.

3. **Jev question set `understand.v2`:**
   - `describe_txn` appends `· match <p>` (two decimals);
   - `target_transaction` gets one added instruction line: "The match score comes from structured matching of amount, date, merchant, type, channel and city; it ignores the wording. Use it as evidence, not as the answer."
   - Every other question is unchanged.

## Implementation

### Files

- Modify: `agent/src/bankagent/llm/extract.py`, `agent/src/bankagent/llm/models.yaml`, `agent/src/bankagent/decisions/understand.py`, `agent/tests/fakes.py`, `agent/tests/test_llm.py`, `agent/tests/test_decisions.py`
- Create: `agent/src/bankagent/decisions/questions/understand.v2.yaml`

### Interfaces

- Consumes: agent-core Tasks 8 and 9.
- Produces:
  - `extract.v2`: `mentions` gains `type_hint` (`purchase|withdrawal|transfer|payment|deposit|null`), `channel_hint` (`atm|pos|app|web|branch|null`) and `city`;
  - the `dev_writer` role in `load_models()`;
  - `matches_mentions(t, m) -> bool`;
  - `describe_txn(t, score=None)` (appends `" · match 0.93"`);
  - `build_understand_request(..., scores: dict[str, float] | None = None)`;
  - the `understand.v2` question set (v1 plus one instruction on match scores).

## Scope Limits

- Additive changes to `llm/extract.py`, `llm/models.yaml` and `decisions/understand.py`, plus `understand.v2.yaml`. The graph is unchanged until unit 37.
- This must land before the dev set (unit 33) is built.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_extract_schema_has_nullable_hints`, `test_dev_writer_role_is_configured`, `test_matches_mentions_is_the_prefilter_rule`, `test_scores_are_shown_only_when_given`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 4 (Agent-core changes I: extract hints, the dev-writer role and scored Jev requests), lines 1048–1436
