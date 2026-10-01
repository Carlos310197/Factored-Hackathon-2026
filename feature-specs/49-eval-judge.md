# 49 · Judge for Soft Criteria and Its Human Validation

**Subsystem:** Evaluation · **Depends on:** 47 · **Reference:** evaluation plan, Task 10

## Goal

Score handoff-packet usefulness and reply language and faithfulness with a Claude judge, and validate it against 40 human labels (Cohen's κ).

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From evaluation §5.3:*

**LLM judge (soft criteria only).** Claude Sonnet with a written rubric in `eval/judge_rubric.md`:
- handoff packet usefulness: 0–2 for each of request, verified facts, actions taken, open questions;
- reply language correct and reply faithful to the receipts: pass/fail.

Carlos labels 40 judged items by hand (stratified across both criteria and both languages); agreement is reported as Cohen's κ. The judge never decides `unsafe` or the outcome class.

## Implementation

### Files

- Create: `eval/judge_rubric.md`, `eval/src/evalkit/judge.py`, `eval/tests/test_judge.py`

### Interfaces

- Consumes: `bankagent.llm.client.call_json(client, cfg: RoleConfig, system, user, schema) -> LLMCall(data, model, prompt_version, usage, latency_ms)`, `bankagent.llm.client.make_bedrock_client(region)`, `bankagent.llm.config.RoleConfig(model, max_tokens, prompt_version, timeout_s, effort=None)`; conversation records (Task 6).
- Produces:
  - `REPLY_FIELDS`, `PACKET_FIELDS`, `judge_role(cfg) -> RoleConfig`, `items_for(rec) -> list[dict]`, `judge_item(client, role, item) -> dict`, `run_judge(records, client, role) -> list[dict]`;
  - `human_sheet(judgments, n=40, seed=0) -> list[dict]`, `cohen_kappa(a, b) -> float | None`, `validate(judgments, labeled_rows) -> dict[field, {"kappa", "n"}]`;
  - CLI `python -m evalkit.judge --run <dir> --live` writing `judgments.jsonl` and `human_sheet.csv`.

## Scope Limits

- `judge_rubric.md` and `judge.py`. The judge never decides `unsafe` or the outcome class.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_kappa`, `test_items_for_a_conversation`, `test_judge_item_parses_structured_output`, `test_human_sheet_is_stratified_and_validation_computes_kappa`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 10 (Judge for soft criteria and its human validation), lines 3504–3758
