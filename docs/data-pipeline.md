# Data pipeline (organizer drop → Snowflake → dbt → serving parquet)

## Data pipeline
Diagram: `docs/diagrams/pipeline.svg`. Spec: `docs/design/2026-09-26-data-pipeline-design.md`. Infrastructure: `docs/design/2026-10-01-infra-iac-design.md`.

Organizer bucket → Snowflake `RAW` (all text, plus load metadata) → dbt `STAGING` (typed, deduplicated, quarantined) → dbt `CURATED` (enforced contracts) → parquet in our S3 bucket plus a `latest.json` pointer that the agent reads.

### Sources and contracts
Five tables from the organizer bucket: `customers`, `products`, `transactions`, `complaints`, `call_center_interactions`.
The contract columns are declared in `dbt/models/staging/sources.yml`. The curated marts enforce column names and types
(`dbt/models/curated/schema.yml`). PII columns (names, document, birth date, contact details, address, credit score, income)
never leave RAW, and product numbers are cut to the last four digits (`product_last4`).

### Freshness policy
Daily partitions, loaded by the scheduled workflow at 06:00 UTC. `dbt source freshness` (warn after 2 days, error after 7) runs on
every load and its result is recorded in the run log, but it does **not** gate the build: the organizer drop is static (it ends
2026-06-17), so a gate would fail every daily run. Staleness is surfaced instead: the serving pointer carries `max_process_date`,
and the agent shows it to customers as "data as of".

### Lineage
`META.RUN_MANIFEST` records every loaded file: run, table, path, ETag, mode (new / restated) and row count. Every RAW row carries
its source file, row number, file timestamp and load time. `META.DQ_RESULTS` records every dbt test outcome per run.

### Quarantine policy
Rows that fail a cast, a not-null contract column or an enum go to `STAGING.QUARANTINE`, with a reason (`cast_failed:<col>`,
`null:<col>`, `enum:<col>`) and the raw row. If the latest load run quarantined more than 1% of the rows it loaded, the build fails.
The rate is per run, so one bad daily partition trips the gate. A broken foreign key also fails the daily build (dbt `relationships`
tests on the staging models, severity error): the run stops before the export, so the serving set the agent reads stays on the last
good run. The curated mart in Snowflake does get the orphan row (dbt does not skip `fct_transaction` for a two-model test); quarantining
orphans in `typed_transactions` would keep the mart clean too, and is listed under before production.
An FK break is not quarantined. Phase 3 of the fixture drop proves this.

### Update correctness (fixture drop)
`fixtures/` holds a labeled synthetic drop: a restated partition (with changed rows and one removed row), duplicate keys, a new column,
a bad type and a header-only file. A restated file replaces its whole partition: staging keeps only each file's latest load, then
deduplicates by key (newest load, then highest row number).
Phase 3 adds two proofs. Idempotent re-run: loading and building the same drop again skips every file, and RAW, the manifest,
staging, quarantine and `fct_transaction` keep identical counts and `hash_agg` content hashes. The new export has the same table
counts and `contract_hash`. Orphan FK: once the fixture customer and product are loaded, a day-22 row pointing at `PRD-ORPHAN0001`
fails exactly one test (`relationships` on `stg_transactions.product_id`, 1 failure, row kept by `store_failures`). The build fails, so
the export is skipped and serving keeps the last good run; `fct_transaction` still builds, so the orphan does reach the Snowflake mart. Offline guards: `test_rerun_over_same_drop_copies_nothing` (`tests/test_load.py`)
and `test_orphan_foreign_keys_fail_the_build_and_block_the_export` (`tests/test_pipeline_workflows.py`).
`tests/test_fixture_drop.py` runs it end to end against `LATAM_FIXTURE` on every push to `main` (`ci.yml`). Pull requests run the
offline tests only, so code from a pull request never gets Snowflake credentials.

### Serving contract for the agent
`s3://latam-bank-serving-762197749808-use1/serving/latest.json` → `{run_id, exported_at, max_process_date, tables, git_sha, contract_hash, dq_summary}`. The pointer describes its own build: the commit that produced it, a SHA-256 of the exported columns in order, and the run's dbt test outcomes by status. The agent refuses a pointer whose `contract_hash` differs from its own contract (`agent/src/bankagent/data/contract.py`), and `tests/test_contract_parity.py` proves that contract equals the dbt columns. Read the keys by name;
Snowflake writes them in alphabetical order. Tables are under `serving/<run_id>/<table>/*.parquet` with lowercase column names,
sorted by `customer_id` where the table has one: `dim_customer`, `dim_product`, `fct_transaction`, `fct_complaint`, `seed_decline_reason`.

### Access
No stored secrets. All infrastructure is Terraform (`infra/terraform`), applied by `.github/workflows/infra.yml`. GitHub Actions
assumes AWS roles through OIDC, and Snowflake trusts those roles through workload identity: `gha-deploy` → `TF_DEPLOY` (Terraform)
and `pipeline-runner` → `PIPELINE_SVC` (the Python steps and dbt, `authenticator: workload_identity`). Only pushes to `main`
can assume either role. The organizer keys are kept in SSM and in the Snowflake stage. Snowflake writes to our bucket through
the storage integration `SI_SERVING` (IAM role `snowflake-serving`).

### Run evidence (live, 2026-10-05)

Run `37378614273-1` (commit `57b728f`), read back from Snowflake and the serving bucket:

| Table | RAW rows (files) | STAGING rows | Quarantined | Exported |
|---|---|---|---|---|
| transactions | 4,425,008 (1,097 daily files) | 4,425,008 | 0 | 4,425,008 (`fct_transaction`) |
| customers | 150,000 (1 file) | 150,000 | 0 | 150,000 (`dim_customer`) |
| products | 400,000 (1 file) | 400,000 | 0 | 400,000 (`dim_product`) |
| complaints | 67,095 (1,097 daily files) | 67,095 | 0 | 67,095 (`fct_complaint`) |
| interactions | 686,296 (1,097 daily files) | 686,296 | 0 | not exported (not used by the agent) |

- **dbt build:** 80 nodes (16 models, 1 seed, 58 data tests, 5 unit tests): 77 pass, 3 warn, 0 error. `META.DQ_RESULTS` records the 58 data tests (53 error-severity, all pass; 5 warn-severity, 3 of them warned); unit tests check the SQL logic, not the data, so they are not DQ results.
- **The 3 warnings** are source nulls that are allowed by design: complaints `claimed_amount` (45,344 rows), interactions `duration_seconds` (96,234) and `customer_detected_accent` (204,750).
- **Quarantine is empty** on the organizer drop: no cast failures, contract nulls or bad enums. The fixture drop is what proves quarantine and the 1 % gate work.
- **Validated again** on run `37381703277-1` (commit `88a2edd`): same counts, same `contract_hash`, `dq_summary` `{pass: 55, warn: 3}`, and the first `dbt-lineage-37381703277-1` artifact (manifest + run results, 114 KB).
- **Lineage:** `META.RUN_MANIFEST` holds 3,293 files and 5,728,399 rows, all loaded as `new` by the initial run; later runs skipped every file (same ETag) and wrote no rows. From now on each run also keeps dbt's `manifest.json` and `run_results.json` as a workflow artifact (`dbt-lineage-<run_id>`, 90 days), and `latest.json` names the commit, the contract hash and the DQ summary.

### Limitations found in the data
- Counts are below the documented totals: 686k interactions vs 800k, and 67k complaints vs 80k.
- `data_backup_20260831/` is a different synthetic generation and is ignored.
- Transcripts are templated (about 42 distinct customer texts per category) with a single intent value, so they are not loaded.
- Product IDs mentioned in calls don't exist in the products table, and complaints never link to a call.
- For 25–33% of rows, the event timestamp falls on the day after the partition date (a timezone offset), so tools query by event time.
- Timestamps arrive as `YYYY-MM-DD HH24:MI:SS`, and integers as `"9.0"`; staging parses both (pinned by dbt unit tests).
- The current drop has no duplicates and no schema changes; the fixture drop proves that both are handled.

### Limitations of the pipeline itself
- The daily run re-exports every table under a new `run_id` even when nothing new was loaded (the pointer still moves).
- RAW only grows: a restated file is loaded again and staging keeps the newest load, but the old RAW rows are never purged;
  a restatement under a new file name leaves the old file's rows in place.
- Curated marts are rebuilt in full each run (no incremental models); fine at this size (4.4M transactions).

### Reproduce
1. One-time bootstrap (AWS SSO profile `hackathon-sso`, snow CLI connection `sbx`): `infra/terraform/bootstrap/apply.sh`, then merge to `main` and let `infra.yml` apply `infra/terraform/platform`.
2. `uv sync && uv run python -m pipeline.setup 02_raw_tables.sql && SETUP_DATABASE=LATAM_FIXTURE uv run python -m pipeline.setup 02_raw_tables.sql`
3. `set -a; source .env; set +a; uv run python -m pipeline.load --run-id initial && bin/dbt build && uv run python -m pipeline.export --run-id initial`
4. `uv run pytest -m "not snowflake"`. For the live tests (`-m snowflake`), the Python steps log in through `SNOWFLAKE_CONNECTION_NAME` from `.env`.
   The fixture proof also shells out to dbt, which needs `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` and `SNOWFLAKE_PASSWORD` exported.
   `bin/dbt` exports them from the snow CLI config, using the macOS path `~/Library/Application Support/snowflake/config.toml` (local only).

In production, `.github/workflows/pipeline.yml` runs the `LATAM_BANK` part of step 2 and all of step 3, daily and on every push to `main`.
`ci.yml` prepares `LATAM_FIXTURE` and runs the fixture proof on every push to `main`.
