# 30 · Records, the Blind Test Sheet and the Resolver CLI

**Subsystem:** Transaction resolver · **Depends on:** 29 · **Reference:** resolver plan, Task 5

## Goal

Build the shared record helpers, the blind test sheet for Andrés (and its ingestion) and the one resolver CLI.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver
- Resolver plan #5 (one CLI), #7 (paths) and #11 (test hash) in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From resolver §5.4 (items 3–5 are unit 39):*

1. `make_test_sheet.py` writes `resolver/data/test_sheet_v1.csv` from test-split cases. Each row contains:
   - the candidates;
   - a marked target, or, for 15 rows, the note "describe a transaction that is NOT in this list";
   - a language;
   - a style hint (e.g. "vague about the amount", "only the date and the channel").

   75 rows are hard, 60 easy and 15 `not_in_list`.
2. Andrés writes each message as a customer would, without seeing the model, the simulator rates or the dev set.

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/records.py`, `agent/src/bankagent/resolver/testset.py`, `agent/scripts/resolver.py`, `agent/tests/resolver_llm.py`, `agent/tests/test_resolver_testset.py`, `agent/tests/test_resolver_cli.py`, `agent/resolver/data/TEST_SHEET_README.md`
- Modify: `agent/.gitignore`

### Interfaces

- Consumes: `simulate`, `load_sim_config` (Task 3); `History`, `TransactionSource`, `sample_histories` (Task 2); `describe_txn` (agent-core); `extract` (Task 4).
- Produces:
  - `public(t)`, `country_of(candidates)`, `save_jsonl(rows, path)`, `load_jsonl(path)`;
  - `QUOTAS`, `style_hint(style)`, `make_test_sheet(histories, cfg, seed, quotas=QUOTAS) -> list[dict]`, `write_sheet(cases, stem)` (writes `stem.json` and `stem.csv` with `SHEET_COLUMNS`);
  - `read_sheet(path)` (handles a BOM and `,` `;` or tab), `read_messages`, `sha256_file`;
  - `ingest_test_set(stem, completed_csv, client, models) -> (rows, sha256)`;
  - `make_ceiling_sheet(rows, n, seed, path) -> ids`, `read_ceiling(path, rows) -> {case_id: txn_id | None}`;
  - the CLI `scripts/resolver.py` with `main(argv) -> int`, the global options `--data-dir --reports-dir --runs-dir --artifact --thresholds-out --region --live`, and every subcommand. Each subcommand imports its modules lazily, so later tasks add the modules it calls.
  - Test double `tests/resolver_llm.py::ScriptedLLM(mentions=None, fail_every=0)`.

## Scope Limits

- Tooling plus `TEST_SHEET_README.md`. Commands that call Bedrock or Jev refuse to run without `--live`.
- Committed dataset files keep transaction fields only.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_sheet_meets_quotas_and_balances_languages`, `test_sheet_files_and_ingestion`, `test_ingestion_refuses_missing_messages_and_survives_extract_errors`, `test_ceiling_round_trip`, `test_style_hint_text`, `test_records_helpers`, `test_ingestion_reads_a_sheet_saved_by_spanish_excel`, `test_live_commands_refuse_without_live`, `test_test_sheet_command`
- **Andrés's completed sheet saved by Spanish-locale Excel or Google Sheets** (`;` delimiter, byte-order mark) must still ingest. Pinned in Task 5 (`test_ingestion_reads_a_sheet_saved_by_spanish_excel`).
- The real sheet is generated from the full-history serving set and sent to Andrés with its README (recorded in Session Notes).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 5 (Records, the blind test sheet and the resolver CLI), lines 1440–2135
