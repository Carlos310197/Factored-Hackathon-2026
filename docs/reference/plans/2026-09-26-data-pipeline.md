# Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load five LATAM Bank source tables from the organizer bucket into Snowflake, curate them with dbt under enforced contracts, and publish a parquet serving set plus `latest.json` pointer to our S3 bucket, with a fixture-driven proof that duplicates, restated files, new columns and bad types are handled.

**Architecture:** A Python loader issues `COPY INTO` per new or changed file (detected by ETag against a manifest) into all-text RAW tables. dbt-snowflake types, deduplicates and tests the data into STAGING (with a QUARANTINE table) and contract-enforced CURATED marts. A Python export step unloads the curated tables as parquet to a run folder in our bucket and flips `latest.json`. GitHub Actions runs load → dbt build → export daily and on push.

**Tech Stack:** Python 3.12 managed by `uv`; `snowflake-connector-python`; `dbt-core` + `dbt-snowflake` (dbt ≥ 1.8 for unit tests); `pytest`; GitHub Actions; Snowflake trial on AWS us-east-2.

**Spec:** `docs/superpowers/specs/2026-09-26-data-pipeline-design.md`

## Global Constraints

- Source: only `s3://<organizer-bucket>/data/` for `customers`, `products`, `transactions`, `complaints`, `call_center_interactions`. Never `data_backup_20260831/`.
- Organizer keys exist only in `.env` (gitignored) and inside the Snowflake stage definition. Never in code, GitHub secrets, or logs.
- RAW tables: every source column `VARCHAR`, plus `_source_file`, `_file_row`, `_file_last_modified`, `_loaded_at`; `ENABLE_SCHEMA_EVOLUTION = TRUE`.
- COPY options: `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE`, `INCLUDE_METADATA = (...)`, `ON_ERROR = ABORT_STATEMENT`; file format `CSV, PARSE_HEADER = TRUE, ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE, SKIP_BYTE_ORDER_MARK = TRUE`.
- Dedup rule everywhere: newest `_loaded_at`, then highest `_file_row`, per primary key.
- Curated marts have `contract: enforced: true`; column names and types exactly as in spec §5.3. PII columns listed in §5.3 never leave RAW.
- Export column names are lowercase (quoted aliases); the agent reads `latest.json` then the run folder.
- Snowflake objects: warehouse `WH_PIPELINE` (X-Small, auto-suspend 60), databases `LATAM_BANK` and `LATAM_FIXTURE`, schemas `RAW`, `STAGING`, `CURATED`, `META`, role `PIPELINE_ROLE`.
- Test severities: error on keys, FKs, enums, contracts, quarantine rate > 1%; warn on known nulls, freshness, unexpected columns, event/process date drift.
- Every task ends with a commit on `main` (single-developer repo; branch if Carlos is pushing to the same repo).

## Review Focus

1. A header-only (zero-row) partition file: COPY loads 0 rows and the manifest records `rows_loaded = 0` with mode `new`; the run continues. Pinned in Task 4 (`test_plan_loads_zero_row_file_is_new` and the fixture's `transactions_20260621.csv`).
2. Duplicate keys inside one file (not across loads): the row with the highest `_file_row` wins. Pinned in Task 6's dbt unit test row `T3`.
3. A timestamp in a different format (e.g. ISO `T` separator) would quarantine an entire partition and trip the 1% test rather than silently nulling. Pinned in Task 6's dbt unit test row `T4` (reason `cast_failed:transaction_date`).
4. Column-name case: Snowflake stores unquoted identifiers uppercase; parquet must carry lowercase names or DuckDB queries in the agent break. Pinned in Task 8 (`test_export_select_quotes_lowercase`) and the fixture test's parquet column assertion.
5. Pointer flip with a failed unload: if any table's unload fails, `latest.json` must not move. Pinned in Task 8 (`test_run_export_does_not_write_pointer_on_failure`).

---

## Prerequisites (manual, one time, before Task 2)

1. Create a Snowflake trial: cloud AWS, region `us-east-2 (Ohio)`, Standard edition. Note the account identifier (`<org>-<account>`).
2. Generate a key pair for your own admin user and for the pipeline service user (used until GitHub OIDC is confirmed for dbt):
   ```bash
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/admin_rsa_key.p8 -nocrypt
   openssl rsa -in ~/.snowflake/admin_rsa_key.p8 -pubout -out ~/.snowflake/admin_rsa_key.pub
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/pipeline_rsa_key.p8 -nocrypt
   openssl rsa -in ~/.snowflake/pipeline_rsa_key.p8 -pubout -out ~/.snowflake/pipeline_rsa_key.pub
   ```
   In Snowsight, as ACCOUNTADMIN: `ALTER USER <your_user> SET RSA_PUBLIC_KEY = '<contents of admin_rsa_key.pub without header/footer lines>';`
3. Create our S3 bucket `latam-bank-serving-<suffix>` in `us-east-2` (private, versioning off).
4. The team repo already exists: `Carlos310197/Factored-Hackathon-2026` (private for now; rename to `factored-hackathon-2026-<team>` and make public before submission). `<org>/<repo>` is `Carlos310197/Factored-Hackathon-2026`. Use the `andrezc98` GitHub account (`gh auth switch --user andrezc98`); it is the one with access.
5. Add to `.env` (gitignored) alongside the organizer keys:
   ```
   SNOWFLAKE_ACCOUNT=<org>-<account>
   SNOWFLAKE_USER=<your_user>
   SNOWFLAKE_PRIVATE_KEY_PATH=/Users/<you>/.snowflake/admin_rsa_key.p8
   SNOWFLAKE_ROLE=ACCOUNTADMIN
   SNOWFLAKE_WAREHOUSE=WH_PIPELINE
   SNOWFLAKE_DATABASE=LATAM_BANK
   SERVING_BUCKET=latam-bank-serving-<suffix>
   GITHUB_REPO=Carlos310197/Factored-Hackathon-2026
   ```

---

### Task 1: Repository scaffold and Snowflake connection helper

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `pipeline/__init__.py`, `pipeline/connect.py`, `tests/__init__.py`, `tests/test_connect.py`

**Interfaces:**
- Produces: `pipeline.connect.build_connect_kwargs(env: Mapping[str, str]) -> dict` and `pipeline.connect.get_connection(database: str | None = None)` returning a `snowflake.connector` connection. Env keys: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, and one of `SNOWFLAKE_OIDC_TOKEN` (GitHub) or `SNOWFLAKE_PRIVATE_KEY_PATH`.

- [ ] **Step 1: Initialize the repo and project files**

The folder already tracks `origin/main` of the team repo and `.gitignore` already excludes `.env`, `data/`, `*.pdf`, build output and `.key.p8` (done on 2026-09-26). Do not re-run `git init`.

`pyproject.toml`:
```toml
[project]
name = "latam-bank-pipeline"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "snowflake-connector-python>=3.15",
  "dbt-core>=1.9",
  "dbt-snowflake>=1.9",
  "python-dotenv>=1.0",
]

[dependency-groups]
dev = ["pytest>=8", "pyarrow>=17"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["snowflake: needs a live Snowflake connection (env vars)"]
```

Run: `uv sync` → creates `.venv` and `uv.lock`.

- [ ] **Step 2: Write the failing test**

`tests/test_connect.py`:
```python
from pipeline.connect import build_connect_kwargs

BASE = {
    "SNOWFLAKE_ACCOUNT": "acme-xy12345",
    "SNOWFLAKE_USER": "PIPELINE_SVC",
    "SNOWFLAKE_ROLE": "PIPELINE_ROLE",
    "SNOWFLAKE_WAREHOUSE": "WH_PIPELINE",
    "SNOWFLAKE_DATABASE": "LATAM_BANK",
}

def test_oidc_token_wins():
    kw = build_connect_kwargs({**BASE, "SNOWFLAKE_OIDC_TOKEN": "jwt", "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"})
    assert kw["authenticator"] == "WORKLOAD_IDENTITY"
    assert kw["workload_identity_provider"] == "OIDC"
    assert kw["token"] == "jwt"
    assert "private_key_file" not in kw

def test_key_pair_when_no_token():
    kw = build_connect_kwargs({**BASE, "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"})
    assert kw["private_key_file"] == "/k.p8"
    assert "authenticator" not in kw

def test_common_fields_and_database_override():
    kw = build_connect_kwargs({**BASE, "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"}, database="LATAM_FIXTURE")
    assert kw["account"] == "acme-xy12345" and kw["user"] == "PIPELINE_SVC"
    assert kw["role"] == "PIPELINE_ROLE" and kw["warehouse"] == "WH_PIPELINE"
    assert kw["database"] == "LATAM_FIXTURE"

def test_missing_auth_raises():
    import pytest
    with pytest.raises(ValueError, match="SNOWFLAKE_OIDC_TOKEN or SNOWFLAKE_PRIVATE_KEY_PATH"):
        build_connect_kwargs(BASE)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_connect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.connect'`

- [ ] **Step 4: Write minimal implementation**

`pipeline/__init__.py`: empty file.

`pipeline/connect.py`:
```python
"""Snowflake connection from environment variables. Auth: GitHub OIDC token (WIF) or key pair."""
import os
from collections.abc import Mapping

from dotenv import load_dotenv


def build_connect_kwargs(env: Mapping[str, str], database: str | None = None) -> dict:
    kw = {
        "account": env["SNOWFLAKE_ACCOUNT"],
        "user": env["SNOWFLAKE_USER"],
        "role": env["SNOWFLAKE_ROLE"],
        "warehouse": env["SNOWFLAKE_WAREHOUSE"],
        "database": database or env["SNOWFLAKE_DATABASE"],
        "client_session_keep_alive": False,
    }
    if env.get("SNOWFLAKE_OIDC_TOKEN"):
        kw.update(authenticator="WORKLOAD_IDENTITY", workload_identity_provider="OIDC", token=env["SNOWFLAKE_OIDC_TOKEN"])
    elif env.get("SNOWFLAKE_PRIVATE_KEY_PATH"):
        kw["private_key_file"] = env["SNOWFLAKE_PRIVATE_KEY_PATH"]
    else:
        raise ValueError("set SNOWFLAKE_OIDC_TOKEN or SNOWFLAKE_PRIVATE_KEY_PATH")
    return kw


def get_connection(database: str | None = None):
    import snowflake.connector

    load_dotenv()
    return snowflake.connector.connect(**build_connect_kwargs(os.environ, database))


if __name__ == "__main__":  # smoke check: uv run python -m pipeline.connect
    with get_connection() as conn:
        print(conn.cursor().execute("select current_user(), current_role(), current_warehouse(), current_database()").fetchone())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_connect.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml uv.lock pipeline tests
git commit -m "chore: scaffold pipeline project with Snowflake connection helper"
```

---

### Task 2: Snowflake account objects, stages, and RAW tables

**Files:**
- Create: `infra/snowflake/00_account.sql`, `infra/snowflake/01_integrations.sql`, `infra/snowflake/02_raw_tables.sql`, `infra/aws/snowflake-serving-role.md`, `pipeline/setup.py`, `tests/test_setup.py`

**Interfaces:**
- Consumes: `pipeline.connect.get_connection`.
- Produces: `pipeline.setup.render(sql: str, params: Mapping[str, str]) -> str` (replaces `${NAME}` tokens; raises `KeyError` on a missing one) and `pipeline.setup.run_script(conn, path, params)` (splits on `;` at line ends and executes each statement). Snowflake objects: `WH_PIPELINE`, `PIPELINE_ROLE`, `PIPELINE_SVC` (WIF user), databases `LATAM_BANK`/`LATAM_FIXTURE` with schemas `RAW`, `STAGING`, `CURATED`, `META`; `RAW.ORGANIZER_STAGE`, `RAW.SERVING_STAGE`, `RAW.FIXTURE_STAGE` (internal, in `LATAM_FIXTURE`), file format `RAW.CSV_HEADER`; RAW tables `CUSTOMERS`, `PRODUCTS`, `TRANSACTIONS`, `COMPLAINTS`, `INTERACTIONS`; `META.RUN_MANIFEST`, `META.DQ_RESULTS`.

- [ ] **Step 1: Write the failing test for the SQL renderer**

`tests/test_setup.py`:
```python
import pytest
from pipeline.setup import render, split_statements

def test_render_substitutes_tokens():
    assert render("URL='s3://${BUCKET}/data/'", {"BUCKET": "b1"}) == "URL='s3://b1/data/'"

def test_render_missing_token_raises():
    with pytest.raises(KeyError):
        render("${MISSING}", {})

def test_split_statements_ignores_comments_and_blank():
    sql = "-- c\ncreate warehouse w;\n\nuse role x;\n"
    assert split_statements(sql) == ["create warehouse w", "use role x"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.setup'`

- [ ] **Step 3: Write the setup runner**

`pipeline/setup.py`:
```python
"""Run infra/snowflake/*.sql with ${TOKEN} substitution from .env. Usage: uv run python -m pipeline.setup 00_account.sql"""
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

from pipeline.connect import get_connection

TOKEN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def render(sql: str, params: Mapping[str, str]) -> str:
    return TOKEN.sub(lambda m: params[m.group(1)], sql)


def split_statements(sql: str) -> list[str]:
    lines = [l for l in sql.splitlines() if not l.strip().startswith("--")]
    out, buf = [], []
    for line in lines:
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    return out


def run_script(conn, path: Path, params: Mapping[str, str]) -> int:
    cur = conn.cursor()
    stmts = split_statements(render(path.read_text(), params))
    for s in stmts:
        cur.execute(s)
    return len(stmts)


if __name__ == "__main__":
    load_dotenv()
    params = {
        "ORGANIZER_BUCKET": os.environ["DATA_BUCKET"],
        "ORGANIZER_KEY_ID": os.environ["AWS_ACCESS_KEY_ID"],
        "ORGANIZER_SECRET": os.environ["AWS_SECRET_ACCESS_KEY"],
        "SERVING_BUCKET": os.environ["SERVING_BUCKET"],
        "SERVING_ROLE_ARN": os.environ.get("SERVING_ROLE_ARN", "arn:aws:iam::000000000000:role/placeholder-until-task-2-step-6"),
        "GITHUB_REPO": os.environ["GITHUB_REPO"],
        "PIPELINE_RSA_PUBLIC_KEY": os.environ.get("PIPELINE_RSA_PUBLIC_KEY", ""),
        "DATABASE": os.environ.get("SETUP_DATABASE", "LATAM_BANK"),
    }
    with get_connection() as conn:
        for name in sys.argv[1:]:
            n = run_script(conn, Path("infra/snowflake") / name, params)
            print(f"{name}: {n} statements")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_setup.py -v`
Expected: 3 passed

- [ ] **Step 5: Write the account script**

`infra/snowflake/00_account.sql`:
```sql
-- Run once as ACCOUNTADMIN: uv run python -m pipeline.setup 00_account.sql
use role ACCOUNTADMIN;
create warehouse if not exists WH_PIPELINE warehouse_size = 'XSMALL' auto_suspend = 60 auto_resume = true initially_suspended = true;
create role if not exists PIPELINE_ROLE;
grant usage, operate on warehouse WH_PIPELINE to role PIPELINE_ROLE;
create database if not exists LATAM_BANK;
create database if not exists LATAM_FIXTURE;
create schema if not exists LATAM_BANK.RAW;
create schema if not exists LATAM_BANK.STAGING;
create schema if not exists LATAM_BANK.CURATED;
create schema if not exists LATAM_BANK.META;
create schema if not exists LATAM_FIXTURE.RAW;
create schema if not exists LATAM_FIXTURE.STAGING;
create schema if not exists LATAM_FIXTURE.CURATED;
create schema if not exists LATAM_FIXTURE.META;
grant ownership on database LATAM_BANK to role PIPELINE_ROLE copy current grants;
grant ownership on all schemas in database LATAM_BANK to role PIPELINE_ROLE copy current grants;
grant ownership on database LATAM_FIXTURE to role PIPELINE_ROLE copy current grants;
grant ownership on all schemas in database LATAM_FIXTURE to role PIPELINE_ROLE copy current grants;
-- Service user for GitHub Actions (OIDC workload identity) with key-pair fallback for dbt.
create user if not exists PIPELINE_SVC
  type = SERVICE
  default_role = PIPELINE_ROLE
  default_warehouse = WH_PIPELINE
  workload_identity = (type = OIDC, issuer = 'https://token.actions.githubusercontent.com', subject = 'repo:${GITHUB_REPO}:ref:refs/heads/main');
alter user PIPELINE_SVC set rsa_public_key = '${PIPELINE_RSA_PUBLIC_KEY}';
grant role PIPELINE_ROLE to user PIPELINE_SVC;
grant role PIPELINE_ROLE to role ACCOUNTADMIN;
```

`infra/snowflake/01_integrations.sql`:
```sql
-- Run as ACCOUNTADMIN after 00_account.sql: uv run python -m pipeline.setup 01_integrations.sql
use role ACCOUNTADMIN;
create or replace file format LATAM_BANK.RAW.CSV_HEADER
  type = CSV parse_header = true error_on_column_count_mismatch = false skip_byte_order_mark = true
  field_optionally_enclosed_by = '"' null_if = ('') empty_field_as_null = true;
-- Organizer bucket: their static read-only keys live only here.
create or replace stage LATAM_BANK.RAW.ORGANIZER_STAGE
  url = 's3://${ORGANIZER_BUCKET}/data/'
  credentials = (aws_key_id = '${ORGANIZER_KEY_ID}' aws_secret_key = '${ORGANIZER_SECRET}')
  file_format = LATAM_BANK.RAW.CSV_HEADER;
-- Our bucket: storage integration (IAM role), no keys.
create storage integration if not exists SI_SERVING
  type = external_stage storage_provider = 'S3' enabled = true
  storage_aws_role_arn = '${SERVING_ROLE_ARN}'
  storage_allowed_locations = ('s3://${SERVING_BUCKET}/serving/');
create or replace stage LATAM_BANK.RAW.SERVING_STAGE
  url = 's3://${SERVING_BUCKET}/serving/' storage_integration = SI_SERVING;
-- Fixture: internal stages (no AWS involved).
create or replace file format LATAM_FIXTURE.RAW.CSV_HEADER
  type = CSV parse_header = true error_on_column_count_mismatch = false skip_byte_order_mark = true
  field_optionally_enclosed_by = '"' null_if = ('') empty_field_as_null = true;
create stage if not exists LATAM_FIXTURE.RAW.FIXTURE_STAGE file_format = LATAM_FIXTURE.RAW.CSV_HEADER;
create stage if not exists LATAM_FIXTURE.RAW.SERVING_STAGE;
grant usage on integration SI_SERVING to role PIPELINE_ROLE;
grant all on all stages in schema LATAM_BANK.RAW to role PIPELINE_ROLE;
grant all on all stages in schema LATAM_FIXTURE.RAW to role PIPELINE_ROLE;
grant all on all file formats in schema LATAM_BANK.RAW to role PIPELINE_ROLE;
grant all on all file formats in schema LATAM_FIXTURE.RAW to role PIPELINE_ROLE;
```

`infra/snowflake/02_raw_tables.sql` (parametrized by `${DATABASE}` so it runs for both databases):
```sql
-- uv run python -m pipeline.setup 02_raw_tables.sql ; SETUP_DATABASE=LATAM_FIXTURE uv run python -m pipeline.setup 02_raw_tables.sql
use role PIPELINE_ROLE;
use database ${DATABASE};
create table if not exists RAW.CUSTOMERS (
  customer_id varchar, document_number varchar, document_type varchar, first_name varchar, last_name varchar,
  date_of_birth varchar, gender varchar, email varchar, mobile_phone varchar, landline_phone varchar, address varchar,
  city varchar, state varchar, country varchar, postal_code varchar, detected_accent varchar, segment varchar,
  credit_score varchar, estimated_monthly_income varchar, occupation varchar, marital_status varchar,
  education_level varchar, registration_date varchar, registration_branch_id varchar, customer_status varchar,
  last_updated varchar, accepts_marketing varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.PRODUCTS (
  product_id varchar, customer_id varchar, product_type varchar, product_number varchar, currency varchar,
  current_balance varchar, credit_limit varchar, interest_rate varchar, opening_date varchar, expiration_date varchar,
  opening_branch_id varchar, product_status varchar, opening_channel varchar, has_linked_app varchar,
  days_past_due varchar, last_transaction_date varchar, last_updated varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.TRANSACTIONS (
  transaction_id varchar, transaction_date varchar, process_date varchar, product_id varchar, customer_id varchar,
  transaction_type varchar, transaction_category varchar, amount varchar, currency varchar, amount_usd varchar,
  channel varchar, branch_id varchar, merchant_name varchar, merchant_category varchar, transaction_country varchar,
  transaction_city varchar, transaction_status varchar, response_code varchar, is_fraud varchar, fraud_score varchar,
  latitude varchar, longitude varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.COMPLAINTS (
  complaint_id varchar, creation_date varchar, process_date varchar, customer_id varchar, case_type varchar,
  category varchar, subcategory varchar, reception_channel varchar, affected_product_id varchar,
  related_branch_id varchar, origin_interaction_id varchar, description varchar, claimed_amount varchar,
  currency varchar, priority varchar, status varchar, assigned_agent_id varchar, assignment_date varchar,
  first_response_date varchar, resolution_date varchar, closing_date varchar, sla_breached varchar,
  resolution_days varchar, resolution varchar, compensation_granted varchar, resolution_satisfaction varchar,
  is_repeat_complainer varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.INTERACTIONS (
  interaction_id varchar, interaction_date varchar, process_date varchar, customer_id varchar, agent_id varchar,
  interaction_type varchar, channel varchar, contact_reason varchar, reason_category varchar,
  duration_seconds varchar, wait_time_seconds varchar, was_resolved varchar, requires_followup varchar,
  detected_sentiment varchar, sentiment_score varchar, customer_detected_accent varchar, agent_used_accent varchar,
  was_escalated varchar, mentioned_products varchar, has_transcript varchar, has_recording varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists META.RUN_MANIFEST (
  run_id varchar, table_name varchar, file_path varchar, etag varchar, mode varchar, rows_loaded number,
  loaded_at timestamp_ntz default current_timestamp()
);
create table if not exists META.DQ_RESULTS (
  run_id varchar, test_name varchar, model varchar, severity varchar, status varchar, failures number,
  ran_at timestamp_ntz
);
```

- [ ] **Step 6: Document the AWS role for the storage integration**

`infra/aws/snowflake-serving-role.md`:
```markdown
# IAM role for Snowflake → our serving bucket

1. Run `01_integrations.sql` once with the placeholder ARN, then in Snowsight:
   `DESC INTEGRATION SI_SERVING;` and copy `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID`.
2. Create IAM role `snowflake-serving-writer` with this trust policy:
   {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":"<STORAGE_AWS_IAM_USER_ARN>"},
     "Action":"sts:AssumeRole","Condition":{"StringEquals":{"sts:ExternalId":"<STORAGE_AWS_EXTERNAL_ID>"}}}]}
   and this inline policy:
   {"Version":"2012-10-17","Statement":[
     {"Effect":"Allow","Action":["s3:PutObject","s3:GetObject","s3:DeleteObject"],"Resource":"arn:aws:s3:::<SERVING_BUCKET>/serving/*"},
     {"Effect":"Allow","Action":["s3:ListBucket"],"Resource":"arn:aws:s3:::<SERVING_BUCKET>","Condition":{"StringLike":{"s3:prefix":["serving/*"]}}}]}
3. Put the role ARN in `.env` as `SERVING_ROLE_ARN` and re-run `01_integrations.sql`
   (the integration is `create if not exists`; run `ALTER STORAGE INTEGRATION SI_SERVING SET STORAGE_AWS_ROLE_ARN = '<arn>';` instead).
4. Verify: `LIST @LATAM_BANK.RAW.SERVING_STAGE;` returns without an access error.
```

- [ ] **Step 7: Run the scripts and smoke-check**

```bash
export PIPELINE_RSA_PUBLIC_KEY="$(grep -v -- '-----' ~/.snowflake/pipeline_rsa_key.pub | tr -d '\n')"
uv run python -m pipeline.setup 00_account.sql 01_integrations.sql 02_raw_tables.sql
SETUP_DATABASE=LATAM_FIXTURE uv run python -m pipeline.setup 02_raw_tables.sql
uv run python -m pipeline.connect
```
Expected: statement counts printed; the smoke check prints `('<YOU>', 'ACCOUNTADMIN', 'WH_PIPELINE', 'LATAM_BANK')`. Then in Snowsight: `LIST @LATAM_BANK.RAW.ORGANIZER_STAGE/customers/;` returns one file. Follow `infra/aws/snowflake-serving-role.md` and confirm `LIST @LATAM_BANK.RAW.SERVING_STAGE;` works.

- [ ] **Step 8: Commit**

```bash
git add infra pipeline/setup.py tests/test_setup.py
git commit -m "feat: Snowflake account objects, stages, RAW tables and setup runner"
```

---

### Task 3: Loader plan logic (pure functions)

**Files:**
- Create: `pipeline/load.py`, `tests/test_load.py`

**Interfaces:**
- Produces: `StageFile(path: str, md5: str, size: int)`, `LoadAction(path: str, mode: Literal["new","restated","skipped"])`, `plan_loads(files: list[StageFile], manifest: dict[str, str]) -> list[LoadAction]`, `relative_path(stage_url_prefix: str, listed_name: str) -> str`, `chunks(seq, n)`.
- Table registry: `TABLES = {"CUSTOMERS": "customers.csv", "PRODUCTS": "products.csv", "TRANSACTIONS": "transactions/", "COMPLAINTS": "complaints/", "INTERACTIONS": "call_center_interactions/"}` (RAW table → stage prefix).

- [ ] **Step 1: Write the failing tests**

`tests/test_load.py`:
```python
from pipeline.load import StageFile, LoadAction, plan_loads, relative_path, chunks, TABLES

def sf(path, md5="a", size=10):
    return StageFile(path=path, md5=md5, size=size)

def test_plan_loads_new_restated_skipped():
    files = [sf("transactions/year=2026/month=06/day=17/transactions_20260617.csv", "m1"),
             sf("transactions/year=2026/month=06/day=18/transactions_20260618.csv", "m2"),
             sf("transactions/year=2026/month=06/day=19/transactions_20260619.csv", "m3")]
    manifest = {"transactions/year=2026/month=06/day=17/transactions_20260617.csv": "m1",
                "transactions/year=2026/month=06/day=18/transactions_20260618.csv": "OLD"}
    actions = plan_loads(files, manifest)
    assert actions == [
        LoadAction(files[0].path, "skipped"),
        LoadAction(files[1].path, "restated"),
        LoadAction(files[2].path, "new"),
    ]

def test_plan_loads_zero_row_file_is_new():
    assert plan_loads([sf("transactions/x.csv", "m", size=0)], {}) == [LoadAction("transactions/x.csv", "new")]

def test_relative_path_strips_stage_prefix():
    name = "s3://bucket/data/transactions/year=2026/month=06/day=17/transactions_20260617.csv"
    assert relative_path("s3://bucket/data/", name) == "transactions/year=2026/month=06/day=17/transactions_20260617.csv"

def test_relative_path_internal_stage_strips_stage_name():
    assert relative_path("", "fixture_stage/transactions/year=2026/month=06/day=17/transactions_20260617.csv") == \
        "transactions/year=2026/month=06/day=17/transactions_20260617.csv"

def test_chunks():
    assert list(chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]

def test_tables_registry():
    assert TABLES["INTERACTIONS"] == "call_center_interactions/"
    assert TABLES["CUSTOMERS"] == "customers.csv"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_load.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.load'`

- [ ] **Step 3: Write the pure functions**

`pipeline/load.py` (first half; the Snowflake calls come in Task 4):
```python
"""Loader: LIST the organizer stage, compare ETags with META.RUN_MANIFEST, COPY new/changed files into RAW."""
from dataclasses import dataclass
from typing import Literal

TABLES: dict[str, str] = {
    "CUSTOMERS": "customers.csv",
    "PRODUCTS": "products.csv",
    "TRANSACTIONS": "transactions/",
    "COMPLAINTS": "complaints/",
    "INTERACTIONS": "call_center_interactions/",
}
Mode = Literal["new", "restated", "skipped"]


@dataclass(frozen=True)
class StageFile:
    path: str   # relative to the stage URL, e.g. transactions/year=2026/month=06/day=17/transactions_20260617.csv
    md5: str
    size: int


@dataclass(frozen=True)
class LoadAction:
    path: str
    mode: Mode


def relative_path(stage_url_prefix: str, listed_name: str) -> str:
    if stage_url_prefix and listed_name.startswith(stage_url_prefix):
        return listed_name[len(stage_url_prefix):]
    # internal stages (prefix '') list names as <stage_name>/<path>
    return listed_name.split("/", 1)[1] if "/" in listed_name else listed_name


def plan_loads(files: list[StageFile], manifest: dict[str, str]) -> list[LoadAction]:
    out = []
    for f in files:
        if f.path not in manifest:
            out.append(LoadAction(f.path, "new"))
        elif manifest[f.path] != f.md5:
            out.append(LoadAction(f.path, "restated"))
        else:
            out.append(LoadAction(f.path, "skipped"))
    return out


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield list(seq[i:i + n])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_load.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/load.py tests/test_load.py
git commit -m "feat: loader plan logic (new / restated / skipped by ETag)"
```

---

### Task 4: Loader Snowflake calls and first full load

**Files:**
- Modify: `pipeline/load.py` (append)
- Create: `tests/test_load_live.py`

**Interfaces:**
- Consumes: Task 3 functions, `pipeline.connect.get_connection`.
- Produces: `list_stage_files(cur, stage: str, prefix: str, stage_url_prefix: str) -> list[StageFile]`, `read_manifest(cur, table: str) -> dict[str, str]`, `copy_files(cur, table: str, stage: str, paths: list[str], force: bool) -> dict[str, int]` (path → rows_loaded), `record_manifest(cur, run_id, table, rows: list[tuple[path, etag, mode, rows_loaded]])`, `run_load(conn, run_id: str, stage: str = "RAW.ORGANIZER_STAGE", stage_url_prefix: str = "", tables=TABLES) -> dict[str, dict[str, int]]` (table → {"new": n, "restated": n, "skipped": n}). CLI: `uv run python -m pipeline.load --run-id <id> [--database LATAM_FIXTURE --stage RAW.FIXTURE_STAGE]`.

- [ ] **Step 1: Write the failing live test (marked `snowflake`)**

`tests/test_load_live.py`:
```python
import os, uuid
import pytest
from pipeline.connect import get_connection
from pipeline.load import list_stage_files, read_manifest, copy_files, record_manifest

pytestmark = pytest.mark.snowflake
STAGE_URL = f"s3://{os.environ.get('DATA_BUCKET','')}/data/"

@pytest.fixture(scope="module")
def cur():
    with get_connection() as conn:
        yield conn.cursor()

def test_list_stage_files_returns_relative_paths(cur):
    files = list_stage_files(cur, "RAW.ORGANIZER_STAGE", "customers.csv", STAGE_URL)
    assert len(files) == 1 and files[0].path == "customers.csv" and len(files[0].md5) == 32

def test_copy_and_manifest_roundtrip_on_fixture_db(cur):
    cur.execute("use database LATAM_FIXTURE")
    cur.execute("truncate table if exists RAW.CUSTOMERS")
    cur.execute("delete from META.RUN_MANIFEST where table_name = 'CUSTOMERS'")
    # stage a tiny customers file into the internal fixture stage
    import tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "customers.csv"
    p.write_text("customer_id,country,segment\nC1,MX,Retail\nC2,CO,Premium\n")
    cur.execute(f"put file://{p} @RAW.FIXTURE_STAGE auto_compress=false overwrite=true")
    rows = copy_files(cur, "CUSTOMERS", "RAW.FIXTURE_STAGE", ["customers.csv"], force=False)
    assert rows == {"customers.csv": 2}
    run_id = uuid.uuid4().hex[:8]
    record_manifest(cur, run_id, "CUSTOMERS", [("customers.csv", "etag1", "new", 2)])
    assert read_manifest(cur, "CUSTOMERS") == {"customers.csv": "etag1"}
    n = cur.execute("select count(*), max(_source_file), max(_loaded_at) is not null from RAW.CUSTOMERS").fetchone()
    assert n[0] == 2 and n[1].endswith("customers.csv") and n[2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `set -a; source .env; set +a; uv run pytest tests/test_load_live.py -v -m snowflake`
Expected: FAIL with `ImportError: cannot import name 'list_stage_files'`

- [ ] **Step 3: Append the Snowflake calls and CLI**

Append to `pipeline/load.py`:
```python
import argparse
import os
import sys
import uuid

FILES_PER_COPY = 500  # Snowflake FILES list limit is 1000

INCLUDE_METADATA = ("include_metadata = (_source_file = METADATA$FILENAME, _file_row = METADATA$FILE_ROW_NUMBER, "
                    "_file_last_modified = METADATA$FILE_LAST_MODIFIED, _loaded_at = METADATA$START_SCAN_TIME)")


def list_stage_files(cur, stage: str, prefix: str, stage_url_prefix: str) -> list[StageFile]:
    rows = cur.execute(f"list @{stage}/{prefix}").fetchall()  # name, size, md5, last_modified
    return [StageFile(relative_path(stage_url_prefix, r[0]), r[2], int(r[1])) for r in rows if r[0].endswith(".csv")]


def read_manifest(cur, table: str) -> dict[str, str]:
    rows = cur.execute(
        "select file_path, etag from META.RUN_MANIFEST where table_name = %s and mode <> 'skipped' "
        "qualify row_number() over (partition by file_path order by loaded_at desc) = 1", (table,)).fetchall()
    return {r[0]: r[1] for r in rows}


def copy_files(cur, table: str, stage: str, paths: list[str], force: bool) -> dict[str, int]:
    loaded: dict[str, int] = {}
    for batch in chunks(paths, FILES_PER_COPY):
        files = ", ".join(f"'{p}'" for p in batch)
        res = cur.execute(
            f"copy into RAW.{table} from @{stage} files = ({files}) "
            f"match_by_column_name = case_insensitive {INCLUDE_METADATA} "
            f"on_error = abort_statement force = {'true' if force else 'false'}").fetchall()
        for r in res:  # file, status, rows_parsed, rows_loaded, ...
            listed = r[0]
            key = next((p for p in batch if listed.endswith(p)), listed)
            loaded[key] = int(r[3] or 0)
    for p in paths:
        loaded.setdefault(p, 0)  # header-only file or already-loaded file reports no row
    return loaded


def record_manifest(cur, run_id: str, table: str, rows: list[tuple[str, str, str, int]]) -> None:
    if rows:
        cur.executemany(
            "insert into META.RUN_MANIFEST (run_id, table_name, file_path, etag, mode, rows_loaded) values (%s, %s, %s, %s, %s, %s)",
            [(run_id, table, p, e, m, n) for (p, e, m, n) in rows])


def run_load(conn, run_id: str, stage: str = "RAW.ORGANIZER_STAGE", stage_url_prefix: str = "", tables=TABLES) -> dict[str, dict[str, int]]:
    cur = conn.cursor()
    summary: dict[str, dict[str, int]] = {}
    for table, prefix in tables.items():
        files = list_stage_files(cur, stage, prefix, stage_url_prefix)
        manifest = read_manifest(cur, table)
        actions = plan_loads(files, manifest)
        md5 = {f.path: f.md5 for f in files}
        counts = {"new": 0, "restated": 0, "skipped": 0}
        rows: list[tuple[str, str, str, int]] = []
        for mode, force in (("new", False), ("restated", True)):
            paths = [a.path for a in actions if a.mode == mode]
            if paths:
                loaded = copy_files(cur, table, stage, paths, force=force)
                rows += [(p, md5[p], mode, loaded[p]) for p in paths]
                counts[mode] = len(paths)
        counts["skipped"] = sum(1 for a in actions if a.mode == "skipped")
        record_manifest(cur, run_id, table, rows)
        conn.commit()
        summary[table] = counts
        print(f"{table}: {counts}", file=sys.stderr)
    return summary


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pipeline.connect import get_connection

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=uuid.uuid4().hex[:12])
    ap.add_argument("--database", default=None)
    ap.add_argument("--stage", default="RAW.ORGANIZER_STAGE")
    ap.add_argument("--stage-url-prefix", default=f"s3://{os.environ.get('DATA_BUCKET', '')}/data/")
    a = ap.parse_args()
    with get_connection(a.database) as conn:
        run_load(conn, a.run_id, a.stage, a.stage_url_prefix)
```

- [ ] **Step 4: Run the live test**

Run: `set -a; source .env; set +a; uv run pytest tests/test_load_live.py -v -m snowflake`
Expected: 2 passed. (The `put` of a 3-column customers file exercises `MATCH_BY_COLUMN_NAME`: unspecified RAW columns stay null.)

- [ ] **Step 5: First full load and a row-count check**

```bash
set -a; source .env; set +a
uv run python -m pipeline.load --run-id initial
```
Expected stderr: `CUSTOMERS: {'new': 1, ...}`, `TRANSACTIONS: {'new': 1097, ...}`, `INTERACTIONS: {'new': 1097, ...}`, `COMPLAINTS: {'new': 1097, ...}`, `PRODUCTS: {'new': 1, ...}`. Takes roughly 10 to 20 minutes on X-Small. Then in Snowsight:
```sql
select 'transactions', count(*) from LATAM_BANK.RAW.TRANSACTIONS
union all select 'interactions', count(*) from LATAM_BANK.RAW.INTERACTIONS
union all select 'complaints', count(*) from LATAM_BANK.RAW.COMPLAINTS
union all select 'customers', count(*) from LATAM_BANK.RAW.CUSTOMERS
union all select 'products', count(*) from LATAM_BANK.RAW.PRODUCTS;
```
Expected: interactions 686,296; complaints 67,095; customers 150,000; products 400,000; transactions in the 4.5M to 5M range. Re-run `uv run python -m pipeline.load --run-id rerun` and confirm every table reports `skipped` equal to its file count and `new: 0`.

- [ ] **Step 6: Commit**

```bash
git add pipeline/load.py tests/test_load_live.py
git commit -m "feat: loader with ETag manifest, batched COPY INTO and CLI"
```

---

### Task 5: dbt project, sources with freshness, and the unexpected-column test

**Files:**
- Create: `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/models/staging/sources.yml`, `dbt/tests/warn_unexpected_columns.sql`, `dbt/.gitignore`

**Interfaces:**
- Produces: dbt profile `latam_bank` with targets `dev` (database `LATAM_BANK`, key pair), `ci` (same, env-driven), `fixture` (database `LATAM_FIXTURE`); sources `raw.customers|products|transactions|complaints|interactions` and `meta.run_manifest|dq_results`. Commands: `cd dbt && uv run dbt build --target dev`.

- [ ] **Step 1: Write the project and profile**

`dbt/dbt_project.yml`:
```yaml
name: latam_bank
version: "1.0.0"
profile: latam_bank
model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]
macro-paths: ["macros"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]
models:
  latam_bank:
    staging:
      +schema: STAGING
      +materialized: table
    curated:
      +schema: CURATED
      +materialized: table
seeds:
  latam_bank:
    +schema: CURATED
tests:
  +store_failures: true
  +schema: META
```

`dbt/profiles.yml` (committed; secrets come from env):
```yaml
latam_bank:
  target: dev
  outputs:
    dev: &base
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      private_key_path: "{{ env_var('SNOWFLAKE_PRIVATE_KEY_PATH') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'PIPELINE_ROLE') }}"
      warehouse: WH_PIPELINE
      database: LATAM_BANK
      schema: STAGING
      threads: 4
      client_session_keep_alive: false
    ci:
      <<: *base
    fixture:
      <<: *base
      database: LATAM_FIXTURE
```

`dbt/.gitignore`:
```
target/
dbt_packages/
logs/
```

Add a macro so custom schema names are used verbatim (dbt's default prefixes the target schema):

`dbt/macros/generate_schema_name.sql`:
```sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ (custom_schema_name or target.schema) | trim }}
{%- endmacro %}
```

- [ ] **Step 2: Write sources with freshness and full column lists**

`dbt/models/staging/sources.yml`:
```yaml
version: 2
sources:
  - name: raw
    database: "{{ target.database }}"
    schema: RAW
    loaded_at_field: _loaded_at
    freshness:
      warn_after: {count: 2, period: day}
      error_after: {count: 7, period: day}
    tables:
      - name: customers
        columns:
          - {name: customer_id}
          - {name: document_number}
          - {name: document_type}
          - {name: first_name}
          - {name: last_name}
          - {name: date_of_birth}
          - {name: gender}
          - {name: email}
          - {name: mobile_phone}
          - {name: landline_phone}
          - {name: address}
          - {name: city}
          - {name: state}
          - {name: country}
          - {name: postal_code}
          - {name: detected_accent}
          - {name: segment}
          - {name: credit_score}
          - {name: estimated_monthly_income}
          - {name: occupation}
          - {name: marital_status}
          - {name: education_level}
          - {name: registration_date}
          - {name: registration_branch_id}
          - {name: customer_status}
          - {name: last_updated}
          - {name: accepts_marketing}
      - name: products
        columns:
          - {name: product_id}
          - {name: customer_id}
          - {name: product_type}
          - {name: product_number}
          - {name: currency}
          - {name: current_balance}
          - {name: credit_limit}
          - {name: interest_rate}
          - {name: opening_date}
          - {name: expiration_date}
          - {name: opening_branch_id}
          - {name: product_status}
          - {name: opening_channel}
          - {name: has_linked_app}
          - {name: days_past_due}
          - {name: last_transaction_date}
          - {name: last_updated}
      - name: transactions
        columns:
          - {name: transaction_id}
          - {name: transaction_date}
          - {name: process_date}
          - {name: product_id}
          - {name: customer_id}
          - {name: transaction_type}
          - {name: transaction_category}
          - {name: amount}
          - {name: currency}
          - {name: amount_usd}
          - {name: channel}
          - {name: branch_id}
          - {name: merchant_name}
          - {name: merchant_category}
          - {name: transaction_country}
          - {name: transaction_city}
          - {name: transaction_status}
          - {name: response_code}
          - {name: is_fraud}
          - {name: fraud_score}
          - {name: latitude}
          - {name: longitude}
      - name: complaints
        columns:
          - {name: complaint_id}
          - {name: creation_date}
          - {name: process_date}
          - {name: customer_id}
          - {name: case_type}
          - {name: category}
          - {name: subcategory}
          - {name: reception_channel}
          - {name: affected_product_id}
          - {name: related_branch_id}
          - {name: origin_interaction_id}
          - {name: description}
          - {name: claimed_amount}
          - {name: currency}
          - {name: priority}
          - {name: status}
          - {name: assigned_agent_id}
          - {name: assignment_date}
          - {name: first_response_date}
          - {name: resolution_date}
          - {name: closing_date}
          - {name: sla_breached}
          - {name: resolution_days}
          - {name: resolution}
          - {name: compensation_granted}
          - {name: resolution_satisfaction}
          - {name: is_repeat_complainer}
      - name: interactions
        columns:
          - {name: interaction_id}
          - {name: interaction_date}
          - {name: process_date}
          - {name: customer_id}
          - {name: agent_id}
          - {name: interaction_type}
          - {name: channel}
          - {name: contact_reason}
          - {name: reason_category}
          - {name: duration_seconds}
          - {name: wait_time_seconds}
          - {name: was_resolved}
          - {name: requires_followup}
          - {name: detected_sentiment}
          - {name: sentiment_score}
          - {name: customer_detected_accent}
          - {name: agent_used_accent}
          - {name: was_escalated}
          - {name: mentioned_products}
          - {name: has_transcript}
          - {name: has_recording}
  - name: meta
    database: "{{ target.database }}"
    schema: META
    tables:
      - name: run_manifest
      - name: dq_results
```

- [ ] **Step 3: Write the unexpected-column singular test (warn)**

`dbt/tests/warn_unexpected_columns.sql`:
```sql
{{ config(severity = 'warn') }}
-- RAW columns not declared in sources.yml (schema evolution landed something new).
{% set expected = [] %}
{% for src in graph.sources.values() if src.source_name == 'raw' %}
  {% for col in src.columns.values() %}
    {% do expected.append("('" ~ src.name | upper ~ "','" ~ col.name | upper ~ "')") %}
  {% endfor %}
{% endfor %}
with declared as (
  select column1 as table_name, column2 as column_name from values {{ expected | join(', ') }}
), actual as (
  select table_name, column_name
  from {{ target.database }}.information_schema.columns
  where table_schema = 'RAW' and table_name in ('CUSTOMERS','PRODUCTS','TRANSACTIONS','COMPLAINTS','INTERACTIONS')
    and left(column_name, 1) <> '_'
)
select a.table_name, a.column_name
from actual a left join declared d using (table_name, column_name)
where d.column_name is null
```

- [ ] **Step 4: Run and verify**

```bash
set -a; source .env; set +a
cd dbt && uv run dbt debug --target dev && uv run dbt source freshness --target dev && uv run dbt test --select warn_unexpected_columns --target dev; cd ..
```
Expected: `dbt debug` → "All checks passed!"; freshness → `PASS` for the five raw tables (loaded today); the singular test → `PASS` (no undeclared columns yet).

- [ ] **Step 5: Commit**

```bash
git add dbt
git commit -m "feat: dbt project with RAW sources, freshness policy and unexpected-column warning"
```

---

### Task 6: Staging models with typing, dedup, quarantine, tests and a dbt unit test

**Files:**
- Create: `dbt/models/staging/typed_transactions.sql`, `typed_customers.sql`, `typed_products.sql`, `typed_complaints.sql`, `typed_interactions.sql`, `stg_transactions.sql`, `stg_customers.sql`, `stg_products.sql`, `stg_complaints.sql`, `stg_interactions.sql`, `quarantine.sql`, `dbt/models/staging/schema.yml`, `dbt/models/staging/unit_tests.yml`, `dbt/tests/assert_quarantine_rate.sql`, `dbt/tests/warn_event_vs_process_date.sql`

**Interfaces:**
- Consumes: sources from Task 5.
- Produces: `stg_*` views with typed contract columns (names as in spec §5.3, lowercase); `quarantine` table (`table_name`, `pk_value`, `reason`, `_source_file`, `_loaded_at`, `raw_row VARIANT`). Reason strings: `null:<col>`, `cast_failed:<col>`, `enum:<col>`.

- [ ] **Step 1: Write the dbt unit test first (typed_transactions)**

`dbt/models/staging/unit_tests.yml`:
```yaml
unit_tests:
  - name: typed_transactions_dedup_cast_enum
    model: typed_transactions
    given:
      - input: source('raw', 'transactions')
        rows:
          # T1 loaded twice: the newer load (Reversed) must win
          - {transaction_id: T1, transaction_date: "2026-06-17 10:00:00", process_date: "2026-06-17", product_id: P1, customer_id: C1, transaction_type: Purchase, amount: "10.00", currency: MXN, channel: POS, transaction_country: Mexico, transaction_status: Approved, is_fraud: "False", _loaded_at: "2026-06-18 00:00:00", _file_row: 1}
          - {transaction_id: T1, transaction_date: "2026-06-17 10:00:00", process_date: "2026-06-17", product_id: P1, customer_id: C1, transaction_type: Purchase, amount: "10.00", currency: MXN, channel: POS, transaction_country: Mexico, transaction_status: Reversed, is_fraud: "False", _loaded_at: "2026-06-19 00:00:00", _file_row: 1}
          # T2: bad amount
          - {transaction_id: T2, transaction_date: "2026-06-17 11:00:00", process_date: "2026-06-17", product_id: P1, customer_id: C1, transaction_type: Purchase, amount: "N/A", currency: MXN, channel: POS, transaction_country: Mexico, transaction_status: Approved, is_fraud: "False", _loaded_at: "2026-06-18 00:00:00", _file_row: 2}
          # T3 duplicated inside one file: highest _file_row wins
          - {transaction_id: T3, transaction_date: "2026-06-17 12:00:00", process_date: "2026-06-17", product_id: P1, customer_id: C1, transaction_type: Deposit, amount: "5.00", currency: MXN, channel: ATM, transaction_country: Mexico, transaction_status: Pending, is_fraud: "False", _loaded_at: "2026-06-18 00:00:00", _file_row: 3}
          - {transaction_id: T3, transaction_date: "2026-06-17 12:00:00", process_date: "2026-06-17", product_id: P1, customer_id: C1, transaction_type: Deposit, amount: "5.00", currency: MXN, channel: ATM, transaction_country: Mexico, transaction_status: Approved, is_fraud: "False", _loaded_at: "2026-06-18 00:00:00", _file_row: 4}
          # T4: ISO timestamp with T separator must be a cast failure, not a silent null
          - {transaction_id: T4, transaction_date: "2026-06-17T13:00:00", process_date: "2026-06-17", product_id: P1, customer_id: C1, transaction_type: Purchase, amount: "1.00", currency: MXN, channel: POS, transaction_country: Mexico, transaction_status: Approved, is_fraud: "False", _loaded_at: "2026-06-18 00:00:00", _file_row: 5}
          # T5: unknown status
          - {transaction_id: T5, transaction_date: "2026-06-17 14:00:00", process_date: "2026-06-17", product_id: P1, customer_id: C1, transaction_type: Purchase, amount: "1.00", currency: MXN, channel: POS, transaction_country: Mexico, transaction_status: Bogus, is_fraud: "False", _loaded_at: "2026-06-18 00:00:00", _file_row: 6}
    expect:
      rows:
        - {transaction_id: T1, transaction_status: Reversed, _quarantine_reason: null}
        - {transaction_id: T2, _quarantine_reason: "cast_failed:amount"}
        - {transaction_id: T3, transaction_status: Approved, _quarantine_reason: null}
        - {transaction_id: T4, _quarantine_reason: "cast_failed:transaction_date"}
        - {transaction_id: T5, _quarantine_reason: "enum:transaction_status"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd dbt && uv run dbt test --select typed_transactions --target dev; cd ..`
Expected: FAIL / compilation error, `typed_transactions` does not exist.

- [ ] **Step 3: Write the typed models**

`dbt/models/staging/typed_transactions.sql`:
```sql
{{ config(materialized='table') }}
with latest as (
    select *
    from {{ source('raw', 'transactions') }}
    qualify row_number() over (partition by transaction_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        transaction_id,
        try_to_timestamp_ntz(transaction_date, 'YYYY-MM-DD HH24:MI:SS') as transaction_ts,
        try_to_date(process_date, 'YYYY-MM-DD')                         as process_date,
        product_id,
        customer_id,
        transaction_type,
        transaction_category,
        try_to_decimal(amount, 15, 2)                                    as amount,
        currency,
        try_to_decimal(amount_usd, 15, 2)                                as amount_usd,
        channel,
        merchant_name,
        merchant_category,
        transaction_country,
        transaction_city,
        transaction_status,
        response_code,
        case when is_fraud = 'True' then true when is_fraud = 'False' then false end as is_fraud,
        try_to_decimal(fraud_score, 5, 2)                                as fraud_score,
        -- raw copies kept only to build reasons
        transaction_date as _raw_transaction_date, amount as _raw_amount, is_fraud as _raw_is_fraud,
        _source_file, _file_row, _loaded_at,
        object_construct(*) as raw_row
    from latest
)
select
    * exclude (_raw_transaction_date, _raw_amount, _raw_is_fraud),
    case
        when transaction_id is null then 'null:transaction_id'
        when _raw_transaction_date is null then 'null:transaction_date'
        when transaction_ts is null then 'cast_failed:transaction_date'
        when process_date is null then 'cast_failed:process_date'
        when product_id is null then 'null:product_id'
        when customer_id is null then 'null:customer_id'
        when _raw_amount is null then 'null:amount'
        when amount is null then 'cast_failed:amount'
        when currency is null then 'null:currency'
        when _raw_is_fraud is not null and is_fraud is null then 'cast_failed:is_fraud'
        when transaction_type not in ('Deposit','Withdrawal','Transfer','Payment','Purchase','Adjustment') then 'enum:transaction_type'
        when transaction_status not in ('Approved','Declined','Pending','Reversed') then 'enum:transaction_status'
        when channel not in ('ATM','Branch','Web','App','POS','Transfer') then 'enum:channel'
    end as _quarantine_reason
from typed
```

`dbt/models/staging/typed_customers.sql`:
```sql
{{ config(materialized='table') }}
with latest as (
    select * from {{ source('raw', 'customers') }}
    qualify row_number() over (partition by customer_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        customer_id, city, state, country, detected_accent, segment, customer_status,
        try_to_date(registration_date, 'YYYY-MM-DD') as registration_date,
        case when accepts_marketing = 'True' then true when accepts_marketing = 'False' then false end as accepts_marketing,
        try_to_timestamp_ntz(last_updated, 'YYYY-MM-DD HH24:MI:SS') as last_updated,
        registration_date as _raw_registration_date, last_updated as _raw_last_updated,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_registration_date, _raw_last_updated),
    case
        when customer_id is null then 'null:customer_id'
        when country is null then 'null:country'
        when _raw_registration_date is not null and registration_date is null then 'cast_failed:registration_date'
        when _raw_last_updated is not null and last_updated is null then 'cast_failed:last_updated'
        when customer_status is null then 'null:customer_status'
    end as _quarantine_reason
from typed
```

`dbt/models/staging/typed_products.sql`:
```sql
{{ config(materialized='table') }}
with latest as (
    select * from {{ source('raw', 'products') }}
    qualify row_number() over (partition by product_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        product_id, customer_id, product_type,
        right(product_number, 4) as product_last4,
        currency,
        try_to_decimal(current_balance, 15, 2) as current_balance,
        try_to_decimal(credit_limit, 15, 2) as credit_limit,
        try_to_decimal(interest_rate, 5, 2) as interest_rate,
        try_to_date(opening_date, 'YYYY-MM-DD') as opening_date,
        try_to_date(expiration_date, 'YYYY-MM-DD') as expiration_date,
        product_status,
        case when has_linked_app = 'True' then true when has_linked_app = 'False' then false end as has_linked_app,
        try_to_number(days_past_due) as days_past_due,
        try_to_timestamp_ntz(last_transaction_date, 'YYYY-MM-DD HH24:MI:SS') as last_transaction_date,
        try_to_timestamp_ntz(last_updated, 'YYYY-MM-DD HH24:MI:SS') as last_updated,
        current_balance as _raw_balance, opening_date as _raw_opening_date,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_balance, _raw_opening_date),
    case
        when product_id is null then 'null:product_id'
        when customer_id is null then 'null:customer_id'
        when _raw_balance is null then 'null:current_balance'
        when current_balance is null then 'cast_failed:current_balance'
        when _raw_opening_date is not null and opening_date is null then 'cast_failed:opening_date'
        when product_type not in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Crédito','Tarjeta Débito','Préstamo Personal','Préstamo Hipotecario','Inversión','Seguro') then 'enum:product_type'
        when product_status not in ('Active','Blocked','Closed','Suspended') then 'enum:product_status'
    end as _quarantine_reason
from typed
```

`dbt/models/staging/typed_complaints.sql`:
```sql
{{ config(materialized='table') }}
with latest as (
    select * from {{ source('raw', 'complaints') }}
    qualify row_number() over (partition by complaint_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        complaint_id,
        try_to_timestamp_ntz(creation_date, 'YYYY-MM-DD HH24:MI:SS') as creation_ts,
        try_to_date(process_date, 'YYYY-MM-DD') as process_date,
        customer_id, case_type, category, subcategory, reception_channel, affected_product_id,
        try_to_decimal(claimed_amount, 15, 2) as claimed_amount,
        currency, priority, status,
        case when sla_breached = 'True' then true when sla_breached = 'False' then false end as sla_breached,
        try_to_number(try_to_double(resolution_days)) as resolution_days,
        try_to_number(try_to_double(resolution_satisfaction)) as resolution_satisfaction,
        case when is_repeat_complainer = 'True' then true when is_repeat_complainer = 'False' then false end as is_repeat_complainer,
        try_to_timestamp_ntz(first_response_date, 'YYYY-MM-DD HH24:MI:SS') as first_response_ts,
        try_to_timestamp_ntz(resolution_date, 'YYYY-MM-DD HH24:MI:SS') as resolution_ts,
        try_to_timestamp_ntz(closing_date, 'YYYY-MM-DD HH24:MI:SS') as closing_ts,
        creation_date as _raw_creation_date, claimed_amount as _raw_claimed_amount,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_creation_date, _raw_claimed_amount),
    case
        when complaint_id is null then 'null:complaint_id'
        when creation_ts is null then 'cast_failed:creation_date'
        when process_date is null then 'cast_failed:process_date'
        when customer_id is null then 'null:customer_id'
        when _raw_claimed_amount is not null and claimed_amount is null then 'cast_failed:claimed_amount'
        when case_type not in ('Complaint','Claim','Request','Suggestion') then 'enum:case_type'
        when status not in ('Open','In Process','Escalated','Resolved','Closed','Rejected') then 'enum:status'
        when priority not in ('Low','Medium','High','Critical') then 'enum:priority'
    end as _quarantine_reason
from typed
```

`dbt/models/staging/typed_interactions.sql`:
```sql
{{ config(materialized='table') }}
with latest as (
    select * from {{ source('raw', 'interactions') }}
    qualify row_number() over (partition by interaction_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        interaction_id,
        try_to_timestamp_ntz(interaction_date, 'YYYY-MM-DD HH24:MI:SS') as interaction_ts,
        try_to_date(process_date, 'YYYY-MM-DD') as process_date,
        customer_id, channel, interaction_type, reason_category,
        try_to_number(try_to_double(duration_seconds)) as duration_seconds,
        try_to_number(try_to_double(wait_time_seconds)) as wait_time_seconds,
        case when was_resolved = 'True' then true when was_resolved = 'False' then false end as was_resolved,
        case when requires_followup = 'True' then true when requires_followup = 'False' then false end as requires_followup,
        case when was_escalated = 'True' then true when was_escalated = 'False' then false end as was_escalated,
        case detected_sentiment
            when 'Muy Positivo' then 'Very Positive' when 'Positivo' then 'Positive' when 'Neutral' then 'Neutral'
            when 'Negativo' then 'Negative' when 'Muy Negativo' then 'Very Negative' end as detected_sentiment,
        try_to_decimal(sentiment_score, 3, 2) as sentiment_score,
        customer_detected_accent,
        case when has_transcript = 'True' then true when has_transcript = 'False' then false end as has_transcript,
        interaction_date as _raw_interaction_date, detected_sentiment as _raw_sentiment,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_interaction_date, _raw_sentiment),
    case
        when interaction_id is null then 'null:interaction_id'
        when interaction_ts is null then 'cast_failed:interaction_date'
        when process_date is null then 'cast_failed:process_date'
        when customer_id is null then 'null:customer_id'
        when _raw_sentiment is not null and detected_sentiment is null then 'enum:detected_sentiment'
        when reason_category not in ('Transaccional','Producto','Queja','Técnico','Comercial','Retención') then 'enum:reason_category'
        when channel not in ('Phone','Web Chat','WhatsApp','Email','App','Web') then 'enum:channel'
    end as _quarantine_reason
from typed
```

- [ ] **Step 4: Write the stg views and the quarantine table**

`dbt/models/staging/stg_transactions.sql`:
```sql
{{ config(materialized='view') }}
select * exclude (_quarantine_reason, raw_row) from {{ ref('typed_transactions') }} where _quarantine_reason is null
```
`dbt/models/staging/stg_customers.sql`, `stg_products.sql`, `stg_complaints.sql`, `stg_interactions.sql`: identical shape, each referencing its `typed_*` model:
```sql
{{ config(materialized='view') }}
select * exclude (_quarantine_reason, raw_row) from {{ ref('typed_customers') }} where _quarantine_reason is null
```

`dbt/models/staging/quarantine.sql`:
```sql
{{ config(materialized='table') }}
{% set parts = [('typed_transactions','transaction_id'), ('typed_customers','customer_id'), ('typed_products','product_id'),
                ('typed_complaints','complaint_id'), ('typed_interactions','interaction_id')] %}
{% for model, pk in parts %}
select '{{ model | replace("typed_", "") }}' as table_name, {{ pk }} as pk_value, _quarantine_reason as reason,
       _source_file, _loaded_at, raw_row
from {{ ref(model) }} where _quarantine_reason is not null
{% if not loop.last %}union all{% endif %}
{% endfor %}
```

- [ ] **Step 5: Write schema tests and the two singular tests**

`dbt/models/staging/schema.yml`:
```yaml
version: 2
models:
  - name: stg_customers
    columns:
      - name: customer_id
        tests: [unique, not_null]
      - name: country
        tests: [not_null]
      - name: customer_detected_accent
  - name: stg_products
    columns:
      - name: product_id
        tests: [unique, not_null]
      - name: customer_id
        tests:
          - not_null
          - relationships: {to: ref('stg_customers'), field: customer_id}
      - name: product_type
        tests:
          - accepted_values: {values: ['Cuenta Ahorro','Cuenta Corriente','Tarjeta Crédito','Tarjeta Débito','Préstamo Personal','Préstamo Hipotecario','Inversión','Seguro']}
      - name: product_status
        tests:
          - accepted_values: {values: ['Active','Blocked','Closed','Suspended']}
  - name: stg_transactions
    columns:
      - name: transaction_id
        tests: [unique, not_null]
      - name: customer_id
        tests:
          - not_null
          - relationships: {to: ref('stg_customers'), field: customer_id}
      - name: product_id
        tests:
          - not_null
          - relationships: {to: ref('stg_products'), field: product_id}
      - name: transaction_status
        tests:
          - accepted_values: {values: ['Approved','Declined','Pending','Reversed']}
      - name: transaction_type
        tests:
          - accepted_values: {values: ['Deposit','Withdrawal','Transfer','Payment','Purchase','Adjustment']}
      - name: channel
        tests:
          - accepted_values: {values: ['ATM','Branch','Web','App','POS','Transfer']}
  - name: stg_complaints
    columns:
      - name: complaint_id
        tests: [unique, not_null]
      - name: customer_id
        tests:
          - not_null
          - relationships: {to: ref('stg_customers'), field: customer_id}
      - name: affected_product_id
        tests:
          - relationships: {to: ref('stg_products'), field: product_id}
      - name: case_type
        tests:
          - accepted_values: {values: ['Complaint','Claim','Request','Suggestion']}
      - name: status
        tests:
          - accepted_values: {values: ['Open','In Process','Escalated','Resolved','Closed','Rejected']}
      - name: priority
        tests:
          - accepted_values: {values: ['Low','Medium','High','Critical']}
      - name: claimed_amount
        tests:
          - not_null: {config: {severity: warn}}
  - name: stg_interactions
    columns:
      - name: interaction_id
        tests: [unique, not_null]
      - name: customer_id
        tests:
          - not_null
          - relationships: {to: ref('stg_customers'), field: customer_id}
      - name: reason_category
        tests:
          - accepted_values: {values: ['Transaccional','Producto','Queja','Técnico','Comercial','Retención']}
      - name: duration_seconds
        tests:
          - not_null: {config: {severity: warn}}
      - name: customer_detected_accent
        tests:
          - not_null: {config: {severity: warn}}
  - name: quarantine
    columns:
      - name: reason
        tests: [not_null]
```

`dbt/tests/assert_quarantine_rate.sql` (error when quarantine exceeds 1% of rows loaded; the fixture target raises the ratio because its drop is tiny):
```sql
with q as (select count(*) as n from {{ ref('quarantine') }}),
     t as (select sum(rows_loaded) as n from {{ source('meta', 'run_manifest') }})
select q.n as quarantined, t.n as loaded from q, t where q.n > {{ var('quarantine_max_ratio', 0.01) }} * t.n
```

`dbt/tests/warn_event_vs_process_date.sql`:
```sql
{{ config(severity = 'warn') }}
select transaction_id, transaction_ts, process_date
from {{ ref('stg_transactions') }}
where abs(datediff('day', transaction_ts::date, process_date)) > 1
```

- [ ] **Step 6: Run the unit test, then build staging**

```bash
cd dbt
uv run dbt test --select typed_transactions,test_type:unit --target dev
uv run dbt build --select staging --target dev
cd ..
```
Expected: unit test PASS; build completes with all error-severity tests PASS, warn-severity tests reporting warnings for `duration_seconds`, `customer_detected_accent`, `claimed_amount` nulls. In Snowsight, `select count(*) from LATAM_BANK.STAGING.QUARANTINE` returns 0 for the real drop.

- [ ] **Step 7: Commit**

```bash
git add dbt
git commit -m "feat: staging models with typing, dedup, quarantine, tests and unit test"
```

---

### Task 7: Curated marts with enforced contracts, the decline-reason seed, and DQ results

**Files:**
- Create: `dbt/models/curated/dim_customer.sql`, `dim_product.sql`, `fct_transaction.sql`, `fct_complaint.sql`, `fct_interaction.sql`, `dbt/models/curated/schema.yml`, `dbt/seeds/seed_decline_reason.csv`, `dbt/seeds/seeds.yml`, `pipeline/dq_results.py`, `tests/test_dq_results.py`

**Interfaces:**
- Consumes: `stg_*` from Task 6.
- Produces: curated tables per spec §5.3; `pipeline.dq_results.parse_dbt_results(run_results: dict, manifest: dict) -> list[dict]` with keys `test_name, model, severity, status, failures`; `pipeline.dq_results.write(cur, run_id, rows)`; CLI `uv run python -m pipeline.dq_results --run-id <id> [--database ...]` reading `dbt/target/run_results.json` and `dbt/target/manifest.json`.

- [ ] **Step 1: Write the failing test for the results parser**

`tests/test_dq_results.py`:
```python
from pipeline.dq_results import parse_dbt_results

RUN = {"results": [
    {"unique_id": "test.latam_bank.unique_stg_transactions_transaction_id.abc", "status": "pass", "failures": 0},
    {"unique_id": "test.latam_bank.warn_unexpected_columns", "status": "warn", "failures": 2},
    {"unique_id": "model.latam_bank.dim_customer", "status": "success", "failures": None},
]}
MANIFEST = {"nodes": {
    "test.latam_bank.unique_stg_transactions_transaction_id.abc": {"name": "unique_stg_transactions_transaction_id", "config": {"severity": "ERROR"}, "depends_on": {"nodes": ["model.latam_bank.stg_transactions"]}},
    "test.latam_bank.warn_unexpected_columns": {"name": "warn_unexpected_columns", "config": {"severity": "warn"}, "depends_on": {"nodes": []}},
}}

def test_parse_only_tests_with_model_and_severity():
    rows = parse_dbt_results(RUN, MANIFEST)
    assert rows == [
        {"test_name": "unique_stg_transactions_transaction_id", "model": "stg_transactions", "severity": "error", "status": "pass", "failures": 0},
        {"test_name": "warn_unexpected_columns", "model": None, "severity": "warn", "status": "warn", "failures": 2},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dq_results.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dq_results'`

- [ ] **Step 3: Write the parser and writer**

`pipeline/dq_results.py`:
```python
"""Persist dbt test outcomes into META.DQ_RESULTS. Usage: uv run python -m pipeline.dq_results --run-id <id>"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_dbt_results(run_results: dict, manifest: dict) -> list[dict]:
    nodes = manifest.get("nodes", {})
    rows = []
    for r in run_results.get("results", []):
        uid = r["unique_id"]
        if not uid.startswith("test."):
            continue
        node = nodes.get(uid, {})
        models = [n.split(".")[-1] for n in node.get("depends_on", {}).get("nodes", []) if n.startswith("model.")]
        rows.append({
            "test_name": node.get("name", uid.split(".")[2]),
            "model": models[0] if models else None,
            "severity": str(node.get("config", {}).get("severity", "error")).lower(),
            "status": r["status"],
            "failures": int(r.get("failures") or 0),
        })
    return rows


def write(cur, run_id: str, rows: list[dict]) -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cur.executemany(
        "insert into META.DQ_RESULTS (run_id, test_name, model, severity, status, failures, ran_at) values (%s, %s, %s, %s, %s, %s, %s)",
        [(run_id, r["test_name"], r["model"], r["severity"], r["status"], r["failures"], now) for r in rows])
    return len(rows)


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pipeline.connect import get_connection

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--database", default=None)
    ap.add_argument("--target-dir", default="dbt/target")
    a = ap.parse_args()
    t = Path(a.target_dir)
    rows = parse_dbt_results(json.loads((t / "run_results.json").read_text()), json.loads((t / "manifest.json").read_text()))
    with get_connection(a.database) as conn:
        n = write(conn.cursor(), a.run_id, rows)
        conn.commit()
    print(f"dq_results: {n} rows")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dq_results.py -v`
Expected: 1 passed

- [ ] **Step 5: Write the seed and curated models**

`dbt/seeds/seed_decline_reason.csv`:
```csv
response_code,reason_key,customer_text_es,customer_text_pt,next_step
00,approved,Operación aprobada,Operação aprovada,none
05,do_not_honor,El banco emisor rechazó la operación,O banco emissor recusou a operação,contact_issuer
14,invalid_card,El número de tarjeta no es válido,O número do cartão não é válido,verify_card
51,insufficient_funds,Fondos insuficientes,Saldo insuficiente,add_funds
54,expired_card,La tarjeta está vencida,O cartão está vencido,request_replacement
```

`dbt/seeds/seeds.yml`:
```yaml
version: 2
seeds:
  - name: seed_decline_reason
    description: "TEAM-AUTHORED SYNTHETIC POLICY DATA modeled on ISO 8583 response codes. Not from the organizer dataset."
    config:
      column_types: {response_code: varchar(2), reason_key: varchar, customer_text_es: varchar, customer_text_pt: varchar, next_step: varchar}
    columns:
      - name: response_code
        tests: [unique, not_null]
```

`dbt/models/curated/dim_customer.sql`:
```sql
select customer_id, country, city, state, segment, detected_accent, customer_status, registration_date, accepts_marketing, last_updated
from {{ ref('stg_customers') }}
```

`dbt/models/curated/dim_product.sql`:
```sql
select product_id, customer_id, product_type, product_last4, currency, current_balance, credit_limit, interest_rate,
       opening_date, expiration_date, product_status, has_linked_app, days_past_due, last_transaction_date, last_updated
from {{ ref('stg_products') }}
```

`dbt/models/curated/fct_transaction.sql`:
```sql
select t.transaction_id, t.transaction_ts, t.process_date, t.product_id, t.customer_id, t.transaction_type, t.transaction_category,
       t.amount, t.currency, t.amount_usd, t.channel, t.merchant_name, t.merchant_category, t.transaction_country, t.transaction_city,
       t.transaction_status, t.response_code,
       case when t.transaction_status = 'Approved' then null else d.reason_key end as decline_reason_key,
       t.is_fraud, t.fraud_score
from {{ ref('stg_transactions') }} t
left join {{ ref('seed_decline_reason') }} d on d.response_code = t.response_code
```

`dbt/models/curated/fct_complaint.sql`:
```sql
select complaint_id, creation_ts, process_date, customer_id, case_type, category, subcategory, reception_channel, affected_product_id,
       claimed_amount, currency, priority, status, sla_breached, resolution_days, resolution_satisfaction, is_repeat_complainer,
       first_response_ts, resolution_ts, closing_ts
from {{ ref('stg_complaints') }}
```

`dbt/models/curated/fct_interaction.sql`:
```sql
select interaction_id, interaction_ts, process_date, customer_id, channel, interaction_type, reason_category, duration_seconds,
       wait_time_seconds, was_resolved, requires_followup, was_escalated, detected_sentiment, sentiment_score,
       customer_detected_accent, has_transcript
from {{ ref('stg_interactions') }}
```

`dbt/models/curated/schema.yml` (contracts enforced; types are Snowflake's):
```yaml
version: 2
models:
  - name: dim_customer
    config: {contract: {enforced: true}}
    columns:
      - {name: customer_id, data_type: varchar, constraints: [{type: not_null}], tests: [unique, not_null]}
      - {name: country, data_type: varchar}
      - {name: city, data_type: varchar}
      - {name: state, data_type: varchar}
      - {name: segment, data_type: varchar}
      - {name: detected_accent, data_type: varchar}
      - {name: customer_status, data_type: varchar}
      - {name: registration_date, data_type: date}
      - {name: accepts_marketing, data_type: boolean}
      - {name: last_updated, data_type: timestamp_ntz}
  - name: dim_product
    config: {contract: {enforced: true}}
    columns:
      - {name: product_id, data_type: varchar, constraints: [{type: not_null}], tests: [unique, not_null]}
      - {name: customer_id, data_type: varchar, tests: [not_null]}
      - {name: product_type, data_type: varchar}
      - {name: product_last4, data_type: varchar}
      - {name: currency, data_type: varchar}
      - {name: current_balance, data_type: "number(15,2)"}
      - {name: credit_limit, data_type: "number(15,2)"}
      - {name: interest_rate, data_type: "number(5,2)"}
      - {name: opening_date, data_type: date}
      - {name: expiration_date, data_type: date}
      - {name: product_status, data_type: varchar}
      - {name: has_linked_app, data_type: boolean}
      - {name: days_past_due, data_type: number}
      - {name: last_transaction_date, data_type: timestamp_ntz}
      - {name: last_updated, data_type: timestamp_ntz}
  - name: fct_transaction
    config: {contract: {enforced: true}}
    columns:
      - {name: transaction_id, data_type: varchar, constraints: [{type: not_null}], tests: [unique, not_null]}
      - {name: transaction_ts, data_type: timestamp_ntz, tests: [not_null]}
      - {name: process_date, data_type: date, tests: [not_null]}
      - {name: product_id, data_type: varchar, tests: [not_null]}
      - {name: customer_id, data_type: varchar, tests: [not_null]}
      - {name: transaction_type, data_type: varchar}
      - {name: transaction_category, data_type: varchar}
      - {name: amount, data_type: "number(15,2)", tests: [not_null]}
      - {name: currency, data_type: varchar}
      - {name: amount_usd, data_type: "number(15,2)"}
      - {name: channel, data_type: varchar}
      - {name: merchant_name, data_type: varchar}
      - {name: merchant_category, data_type: varchar}
      - {name: transaction_country, data_type: varchar}
      - {name: transaction_city, data_type: varchar}
      - {name: transaction_status, data_type: varchar}
      - {name: response_code, data_type: varchar}
      - {name: decline_reason_key, data_type: varchar}
      - {name: is_fraud, data_type: boolean}
      - {name: fraud_score, data_type: "number(5,2)"}
  - name: fct_complaint
    config: {contract: {enforced: true}}
    columns:
      - {name: complaint_id, data_type: varchar, constraints: [{type: not_null}], tests: [unique, not_null]}
      - {name: creation_ts, data_type: timestamp_ntz}
      - {name: process_date, data_type: date}
      - {name: customer_id, data_type: varchar, tests: [not_null]}
      - {name: case_type, data_type: varchar}
      - {name: category, data_type: varchar}
      - {name: subcategory, data_type: varchar}
      - {name: reception_channel, data_type: varchar}
      - {name: affected_product_id, data_type: varchar}
      - {name: claimed_amount, data_type: "number(15,2)"}
      - {name: currency, data_type: varchar}
      - {name: priority, data_type: varchar}
      - {name: status, data_type: varchar}
      - {name: sla_breached, data_type: boolean}
      - {name: resolution_days, data_type: number}
      - {name: resolution_satisfaction, data_type: number}
      - {name: is_repeat_complainer, data_type: boolean}
      - {name: first_response_ts, data_type: timestamp_ntz}
      - {name: resolution_ts, data_type: timestamp_ntz}
      - {name: closing_ts, data_type: timestamp_ntz}
  - name: fct_interaction
    config: {contract: {enforced: true}}
    columns:
      - {name: interaction_id, data_type: varchar, constraints: [{type: not_null}], tests: [unique, not_null]}
      - {name: interaction_ts, data_type: timestamp_ntz}
      - {name: process_date, data_type: date}
      - {name: customer_id, data_type: varchar, tests: [not_null]}
      - {name: channel, data_type: varchar}
      - {name: interaction_type, data_type: varchar}
      - {name: reason_category, data_type: varchar}
      - {name: duration_seconds, data_type: number}
      - {name: wait_time_seconds, data_type: number}
      - {name: was_resolved, data_type: boolean}
      - {name: requires_followup, data_type: boolean}
      - {name: was_escalated, data_type: boolean}
      - {name: detected_sentiment, data_type: varchar}
      - {name: sentiment_score, data_type: "number(3,2)"}
      - {name: customer_detected_accent, data_type: varchar}
      - {name: has_transcript, data_type: boolean}
```

- [ ] **Step 6: Build everything and persist DQ results**

```bash
set -a; source .env; set +a
cd dbt && uv run dbt build --target dev; cd ..
uv run python -m pipeline.dq_results --run-id initial
```
Expected: `dbt build` completes; contracts pass (a type mismatch fails loudly with "contract enforced" in the message; fix the model, not the contract). `dq_results: N rows` printed; `select status, count(*) from LATAM_BANK.META.DQ_RESULTS group by 1` shows `pass` and `warn` rows only.

- [ ] **Step 7: Commit**

```bash
git add dbt pipeline/dq_results.py tests/test_dq_results.py
git commit -m "feat: curated marts with enforced contracts, decline-reason seed, DQ results persistence"
```

---

### Task 8: Export to the serving bucket with an atomic pointer

**Files:**
- Create: `pipeline/export.py`, `tests/test_export.py`

**Interfaces:**
- Consumes: curated tables (Task 7), `RAW.SERVING_STAGE` (Task 2).
- Produces: `EXPORT_TABLES`, `export_select(table: str, columns: list[str]) -> str`, `table_columns(cur, schema, table) -> list[str]`, `unload_table(cur, table, run_id, stage) -> int`, `build_pointer(run_id, exported_at, max_process_date, tables: dict[str,int]) -> dict`, `write_pointer(cur, pointer, stage)`, `list_runs(cur, stage) -> list[str]`, `prune_runs(cur, stage, keep=3)`, `run_export(conn, run_id, stage="RAW.SERVING_STAGE") -> dict`. CLI: `uv run python -m pipeline.export --run-id <id> [--database ... --stage ...]`. Pointer schema: `{"run_id": str, "exported_at": ISO-8601, "max_process_date": "YYYY-MM-DD", "tables": {"dim_customer": rows, ...}}` and files at `<stage>/<run_id>/<table>/data_*.parquet`.

- [ ] **Step 1: Write the failing tests**

`tests/test_export.py`:
```python
import pytest
from pipeline.export import EXPORT_TABLES, export_select, build_pointer, runs_to_prune, run_export

def test_export_tables():
    assert EXPORT_TABLES == ["dim_customer", "dim_product", "fct_transaction", "fct_complaint", "seed_decline_reason"]

def test_export_select_quotes_lowercase():
    sql = export_select("DIM_CUSTOMER", ["CUSTOMER_ID", "COUNTRY"])
    assert sql == 'select CUSTOMER_ID as "customer_id", COUNTRY as "country" from CURATED.DIM_CUSTOMER'

def test_build_pointer_shape():
    p = build_pointer("r1", "2026-09-27T06:00:00Z", "2026-06-17", {"dim_customer": 150000})
    assert p == {"run_id": "r1", "exported_at": "2026-09-27T06:00:00Z", "max_process_date": "2026-06-17", "tables": {"dim_customer": 150000}}

def test_runs_to_prune_keeps_newest_three():
    assert runs_to_prune(["20260925-a", "20260926-b", "20260927-c", "20260928-d"], keep=3) == ["20260925-a"]

class FailingCursor:
    def __init__(self): self.executed = []
    def execute(self, sql, *a):
        self.executed.append(sql)
        if "copy into" in sql.lower() and "fct_transaction" in sql.lower():
            raise RuntimeError("boom")
        return self
    def fetchall(self): return [("CUSTOMER_ID",)]
    def fetchone(self): return (1,)

class Conn:
    def __init__(self, cur): self._cur = cur
    def cursor(self): return self._cur
    def commit(self): pass

def test_run_export_does_not_write_pointer_on_failure():
    cur = FailingCursor()
    with pytest.raises(RuntimeError):
        run_export(Conn(cur), "r1", stage="RAW.SERVING_STAGE")
    assert not any("latest.json" in s for s in cur.executed)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.export'`

- [ ] **Step 3: Write the export module**

`pipeline/export.py`:
```python
"""Unload curated tables as parquet to <stage>/<run_id>/<table>/ and flip <stage>/latest.json. Usage: uv run python -m pipeline.export --run-id <id>"""
import argparse
import json
import sys
from datetime import datetime, timezone

EXPORT_TABLES = ["dim_customer", "dim_product", "fct_transaction", "fct_complaint", "seed_decline_reason"]


def table_columns(cur, schema: str, table: str) -> list[str]:
    rows = cur.execute(
        "select column_name from information_schema.columns where table_schema = %s and table_name = %s order by ordinal_position",
        (schema.upper(), table.upper())).fetchall()
    return [r[0] for r in rows]


def export_select(table: str, columns: list[str]) -> str:
    cols = ", ".join(f'{c} as "{c.lower()}"' for c in columns)
    return f"select {cols} from CURATED.{table.upper()}"


def unload_table(cur, table: str, run_id: str, stage: str) -> int:
    cols = table_columns(cur, "CURATED", table)
    res = cur.execute(
        f"copy into @{stage}/{run_id}/{table}/data_ from ({export_select(table, cols)}) "
        f"file_format = (type = parquet) header = true overwrite = true max_file_size = 268435456").fetchall()
    return sum(int(r[0]) for r in res)  # rows_unloaded per file


def build_pointer(run_id: str, exported_at: str, max_process_date: str, tables: dict[str, int]) -> dict:
    return {"run_id": run_id, "exported_at": exported_at, "max_process_date": max_process_date, "tables": tables}


def write_pointer(cur, pointer: dict, stage: str) -> None:
    payload = json.dumps(pointer).replace("'", "''")
    cur.execute(
        f"copy into @{stage}/latest.json from (select parse_json('{payload}')) "
        "file_format = (type = json compression = none) single = true overwrite = true")


def list_runs(cur, stage: str) -> list[str]:
    rows = cur.execute(f"list @{stage}/").fetchall()
    runs = set()
    for r in rows:
        rel = r[0].split("/serving/", 1)[-1] if "/serving/" in r[0] else r[0].split("/", 1)[-1]
        parts = rel.split("/")
        if len(parts) >= 3:
            runs.add(parts[0])
    return sorted(runs)


def runs_to_prune(runs: list[str], keep: int = 3) -> list[str]:
    return sorted(runs)[:-keep] if len(runs) > keep else []


def prune_runs(cur, stage: str, keep: int = 3) -> list[str]:
    old = runs_to_prune(list_runs(cur, stage), keep)
    for r in old:
        cur.execute(f"remove @{stage}/{r}/")
    return old


def run_export(conn, run_id: str, stage: str = "RAW.SERVING_STAGE") -> dict:
    cur = conn.cursor()
    counts = {}
    for t in EXPORT_TABLES:
        counts[t] = unload_table(cur, t, run_id, stage)   # any failure raises before the pointer moves
        print(f"unloaded {t}: {counts[t]} rows", file=sys.stderr)
    max_pd = cur.execute("select to_varchar(max(process_date), 'YYYY-MM-DD') from CURATED.FCT_TRANSACTION").fetchone()[0]
    pointer = build_pointer(run_id, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), max_pd, counts)
    write_pointer(cur, pointer, stage)
    conn.commit()
    prune_runs(cur, stage, keep=3)
    return pointer


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pipeline.connect import get_connection

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--database", default=None)
    ap.add_argument("--stage", default="RAW.SERVING_STAGE")
    a = ap.parse_args()
    with get_connection(a.database) as conn:
        print(json.dumps(run_export(conn, a.run_id, a.stage)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_export.py -v`
Expected: 5 passed

- [ ] **Step 5: Run a real export and verify from the bucket side**

```bash
set -a; source .env; set +a
uv run python -m pipeline.export --run-id "$(date +%Y%m%d)-initial"
```
Expected: JSON pointer printed with five table counts. In Snowsight: `LIST @LATAM_BANK.RAW.SERVING_STAGE/;` shows `latest.json` and `<run_id>/<table>/data_0_0_0.snappy.parquet` files. Quick reader check with DuckDB (uses the AWS profile that can read the bucket):
```bash
uv run --with duckdb python -c "
import duckdb, os; b=os.environ['SERVING_BUCKET']
c=duckdb.connect(); c.sql(\"create secret (type s3, provider credential_chain, region 'us-east-2')\")
p=c.sql(f\"select * from read_json_auto('s3://{b}/serving/latest.json')\").fetchone(); print(p)
print(c.sql(f\"describe select * from 's3://{b}/serving/{p[0]}/fct_transaction/*.parquet'\").fetchall()[:3])"
```
Expected: pointer row, and column names printed in lowercase (`transaction_id`, ...).

- [ ] **Step 6: Commit**

```bash
git add pipeline/export.py tests/test_export.py
git commit -m "feat: parquet export to serving stage with atomic latest.json pointer and pruning"
```

---

### Task 9: Fixture drop generator and the end-to-end proof test

**Files:**
- Create: `fixtures/README.md`, `fixtures/make_fixture.py`, `tests/test_fixture_drop.py`, `tests/test_make_fixture.py`

**Interfaces:**
- Consumes: loader CLI functions (`run_load`), dbt `fixture` target, `run_export`, `dq_results`.
- Produces: `fixtures.make_fixture.write_phase(out_dir: Path, phase: int) -> list[Path]` writing files under `out_dir/transactions/year=2026/month=06/day=DD/transactions_202606DD.csv`. Phase 1: day 17 original (20 rows). Phase 2: day 17 restated (3 rows changed to `Reversed` + 5 duplicate rows appended), day 18 new (10 rows), day 19 with extra column `merchant_country`, day 20 with one `amount = N/A`, day 21 header-only.

- [ ] **Step 1: Write the failing unit test for the generator**

`tests/test_make_fixture.py`:
```python
import csv
from pathlib import Path
from fixtures.make_fixture import write_phase, COLUMNS

def rows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))

def test_phase1_and_phase2_shapes(tmp_path):
    p1 = write_phase(tmp_path / "p1", 1)
    assert [p.name for p in p1] == ["transactions_20260617.csv"]
    r17 = rows(p1[0]); assert len(r17) == 20 and list(r17[0].keys()) == COLUMNS
    p2 = write_phase(tmp_path / "p2", 2)
    by = {p.name: p for p in p2}
    r17b = rows(by["transactions_20260617.csv"])
    assert len(r17b) == 25 and sum(1 for r in r17b if r["transaction_status"] == "Reversed") == 3
    ids = [r["transaction_id"] for r in r17b]; assert len(ids) - len(set(ids)) == 5
    assert len(rows(by["transactions_20260618.csv"])) == 10
    assert "merchant_country" in rows(by["transactions_20260619.csv"])[0]
    assert any(r["amount"] == "N/A" for r in rows(by["transactions_20260620.csv"]))
    assert rows(by["transactions_20260621.csv"]) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_make_fixture.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fixtures'`

- [ ] **Step 3: Write the generator and README**

`fixtures/__init__.py`: empty.

`fixtures/make_fixture.py`:
```python
"""SYNTHETIC fixture drop for the transactions table. Nothing here comes from the organizer dataset."""
import csv
from pathlib import Path

COLUMNS = ["transaction_id", "transaction_date", "process_date", "product_id", "customer_id", "transaction_type",
           "transaction_category", "amount", "currency", "amount_usd", "channel", "branch_id", "merchant_name",
           "merchant_category", "transaction_country", "transaction_city", "transaction_status", "response_code",
           "is_fraud", "fraud_score", "latitude", "longitude"]


def row(i: int, day: int, status: str = "Approved", amount: str | None = None, extra: dict | None = None) -> dict:
    r = {
        "transaction_id": f"FIX-{day:02d}-{i:04d}", "transaction_date": f"2026-06-{day:02d} 10:{i % 60:02d}:00",
        "process_date": f"2026-06-{day:02d}", "product_id": "PRD-FIXTURE0001", "customer_id": "CUS-FIXTURE0001",
        "transaction_type": "Purchase", "transaction_category": "Food", "amount": amount or f"{100 + i}.00",
        "currency": "MXN", "amount_usd": f"{(100 + i) / 17:.2f}", "channel": "POS", "branch_id": "",
        "merchant_name": "Tienda Fixture", "merchant_category": "5411", "transaction_country": "Mexico",
        "transaction_city": "CDMX", "transaction_status": status, "response_code": "00" if status == "Approved" else "05",
        "is_fraud": "False", "fraud_score": "3.5", "latitude": "19.43", "longitude": "-99.13",
    }
    if extra:
        r.update(extra)
    return r


def _write(path: Path, rows: list[dict], columns: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
    return path


def _path(out: Path, day: int) -> Path:
    return out / "transactions" / "year=2026" / "month=06" / f"day={day:02d}" / f"transactions_202606{day:02d}.csv"


def write_phase(out: Path, phase: int) -> list[Path]:
    if phase == 1:
        return [_write(_path(out, 17), [row(i, 17) for i in range(20)], COLUMNS)]
    d17 = [row(i, 17, status="Reversed" if i < 3 else "Approved") for i in range(20)]
    d17 += [row(i, 17) for i in range(5)]  # 5 exact duplicates of already-present keys (same file)
    files = [
        _write(_path(out, 17), d17, COLUMNS),
        _write(_path(out, 18), [row(i, 18) for i in range(10)], COLUMNS),
        _write(_path(out, 19), [row(i, 19, extra={"merchant_country": "MX"}) for i in range(5)], COLUMNS + ["merchant_country"]),
        _write(_path(out, 20), [row(0, 20, amount="N/A")] + [row(i, 20) for i in range(1, 5)], COLUMNS),
        _write(_path(out, 21), [], COLUMNS),
    ]
    return files


if __name__ == "__main__":
    import sys
    for p in write_phase(Path(sys.argv[1]), int(sys.argv[2])):
        print(p)
```

`fixtures/README.md`:
```markdown
# Fixture drop (synthetic)

Every row here is generated by `make_fixture.py`. It exists to prove the pipeline's behavior on
conditions the real organizer drop does not contain: a restated partition, duplicate keys,
a new column, a bad type, and a header-only file. Loaded only into `LATAM_FIXTURE` through the
internal stage `RAW.FIXTURE_STAGE`. Never mixed with `LATAM_BANK`.
```

- [ ] **Step 4: Run the generator test**

Run: `uv run pytest tests/test_make_fixture.py -v`
Expected: 1 passed

- [ ] **Step 5: Write the end-to-end proof test**

`tests/test_fixture_drop.py`:
```python
"""Proof of update correctness on a labeled synthetic drop. Needs Snowflake env vars; runs in CI."""
import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from fixtures.make_fixture import write_phase
from pipeline.connect import get_connection
from pipeline.export import run_export
from pipeline.load import run_load

pytestmark = pytest.mark.snowflake
DB, STAGE, SERVING = "LATAM_FIXTURE", "RAW.FIXTURE_STAGE", "RAW.SERVING_STAGE"
TABLES = {"TRANSACTIONS": "transactions/"}


def dbt(*args):
    env = {**os.environ, "DBT_PROFILES_DIR": "dbt"}
    r = subprocess.run(["uv", "run", "dbt", *args, "--target", "fixture", "--project-dir", "dbt",
                        "--vars", "{quarantine_max_ratio: 0.05}"], env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def upload(cur, files):
    for p in files:
        rel = p.relative_to(p.parents[4])  # transactions/year=.../file.csv
        cur.execute(f"put file://{p} @{STAGE}/{rel.parent.as_posix()}/ auto_compress=false overwrite=true")


@pytest.fixture(scope="module")
def conn():
    with get_connection(DB) as c:
        yield c


def reset(cur):
    cur.execute(f"remove @{STAGE}/")
    cur.execute(f"remove @{SERVING}/")
    for t in ["RAW.TRANSACTIONS"]:
        cur.execute(f"truncate table {t}")
    cur.execute("delete from META.RUN_MANIFEST")
    cur.execute("delete from META.DQ_RESULTS")


def test_fixture_drop_end_to_end(conn, tmp_path):
    cur = conn.cursor()
    reset(cur)
    # phase 1: original day 17
    upload(cur, write_phase(tmp_path / "p1", 1))
    s1 = run_load(conn, "fix-1", STAGE, "", TABLES)
    assert s1["TRANSACTIONS"] == {"new": 1, "restated": 0, "skipped": 0}
    rc, out = dbt("build", "--select", "typed_transactions", "stg_transactions", "quarantine", "fct_transaction", "seed_decline_reason")
    assert rc == 0, out
    p1 = run_export(conn, "fix-1", SERVING)
    assert p1["tables"]["fct_transaction"] == 20

    # phase 2: restated day 17 (+3 changed, +5 dups), new day 18, extra column day 19, bad amount day 20, header-only day 21
    upload(cur, write_phase(tmp_path / "p2", 2))
    s2 = run_load(conn, "fix-2", STAGE, "", TABLES)
    assert s2["TRANSACTIONS"] == {"new": 4, "restated": 1, "skipped": 0}
    rc, out = dbt("build", "--select", "typed_transactions", "stg_transactions", "quarantine", "fct_transaction", "seed_decline_reason", "warn_unexpected_columns", "assert_quarantine_rate")
    assert rc == 0, out
    subprocess.run(["uv", "run", "python", "-m", "pipeline.dq_results", "--run-id", "fix-2", "--database", DB], check=True)

    q = lambda sql: cur.execute(sql).fetchall()
    # new partition loaded
    assert q("select count(*) from STAGING.STG_TRANSACTIONS where process_date = '2026-06-18'")[0][0] == 10
    # duplicates collapsed: 20 unique keys for day 17
    assert q("select count(*), count(distinct transaction_id) from STAGING.STG_TRANSACTIONS where process_date = '2026-06-17'")[0] == (20, 20)
    # restated rows updated
    assert q("select count(*) from STAGING.STG_TRANSACTIONS where process_date = '2026-06-17' and transaction_status = 'Reversed'")[0][0] == 3
    # extra column landed in RAW, absent from staging, recorded as warn
    assert q("select count(*) from information_schema.columns where table_schema='RAW' and table_name='TRANSACTIONS' and column_name='MERCHANT_COUNTRY'")[0][0] == 1
    assert q("select count(*) from information_schema.columns where table_schema='STAGING' and table_name='STG_TRANSACTIONS' and column_name='MERCHANT_COUNTRY'")[0][0] == 0
    assert q("select status from META.DQ_RESULTS where run_id='fix-2' and test_name='warn_unexpected_columns'")[0][0] == "warn"
    # bad amount quarantined with reason
    assert q("select reason from STAGING.QUARANTINE where pk_value = 'FIX-20-0000'")[0][0] == "cast_failed:amount"
    # manifest records modes; header-only file loaded 0 rows as new
    modes = dict(q("select mode, count(*) from META.RUN_MANIFEST where run_id='fix-2' group by 1"))
    assert modes == {"new": 4, "restated": 1}
    assert q("select rows_loaded from META.RUN_MANIFEST where run_id='fix-2' and file_path like '%20260621%'")[0][0] == 0
    # pointer advanced and parquet columns are lowercase
    p2 = run_export(conn, "fix-2", SERVING)
    assert p2["run_id"] == "fix-2" and p2["tables"]["fct_transaction"] == 20 + 10 + 5 + 4
    local = tmp_path / "dl"; local.mkdir()
    cur.execute(f"get @{SERVING}/fix-2/fct_transaction/ file://{local}/")
    import pyarrow.parquet as pq
    f = next(local.glob("*.parquet"))
    assert "transaction_id" in pq.read_schema(f).names
```

- [ ] **Step 6: Run the proof**

Run: `set -a; source .env; set +a; uv run pytest tests/test_fixture_drop.py -v -m snowflake -s`
Expected: 1 passed in a few minutes. The fixture quarantines 1 row out of 65 loaded across both phases (1.5%), which is why the helper passes `quarantine_max_ratio: 0.05`; the production default stays 1%.

- [ ] **Step 7: Commit**

```bash
git add fixtures tests/test_make_fixture.py tests/test_fixture_drop.py dbt/tests/assert_quarantine_rate.sql
git commit -m "feat: synthetic fixture drop and end-to-end update-correctness proof"
```

---

### Task 10: GitHub Actions: CI on pull requests, scheduled pipeline on main

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/pipeline.yml`

**Interfaces:**
- Consumes: CLIs from Tasks 4, 7, 8; dbt `ci` target; Snowflake user `PIPELINE_SVC` (WIF subject `repo:<org>/<repo>:ref:refs/heads/main`).
- Repository secrets: `SNOWFLAKE_PRIVATE_KEY` (contents of `pipeline_rsa_key.p8`, used until WIF is confirmed for dbt). Repository variables: `SNOWFLAKE_ACCOUNT`, `SERVING_BUCKET`.

- [ ] **Step 1: Write the CI workflow**

`.github/workflows/ci.yml`:
```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run pytest -m "not snowflake" -q
  fixture:
    needs: unit
    if: github.event.pull_request.head.repo.full_name == github.repository || github.event_name == 'push'
    runs-on: ubuntu-latest
    env:
      SNOWFLAKE_ACCOUNT: ${{ vars.SNOWFLAKE_ACCOUNT }}
      SNOWFLAKE_USER: PIPELINE_SVC
      SNOWFLAKE_ROLE: PIPELINE_ROLE
      SNOWFLAKE_WAREHOUSE: WH_PIPELINE
      SNOWFLAKE_DATABASE: LATAM_BANK
      SNOWFLAKE_PRIVATE_KEY_PATH: ${{ github.workspace }}/.key.p8
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: printf '%s' "${{ secrets.SNOWFLAKE_PRIVATE_KEY }}" > .key.p8 && chmod 600 .key.p8
      - run: uv run pytest tests/test_fixture_drop.py -m snowflake -q
      - if: always()
        run: rm -f .key.p8
```

- [ ] **Step 2: Write the pipeline workflow**

`.github/workflows/pipeline.yml`:
```yaml
name: pipeline
on:
  schedule:
    - cron: "0 6 * * *"   # daily 06:00 UTC
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  id-token: write
concurrency: pipeline
env:
  SNOWFLAKE_ACCOUNT: ${{ vars.SNOWFLAKE_ACCOUNT }}
  SNOWFLAKE_USER: PIPELINE_SVC
  SNOWFLAKE_ROLE: PIPELINE_ROLE
  SNOWFLAKE_WAREHOUSE: WH_PIPELINE
  SNOWFLAKE_DATABASE: LATAM_BANK
  SNOWFLAKE_PRIVATE_KEY_PATH: ${{ github.workspace }}/.key.p8
  DBT_PROFILES_DIR: dbt
  RUN_ID: ${{ github.run_id }}-${{ github.run_attempt }}
jobs:
  load:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: printf '%s' "${{ secrets.SNOWFLAKE_PRIVATE_KEY }}" > .key.p8 && chmod 600 .key.p8
      - run: uv run python -m pipeline.load --run-id "$RUN_ID" --stage-url-prefix "s3://${{ vars.ORGANIZER_BUCKET }}/data/"
      - if: always()
        run: rm -f .key.p8
  build:
    needs: load
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: printf '%s' "${{ secrets.SNOWFLAKE_PRIVATE_KEY }}" > .key.p8 && chmod 600 .key.p8
      - run: uv run dbt source freshness --project-dir dbt --target ci || true
      - run: uv run dbt build --project-dir dbt --target ci
      - if: always()
        run: uv run python -m pipeline.dq_results --run-id "$RUN_ID"
      - if: always()
        run: rm -f .key.p8
  export:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: printf '%s' "${{ secrets.SNOWFLAKE_PRIVATE_KEY }}" > .key.p8 && chmod 600 .key.p8
      - run: uv run python -m pipeline.export --run-id "$RUN_ID"
      - if: always()
        run: rm -f .key.p8
```

Add repository variable `ORGANIZER_BUCKET` (the bucket name only; it is not a secret, but keep it out of the README).

- [ ] **Step 3: Try GitHub OIDC for the Python steps, keep the key pair only where needed**

In `pipeline.yml`, before the `load` and `export` run steps, add:
```yaml
      - id: oidc
        run: |
          TOKEN=$(curl -sH "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=snowflakecomputing.com" | jq -r .value)
          echo "::add-mask::$TOKEN"; echo "SNOWFLAKE_OIDC_TOKEN=$TOKEN" >> "$GITHUB_ENV"
```
`build_connect_kwargs` prefers the token, so `load` and `export` no longer read the key. Run the workflow with `workflow_dispatch`; if `load` fails with an authentication error, check `SHOW USERS LIKE 'PIPELINE_SVC'` for the WIF subject and the `audience`. Then for dbt: set `authenticator: workload_identity` on the `ci` target and run `dbt debug --target ci` in the `build` job; if dbt-snowflake rejects the value (`Invalid authenticator`), revert the profile change and keep the key file for the `build` job only. Record the outcome in the README access section.

- [ ] **Step 4: Push and verify**

```bash
git add .github
git commit -m "ci: pull-request checks and daily load → build → export pipeline"
git push -u origin main
```
Expected: `ci` green (unit + fixture), `pipeline` green on the push; `LIST @LATAM_BANK.RAW.SERVING_STAGE/` shows a new run folder and `latest.json` updated; `select max(loaded_at) from LATAM_BANK.META.RUN_MANIFEST` is today and every table reports `skipped` for unchanged files.

---

### Task 11: README for the data pipeline

**Files:**
- Create: `README.md` (pipeline section; the agent side adds its own sections later)

- [ ] **Step 1: Write the documentation**

`README.md` must contain these sections with real values from the run (fill the numbers from Snowsight, do not leave brackets):
```markdown
# Factored Hackathon 2026 — LATAM Bank customer-service system

## Data pipeline
Diagram: `docs/diagrams/pipeline.svg`. Spec: `docs/superpowers/specs/2026-09-26-data-pipeline-design.md`.

### Sources and contracts
Five tables from the organizer bucket (`customers`, `products`, `transactions`, `complaints`, `call_center_interactions`).
Contract columns are declared in `dbt/models/staging/sources.yml`; curated marts enforce column names and types
(`dbt/models/curated/schema.yml`). PII columns (names, document, birth date, contact details, address, credit score, income)
never leave RAW; product numbers are reduced to the last four digits.

### Freshness policy
Daily partitions, loaded by the scheduled workflow at 06:00 UTC. `dbt source freshness` warns after 2 days and errors after 7.
The serving pointer carries `max_process_date`, which the agent shows to customers as "data as of".

### Lineage
`META.RUN_MANIFEST` records every file loaded: run, table, path, ETag, mode (new / restated / skipped), rows. Every RAW row carries
its source file, row number, file timestamp and load time. `META.DQ_RESULTS` records every dbt test outcome per run.

### Quarantine policy
Rows failing a cast, a not-null contract column, or an enum land in `STAGING.QUARANTINE` with a reason and the raw row.
More than 1% quarantined in a run fails the build. Foreign-key breaks fail the build directly.

### Update correctness (fixture drop)
`fixtures/` is a labeled synthetic drop: restated partition, duplicate keys, new column, bad type, header-only file.
`tests/test_fixture_drop.py` runs it end to end on every pull request against `LATAM_FIXTURE`.

### Serving contract for the agent
`s3://<bucket>/serving/latest.json` → `{run_id, exported_at, max_process_date, tables}`; tables under `serving/<run_id>/<table>/*.parquet`
with lowercase column names: `dim_customer`, `dim_product`, `fct_transaction`, `fct_complaint`, `seed_decline_reason`.

### Access
Organizer keys live only inside the Snowflake stage definition. GitHub Actions authenticates to Snowflake as a service user via
OIDC workload identity for the Python steps; dbt uses <OIDC | a key pair (fallback), state which>. Snowflake writes to our bucket
through a storage integration (IAM role). The agent reads with its task role.

### Limitations found in the data
- Counts below the documented totals (686k interactions vs 800k; 67k complaints vs 80k).
- `data_backup_20260831/` is a different synthetic generation and is ignored.
- Transcripts are templated (about 42 distinct customer texts per category) with a single intent value; not loaded.
- Product IDs mentioned in calls do not exist in the products table; complaints never link to a call.
- Event timestamps fall on the day after the partition date for 25–33% of rows (timezone offset); tools query by event time.
- No duplicates or schema changes exist in the current drop; the fixture proves the handling.

### Reproduce
1. Prerequisites in `docs/superpowers/plans/2026-09-26-data-pipeline.md` (Snowflake trial, key pairs, bucket, `.env`).
2. `uv sync && uv run python -m pipeline.setup 00_account.sql 01_integrations.sql 02_raw_tables.sql`
3. `uv run python -m pipeline.load --run-id initial && (cd dbt && uv run dbt build) && uv run python -m pipeline.export --run-id initial`
4. `uv run pytest -m "not snowflake"`; `uv run pytest -m snowflake` with `.env` loaded.
```

- [ ] **Step 2: Verify every command in "Reproduce" runs as written, then commit**

```bash
git add README.md
git commit -m "docs: data pipeline contracts, freshness, lineage, fixture and limitations"
git push
```

---

## Self-review notes

- Spec §4 orchestration → Task 10. §4.1 migration path → README/spec only (documented, not built, as the spec says).
- §5.1 RAW → Tasks 2 and 4. §5.2 staging, dedup, quarantine, tests, freshness → Tasks 5 and 6. §5.3 curated and contracts, seed, DQ results, manifest → Task 7 (manifest written by Task 4). §5.4 export and pointer → Task 8.
- §6 failure handling: abort-on-error and retries in Task 4; export-after-green and atomic pointer in Task 8 and Task 10's job dependencies; quarantine gate in Task 6; schema evolution in Tasks 2 and 5.
- §7 access → Tasks 2 and 10 (with the dbt WIF verification step). §8 fixture → Task 9. §9 definition of done → Tasks 10 and 11.
- Names used across tasks: `run_load`, `run_export`, `parse_dbt_results`, `write`, `build_connect_kwargs`, `get_connection`, `RAW.ORGANIZER_STAGE`, `RAW.SERVING_STAGE`, `RAW.FIXTURE_STAGE`, `META.RUN_MANIFEST`, `META.DQ_RESULTS`, `STAGING.QUARANTINE` are spelled the same everywhere.
- Review Focus items 1 to 5 are pinned in Tasks 4/9, 6, 6, 8/9 and 8 respectively.
