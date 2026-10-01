# 27 · Resolver History Sampler

**Subsystem:** Transaction resolver · **Depends on:** 26 · **Reference:** resolver plan, Task 2

## Goal

Sample customer histories (60-day candidate windows) per split from a pinned serving run, deterministically.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From resolver §3.2:*

**Training data source:** `fct_transaction` from one pinned serving `run_id` (the curated export), so every model version traces to the pipeline's `RUN_MANIFEST`.

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/histories.py`, `agent/tests/fixtures/resolver_serving.py`, `agent/tests/test_resolver_histories.py`
- Modify: `agent/tests/conftest.py` (append the `history_serving` fixture)

### Interfaces

- Consumes: `ServingData`, `_jsonable` (agent-core `data/serving.py`); `TXN_FIELDS` (`tools/read.py`); `DDL` (`tests/fixtures/serving_fixture.py`); `customer_split`, `ANCHORS`, `WINDOW_DAYS` (Task 1).
- Produces:
  - `History(split, customer_id, anchor: str, candidates: list[dict])`;
  - `TransactionSource(serving_dir)` with `.run_id`, `.customers(split)` and `.windows(pairs)`;
  - `sample_histories(source, split, n, seed, min_candidates=2) -> list[History]`. Candidates match `ReadTools.list_transactions` exactly (`TXN_FIELDS`, newest first, 60-day inclusive window).
  - Test fixture `history_serving`: a synthetic serving root, `RUN_ID = "resolver-fixture-1"`, 200 customers `CLI-HIST%08d` from 2023-07 to 2026-06.

## Scope Limits

- `resolver/histories.py` and its fixture. No simulation (unit 28).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_histories_respect_split_window_and_order`, `test_histories_are_deterministic_and_splits_disjoint`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 2 (History sampler), lines 520–737
