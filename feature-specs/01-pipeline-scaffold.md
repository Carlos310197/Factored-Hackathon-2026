# 01 · Pipeline Scaffold and Snowflake Connection

**Subsystem:** Data pipeline · **Depends on:** none · **Reference:** pipeline plan, Task 1

## Goal

Set up the pipeline's Python project and the one helper every step uses to connect to Snowflake, with GitHub OIDC or key-pair auth.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Data Pipeline
- `context/architecture-context.md` → Data Pipeline; Storage Model and Contracts → Serving contract
- `context/architecture-context.md` → Access Controls and Secrets → Access and secrets · pipeline §7

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Prerequisites (manual, one time, before unit 02)

*From the pipeline plan (owner actions; the agent only checks they're done):*

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

## Implementation

### Files

- Create: `pyproject.toml`, `.gitignore`, `pipeline/__init__.py`, `pipeline/connect.py`, `tests/__init__.py`, `tests/test_connect.py`

### Interfaces

- Produces: `pipeline.connect.build_connect_kwargs(env: Mapping[str, str]) -> dict` and `pipeline.connect.get_connection(database: str | None = None)` returning a `snowflake.connector` connection. Env keys: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, and one of `SNOWFLAKE_OIDC_TOKEN` (GitHub) or `SNOWFLAKE_PRIVATE_KEY_PATH`.

## Scope Limits

- Project files and `pipeline/connect.py` only. No SQL objects and no loader.
- Don't run `git init` again: the folder already tracks the team repo.
- No credentials in code or tests; tests build kwargs from a fake environment.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_oidc_token_wins`, `test_key_pair_when_no_token`, `test_common_fields_and_database_override`, `test_missing_auth_raises`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-26-data-pipeline.md`: Task 1 (Repository scaffold and Snowflake connection helper), lines 63–194
