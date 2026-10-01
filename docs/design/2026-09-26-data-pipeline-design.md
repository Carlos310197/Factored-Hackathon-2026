# Data pipeline design: Snowflake + dbt curation for the LATAM Bank dataset

Date: 2026-09-26 · Status: draft for review · Owners: Andrés, Carlos
Related: `analysis/domain_evidence.py`, `analysis/etl_facts.py`, `docs/diagrams/pipeline.svg`, `docs/diagrams/ingestion-modes.svg`

## 1. Purpose

Build the repeatable data preparation the hackathon brief scores under "sound data and ML practice": contracts, quality checks, lineage, and an update/freshness policy. The pipeline curates the five source tables the chosen workflow needs (account/payment inquiries + transaction-dispute intake) and publishes a serving copy the live agent reads without depending on Snowflake being awake.

Decisions already taken (2026-09-26): workflow = account/payment inquiries + dispute intake; warehouse = Snowflake with dbt-snowflake (chosen over dbt-duckdb on AWS; the caveats raised were the 30-day trial, cold-start latency for live reads, and a third-party data-use question); the agent reads an S3 parquet export, never Snowflake directly.

## 2. Verified facts the design rests on

From profiling the organizer bucket (`s3://factored-datathon-2026-…/data/`) on 2026-09-26:

- Layout: one CSV per day per fact table (`<table>_YYYYMMDD.csv` under `year=/month=/day=`), 1,097 partitions from 2023-06-17 to 2026-06-17. Dimension tables are single CSVs. The partition always equals `process_date`. CSV headers carry a UTF-8 BOM.
- Types parse 100% from text. Referential integrity is 100% for `customer_id` and `product_id`. No duplicate keys and no exact or near duplicates in any of the seven tables checked. No schema change between the first and last file of any table.
- Real quirks: nulls only in nullable columns (duration 14%, claimed amount 68%, accent 30%); the event timestamp falls on the day after `process_date` for 25% of transactions and 33% of interactions, consistent with a timezone offset; sentiment values are Spanish while the dictionary lists English.
- `data_backup_20260831/` is a different synthetic generation (0 shared IDs for the same day, 4k of 150k customer IDs in common). It is never loaded.
- Cross-table links that do not work: `interactions.mentioned_products` (0.65% match products), `complaints.origin_interaction_id` (100% empty). Grounding goes through `customer_id`.

Consequence: the documented traps (2% duplicates, schema evolution, late arrivals) are not present in the current drop. The pipeline builds the defenses anyway and proves them with a labeled fixture drop, which the brief explicitly allows ("demonstrate update correctness with a clearly labeled test fixture").

## 3. Scope

In: `customers`, `products`, `transactions`, `complaints`, `call_center_interactions` from `data/`.
Out: `digital_events`, `campaign_sends`, `satisfaction_surveys`, `call_transcripts`, `branches`, `service_agents`, `marketing_campaigns`, `daily_exchange_rates`, and the whole `data_backup_20260831/` prefix. Transcripts are documented as unusable (templated text, no intents) using the profiling output; they are not loaded.

## 4. Architecture

```
organizer S3 (read-only keys)
  │ COPY INTO from external stage, one PATTERN per table, METADATA$FILENAME + load time captured
  ▼
RAW        one table per source, all text, append-only
  │ dbt-snowflake
  ▼
STAGING    typed to contract, normalized, deduped by key, tested; failures → QUARANTINE
  ▼
CURATED    contract-enforced marts + dq_results + run_manifest
  │ COPY INTO s3://<our-bucket>/serving/<run_id>/ as parquet, then latest.json pointer
  ▼
Agent API  in-process DuckDB over the parquet, read-only
```

Orchestration: one GitHub Actions workflow (`pipeline.yml`) with a daily cron and a run on every push to `main`: `load` → `dbt build` → `export`. Each step is a job that depends on the previous one succeeding.

Snowflake account: new trial on AWS `us-east-2` (same region as the organizer bucket), Standard edition, one `X-Small` warehouse `WH_PIPELINE` with `AUTO_SUSPEND = 60`. Databases: `LATAM_BANK` (schemas `RAW`, `STAGING`, `CURATED`, `META`) and `LATAM_FIXTURE` (same schemas, used only by the fixture test).

### 4.1 Ingestion modes (documented migration path, not built)

The organizer data is delivered as daily files, so the loader is batch. If the bank swapped files for continuous delivery or CDC, only the trigger, the RAW row shape, and the serving path change; models, tests, and contracts carry over. Continuous files: Snowpipe auto-ingest (requires bucket-owner event notifications, so for a bucket we do not own a Snowflake Task polling `COPY INTO` on a short schedule) with Streams + Tasks or Dynamic Tables driving transforms; GitHub becomes CI/CD only. CDC or real-time events: DMS/Debezium into Kinesis/Kafka, Snowpipe Streaming into RAW as a change log (operation, key, sequence number, timestamp), Dynamic Tables with a 1-minute target lag, and the agent reading a hot store fed by the same stream while Snowflake keeps the analytics copy. Genuine streaming in this project is limited to our own app events (sessions, dispute cases, actions, traces) into Snowflake via Snowpipe Streaming so the ops metrics refresh from the same warehouse as the baseline.

## 5. Layers and contracts

### 5.1 RAW (`LATAM_BANK.RAW`)

One table per source with every source column as `VARCHAR`, plus `_source_file`, `_file_row`, `_file_last_modified`, and `_loaded_at`, filled by the COPY option `INCLUDE_METADATA = (_source_file = METADATA$FILENAME, _file_row = METADATA$FILE_ROW_NUMBER, _file_last_modified = METADATA$FILE_LAST_MODIFIED, _loaded_at = METADATA$START_SCAN_TIME)`. Append-only. File format `CSV, PARSE_HEADER = TRUE, ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE, SKIP_BYTE_ORDER_MARK = TRUE`; loads use `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` (required by `INCLUDE_METADATA`) and the RAW tables have `ENABLE_SCHEMA_EVOLUTION = TRUE`, so a new source column is added to RAW instead of failing the load. `ON_ERROR = ABORT_STATEMENT` so a partition lands whole or not at all. Snowflake's 64-day load history makes re-running the same file a no-op; `FORCE = TRUE` is used only for files the loader has identified as changed.

Loader (`pipeline/load.py`, Python + snowflake-connector, no AWS credentials): `LIST @organizer_stage/<table>/` → compare `name` and `md5` (ETag) against `META.RUN_MANIFEST` → for each new file `COPY INTO` with `PATTERN` of that file; for each changed file `COPY INTO … FORCE = TRUE`; insert one manifest row per file (`run_id`, `table`, `file`, `etag`, `rows_loaded`, `loaded_at`, `mode` = new|restated|skipped). Dimension CSVs are treated the same way (one file each). Retries: one retry on connector/network errors; a second failure fails the job.

### 5.2 STAGING (`LATAM_BANK.STAGING`, dbt `stg_*` models, materialized as tables)

- Cast every column to the data-dictionary type; `'True'/'False'` → boolean; `process_date` parsed from `_source_file`; event timestamps kept exactly as delivered.
- Normalization: sentiment `Positivo/Neutral/Negativo/Muy Negativo` → `Positive/Neutral/Negative/Very Negative`; empty strings → null; whitespace trimmed on keys.
- Dedup: `QUALIFY ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _loaded_at DESC, _file_row DESC) = 1`.
- Only contract columns are selected; an unexpected column in RAW is surfaced by a warn-level singular test that compares `INFORMATION_SCHEMA.COLUMNS` to the contract.
- Quarantine: `STAGING.QUARANTINE` (one table: `table_name`, `pk_value`, `reason`, `_source_file`, `_loaded_at`, `raw_row VARIANT`) receives rows that fail a cast, a not-null contract column, or an enum. Foreign-key violations are an error-level `relationships` test instead (referential integrity is 100% in the real drop, and a broken FK is a systemic problem, not a row problem). Staging models exclude quarantined rows. A singular test errors when quarantined rows exceed 1% of the rows loaded in that run.
- Tests (dbt schema tests): `unique` + `not_null` on every primary key; `not_null` on dictionary NOT NULL columns; `accepted_values` on `transaction_status`, `transaction_type`, `channel`, `case_type`, `status`, `priority`, `reason_category`, `product_type`, `product_status`; `relationships` on `customer_id` → customers and `product_id` → products. Warn-level tests: `not_null` on `duration_seconds`, `customer_detected_accent`, `claimed_amount`; a singular test flagging event date more than one day away from `process_date`.
- Source freshness (`sources.yml`, `loaded_at_field: _loaded_at`): warn after 2 days, error after 7 days. This is the written freshness policy.

### 5.3 CURATED (`LATAM_BANK.CURATED`, dbt models with `contract: enforced`)

| Model | Grain | Columns (type) | Notes |
|---|---|---|---|
| `dim_customer` | customer | `customer_id` (varchar), `country`, `city`, `state`, `segment`, `detected_accent`, `customer_status`, `registration_date` (date), `accepts_marketing` (boolean), `last_updated` (timestamp) | Excludes name, document, date of birth, email, phones, address, postal code, credit score, income, occupation, marital status, education. |
| `dim_product` | product | `product_id`, `customer_id`, `product_type`, `product_last4` (varchar, last 4 of `product_number`), `currency`, `current_balance` (number 15,2), `credit_limit`, `interest_rate`, `opening_date`, `expiration_date`, `product_status`, `has_linked_app`, `days_past_due`, `last_transaction_date`, `last_updated` | Full product number never leaves RAW. |
| `fct_transaction` | transaction | `transaction_id`, `transaction_ts` (timestamp), `process_date` (date), `product_id`, `customer_id`, `transaction_type`, `transaction_category`, `amount`, `currency`, `amount_usd`, `channel`, `merchant_name`, `merchant_category`, `transaction_country`, `transaction_city`, `transaction_status`, `response_code`, `decline_reason_key` (varchar, null when approved), `is_fraud`, `fraud_score` | `decline_reason_key` joined from the seed. Full history (5M rows). |
| `fct_complaint` | complaint | `complaint_id`, `creation_ts`, `process_date`, `customer_id`, `case_type`, `category`, `subcategory`, `reception_channel`, `affected_product_id`, `claimed_amount`, `currency`, `priority`, `status`, `sla_breached`, `resolution_days`, `resolution_satisfaction`, `is_repeat_complainer`, `first_response_ts`, `resolution_ts`, `closing_ts` | Description and resolution text excluded (5 distinct values, no information). |
| `fct_interaction` | interaction | `interaction_id`, `interaction_ts`, `process_date`, `customer_id`, `channel`, `interaction_type`, `reason_category`, `duration_seconds`, `wait_time_seconds`, `was_resolved`, `requires_followup`, `was_escalated`, `detected_sentiment`, `sentiment_score`, `customer_detected_accent`, `has_transcript` | Analytics and baseline metrics only; not exported. |
| `seed_decline_reason` | response code | `response_code`, `reason_key`, `customer_text_es`, `customer_text_pt`, `next_step` | Team-authored, labeled synthetic policy data modeled on ISO 8583 codes: `00` approved, `05` do_not_honor, `14` invalid_card, `51` insufficient_funds, `54` expired_card. |
| `META.DQ_RESULTS` | test × run | `run_id`, `test_name`, `model`, `severity`, `status`, `failures`, `ran_at` | Written from dbt `run_results.json` by a post-`dbt build` step; stored failures kept via `store_failures`. |
| `META.RUN_MANIFEST` | file × run | see loader | Lineage from source file to load. |

### 5.4 Serving export (our bucket, `s3://<our-bucket>/serving/`)

- Storage integration `SI_SERVING` (Snowflake assumes an IAM role in our account scoped to `serving/*`). No static keys.
- Per run: `COPY INTO @serving_stage/<run_id>/<model>/ FROM CURATED.<model> FILE_FORMAT = (TYPE = PARQUET) HEADER = TRUE OVERWRITE = TRUE` for `dim_customer`, `dim_product`, `fct_transaction`, `fct_complaint`, `seed_decline_reason`. Multiple files per table are fine; the agent reads a glob.
- Pointer: `COPY INTO @serving_stage/latest.json FROM (SELECT OBJECT_CONSTRUCT('run_id', …, 'exported_at', …, 'max_process_date', …, 'tables', …)) FILE_FORMAT = (TYPE = JSON COMPRESSION = NONE) SINGLE = TRUE OVERWRITE = TRUE`. The agent reads `latest.json` then the run folder; the flip is the only visible state change. Old run folders are kept for the last 3 runs and deleted by the export step afterwards.
- Serving contract for the agent (interface other components depend on): column names and types exactly as in 5.3; `max_process_date` in the pointer is surfaced to customers as "data as of".

## 6. Failure handling

- COPY runs with abort-on-error; a failed partition leaves RAW untouched for that file. One retry on transient errors, then the workflow stops. `dbt build` and `export` do not run if `load` failed.
- `dbt build` fails on any error-severity test or contract violation; `export` runs only after a green build, so the serving set is never produced from a broken warehouse state.
- Row-level problems go to quarantine with a reason; the 1% singular test turns a systemic problem into a run failure.
- Schema evolution lands in RAW without failing; staging ignores unknown columns and a warn test makes them visible in `DQ_RESULTS`.
- Restated files are detected by ETag and force-reloaded; staging keeps the newest load per key.
- Export is atomic from the reader's point of view: unload into a run folder, then flip the pointer.

## 7. Access and secrets

- Organizer bucket: their static read-only keys, stored only inside the Snowflake stage definition (`CREATE STAGE organizer_stage URL = 's3://…/data/' CREDENTIALS = (…)`). They never appear in the repo, in GitHub secrets, or in CI logs.
- GitHub Actions → Snowflake: a Snowflake `SERVICE` user with `WORKLOAD_IDENTITY (TYPE = OIDC, ISSUER = 'https://token.actions.githubusercontent.com', SUBJECT = 'repo:<org>/<repo>:ref:refs/heads/main')`, role `PIPELINE_ROLE` with usage on the warehouse and ownership of `LATAM_BANK` and `LATAM_FIXTURE`. The workflow requests the GitHub OIDC token (`permissions: id-token: write`). Verified: the Snowflake side, and the Python connector (`authenticator = WORKLOAD_IDENTITY`, `workload_identity_provider = OIDC`, `token = <GitHub JWT>`), which covers the `load` and `export` steps. To verify in the first implementation task: whether dbt-snowflake can pass that same token. If it cannot, the `dbt build` step uses key-pair auth for the same service user, with the private key in a GitHub secret and rotated after the hackathon; that would be the one secret of ours.
- Snowflake → our bucket: storage integration `SI_SERVING` (IAM role trust to Snowflake's account, `s3:PutObject/DeleteObject/GetObject/ListBucket` on `serving/*`).
- Agent (Fargate) → our bucket: task role with `s3:GetObject/ListBucket` on `serving/*`.
- Net: one inherited static credential, held in Snowflake; none of ours, or exactly one (the dbt key pair) if the fallback is needed.

## 8. Fixture drop and tests

A Snowflake internal stage `LATAM_FIXTURE.RAW.FIXTURE_STAGE` (uploaded with `PUT` by the test, no AWS credentials needed) mirrors the organizer layout for `transactions` only; the generator and its README in `fixtures/` label it synthetic:
- a new partition `year=2026/month=06/day=18/transactions_20260618.csv` (200 rows);
- a restated `transactions_20260617.csv` with 3 rows whose `transaction_status` changed and 5 exact duplicate rows appended;
- a file with an extra column `merchant_country`;
- a file with one row whose `amount` is `N/A`.

`tests/test_fixture_drop.py` (pytest, one file): points the loader at `fixture_stage` and database `LATAM_FIXTURE`, runs `load` then `dbt build --target fixture`, then asserts via SQL: the new partition's rows are present; the 5 duplicates collapse to unique keys; the 3 changed rows show the restated status; `merchant_country` exists in RAW, is absent from staging, and the unexpected-column test is recorded as `warn`; the `N/A` row is in `QUARANTINE` with reason `cast_failed:amount`; the run manifest records modes `new` and `restated`; the pointer's `run_id` advanced. The test runs in CI on every pull request.

Other checks: dbt schema and singular tests (5.2), and a unit test for the loader's ETag comparison.

## 9. Definition of done

- `pipeline.yml` green on `main`: load, `dbt build`, export.
- `tests/test_fixture_drop.py` green in CI.
- `s3://<our-bucket>/serving/latest.json` present and pointing at a run folder containing the five exported tables.
- `META.DQ_RESULTS` and `META.RUN_MANIFEST` populated for the latest run.
- README section documenting: source contracts, freshness policy, lineage (manifest), quarantine policy, the fixture drop, and limitations (backup prefix ignored, transcripts unusable, timezone offset, counts below the documented totals, static organizer keys).

## 10. Open items

- Confirm in Slack `#technical-help` that dataset records may be loaded into Snowflake (third party) and sent to an external LLM. Synthetic data, but the brief says to follow the published data-use terms.
- Carlos to confirm the workflow and the Snowflake choice.
- Create the Snowflake trial (AWS us-east-2), our S3 bucket, and the public GitHub repo `factored-hackathon-2026-<team>`. The project folder is not a git repository yet.
- Who owns the Snowflake account and the AWS account for the bucket and the agent.

## 11. Out of scope for this spec

Agent, tool layer, evaluation harness, learned component, UI, deployment of the agent, and the app's own store. Each gets its own spec. This spec fixes the serving contract (5.3, 5.4) those components consume.
