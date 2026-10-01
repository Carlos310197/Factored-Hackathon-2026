# 46 · Eval Runtime Wiring and the Resumable Run CLI

**Subsystem:** Evaluation · **Depends on:** 45 · **Reference:** evaluation plan, Task 7

## Goal

Wire the real agent runtime per repetition (its own table prefix) and run goals × repetitions in parallel, resumably.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation
- `feature-specs/45-eval-conversation.md` → Harness · evaluation §4.5

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `eval/src/evalkit/agent_runtime.py`, `eval/src/evalkit/run.py`, `eval/tests/test_run.py`
- Modify: `.gitignore` (append `eval/runs/*/tmp/`)

### Interfaces

- Consumes:
  - `bankagent.runtime.build_runtime(settings) -> Runtime(settings, service, jwks)`; `bankagent.settings.Settings.from_env(env)`; `bankagent.store.tables.create_tables(client, prefix)`; `bankagent.auth.tokens.JwksCache(url, fetch=...)`; `bankagent.app.handle(payload, headers, rt)`; `bankagent.llm.config.load_models()`;
  - `apply_fault`, `FAULTS` (Task 6); `TokenIssuer`, `run_conversation` (Task 6); `PersonaClient` (Task 5); `GoalCard`, `read_goals`, `sha256_file` (Task 4); `load_config`, `require_live` (Task 4).
- Produces:
  - `evalkit.agent_runtime`: `table_prefix(run_id, rep) -> str`, `ensure_tables(cfg, prefix)`, `build_eval_runtime(cfg, prefix, fault, tokens) -> (rt, real_store)`;
  - `evalkit.run`: `pending(cards, reps, done) -> list[tuple[GoalCard, int]]`, `load_done(path) -> set[tuple[str, int]]`, `manifest(run_id, goals_path, reps, cfg) -> dict`, `main(argv) -> int` (CLI `python -m evalkit.run --goals --run-id --reps --workers --live`).

## Scope Limits

- `agent_runtime.py` and `run.py`. Live runs refuse to start without `--live`.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_table_prefix_is_unique_per_rep`, `test_pending_skips_finished_pairs`, `test_load_done_reads_jsonl`, `test_manifest_records_the_goal_hash`, `test_main_refuses_without_live`
- **Repetitions of one goal hit the same transaction:** the agent's dispute write is conditional on `transaction_id`, so rep 2 would see rep 1's dispute. Each repetition gets its own table prefix. Pinned in Task 7 (`test_table_prefix_is_unique_per_rep`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 7 (Runtime wiring and the resumable run CLI), lines 2550–2797
