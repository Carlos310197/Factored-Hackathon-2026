# 23 · Local Serving Set and Demo Identities

**Subsystem:** Agent core · **Depends on:** 16, 14 · **Reference:** agent-core plan, Task 12

## Goal

Build a contract-true serving set from the local drop (no PII) and pick about 20 labeled demo identities mapped to real customers.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `agent/src/bankagent/data/local_build.py`, `agent/src/bankagent/data/demo_users.py`, `agent/scripts/build_local_serving.py`, `agent/scripts/pick_demo_users.py`, `agent/.gitignore`, `agent/tests/test_local_build.py`

### Interfaces

- Consumes: `CONTRACT` (Task 5), `hash_password` (Task 3), `ServingData`/`ReadTools` (Task 5, test only).
- Produces:
  - `build_local_serving(data_dir: Path, out_dir: Path, since="2026-02-01", run_id=None) -> dict`: writes `<out_dir>/latest.json` + `<out_dir>/<run_id>/<table>/data_0.parquet` in contract order, sorted by `customer_id`; labeled dev-only;
  - `select_demo_customers(serving_dir: Path, per_country: dict[str, int]) -> list[dict]`;
  - `build_users(customers, pt_every=4) -> list[dict]`;
  - `write_users(path, users)`.
- Outputs `agent/.serving/` and `agent/config/demo_users.yaml` are gitignored. They're generated locally, never committed.

## Scope Limits

- Dev tooling only. `config/demo_users.yaml` is generated and gitignored, because it names real dataset customer ids.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_local_build_follows_contract_and_drops_pii`, `test_local_build_values`, `test_select_demo_customers_and_users`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 12 (Local serving set and demo identities (dev tooling)), lines 5240–5596
