# 16 · Serving Reader and Read Tools

**Subsystem:** Agent core · **Depends on:** 12 · **Reference:** agent-core plan, Task 5

## Goal

Read the serving set through DuckDB (pointer → run folder) and expose customer-scoped read tools that return receipts.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- `context/architecture-context.md` → Serving contract · pipeline §5.3–5.4

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Tools (`tools/`) · agent-core §7.1

Every tool returns `{data, receipt_id, source, as_of}`.

| Tool | Returns | Guards |
|---|---|---|
| `get_accounts(ctx)` | `dim_product` rows: type, last4, currency, balance, credit limit, status, days past due, last transaction date | scope `inquiry:read` |
| `list_transactions(ctx, filters)` | `fct_transaction` in the 60-day window | `inquiry:read` |
| `get_transaction(ctx, id)` | one transaction | not owned ≡ not found |
| `explain_decline(ctx, id)` | seed reason key, ES/PT text, next step | `Declined` only |
| `list_disputes(ctx)` | our disputes, plus earlier `fct_complaint` rows (labeled separately) | `inquiry:read` |
| `create_dispute(ctx, draft)` | receipt | scope `dispute:create`; policy re-evaluated |
| `create_handoff(ctx, packet)` | receipt | always allowed |
| `data_as_of()` | `max_process_date` | none |

- **Reads** use DuckDB against the S3 run folder named by `latest.json`.
- **AgentCore constraint:** a fresh microVM per session makes copying the serving set per session impractical, so reads rely on row-group pruning by `customer_id`. **Pipeline change request:** sort the serving export (`fct_transaction`, `fct_complaint`, `dim_product`) by `customer_id`. If the measured per-turn latency is too high, the fallback is an agent-facing export of the last 90 days only.

## Implementation

### Files

- Create: `agent/src/bankagent/data/__init__.py`, `agent/src/bankagent/data/contract.py`, `agent/src/bankagent/data/serving.py`, `agent/src/bankagent/tools/__init__.py`, `agent/src/bankagent/tools/read.py`, `agent/tests/fixtures/__init__.py`, `agent/tests/fixtures/serving_fixture.py`, `agent/tests/test_serving.py`, `agent/tests/test_read_tools.py`
- Modify: `agent/tests/conftest.py` (append the `serving_root` fixture)

### Interfaces

- Consumes: `SessionContext`, `SCOPE_READ`, `new_id` (Task 1).
- Produces:
  - `CONTRACT: dict[str, list[str]]` (column order per table);
  - `ServingData(base_uri, region="us-east-2")` with `.pointer() -> Pointer(run_id, max_process_date: date, exported_at)` and `.query(run_id, table, where, params, order_by="") -> list[dict]` (JSON-safe values: Decimal → float, date/datetime → ISO string);
  - `ServingError`;
  - `ToolResult(source, data, as_of, receipt_id)` with `.receipt() -> {"receipt_id", "source", "as_of", "data"}`;
  - `NotFound` (message `"not_found"`), `NotDeclined`;
  - `ReadTools(serving)` with `get_accounts(ctx, run_id, as_of)`, `list_transactions(ctx, run_id, as_of, window_days=60)` (newest first), `get_transaction(ctx, run_id, as_of, transaction_id)`, `explain_decline(ctx, run_id, as_of, transaction_id)`, `list_complaints(ctx, run_id, as_of)`, and the attribute `.serving`.
- Test fixture constants: `AS_OF="2026-06-17"`, `RUN_ID="fixture-run-1"`, `C1/C2`, `P1/P2`, `t(n)`. For C1, `list_transactions` returns newest first: `t(103), t(102), t(105), t(108), t(101), t(100), t(107), t(104)`.

## Scope Limits

- The read tools only. `create_dispute` and `create_handoff` are unit 18.
- Tests run on a small labeled synthetic parquet fixture that follows the serving contract exactly.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_pointer_reads_run_and_as_of`, `test_missing_pointer_is_serving_error`, `test_fixture_matches_serving_contract`, `test_query_returns_json_safe_values`, `test_rejects_unknown_table_and_unsafe_run_id`, `test_missing_run_folder_is_serving_error`, `test_accounts_only_own`, `test_list_transactions_window_and_order`, `test_foreign_and_missing_transactions_are_indistinguishable`, `test_explain_decline_uses_seed`, `test_explain_decline_on_approved_raises`, `test_complaints_scoped`, `test_scope_required`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 5 (Serving contract, synthetic fixture, DuckDB reader and read tools), lines 1255–1732
