# Progress Tracker

Update this file whenever the current phase, the active unit or the implementation state changes. Record what is actually implemented.

## Current Phase

- **Data pipeline built (units 01–11)**, **Terraform infrastructure deployed** (state, OIDC, serving bucket, Snowflake objects, ECS web hosting shell), **Agent core units 12–24 complete** (scaffold, Jev client, identity tokens, dispute policy, serving reader and read tools, DynamoDB store, write tools and handoff packet, Jev question sets/thresholds/routing, OpenAI on Bedrock, LangGraph workflow and agent service, AgentCore runtime entrypoint, local serving builder and demo identities, container image + local compose stack + terminal chat) and **Transaction resolver units 26–28 complete** (features and splits, history sampler, simulator). Agent core continues with unit 25, the resolver with units 29–39. Evaluation, UI and the remaining Terraform roots (`data`, `identity`, `agent`, `realtime`, `ops`) are not started: there is no `eval/` or `web/` code yet.
- Region: **us-east-1** for all our AWS resources and Snowflake. The organizer bucket (theirs) stays in us-east-2.
- Offline suite: `uv run pytest -m "not snowflake"` → 43 passed, 6 deselected (2026-10-05). Agent suite: `cd agent && uv run pytest` → 191 passed (2026-10-05). Container contract: `cd agent && uv run pytest -m container` → 4 passed against `docker compose up` (2026-10-05).
- Submission deadline: **2026-10-05**.

## Current Goal

- Continue the transaction resolver at `feature-specs/29-resolver-agent-hooks.md` (Agent-Core Changes I: extract hints, dev writer, `understand.v2`); `31-resolver-model.md` needs only `26` and can run in parallel. Agent core `25` and the as-is diagnosis (`40`) can also run in parallel. The UI (53+) and deployment (77+) follow the agent core.

## Completed

- 2026-09-26 → 2026-10-01: design specs and implementation plans for all six subsystems, plus the infra-as-code design and plan (`docs/design/2026-10-01-infra-iac-design.md`, `docs/reference/plans/2026-10-01-infra-iac.md`).
- 2026-10-01: docs reorganized into `context/` + `feature-specs/`; specs archived in `docs/design/`, plans in `docs/reference/plans/`. `analysis/` (profiling scripts) moved out of git (gitignored).
- 2026-10-01: **Terraform infrastructure** (`infra/terraform/`, applied by `.github/workflows/infra.yml`; see `architecture-context.md` → Deployed Infrastructure):
  - `bootstrap/`: state bucket `fh26-tfstate-762197749808-use1`, GitHub OIDC provider, role `gha-deploy`, Snowflake user `TF_DEPLOY` (AWS workload identity), organizer keys in SSM. Applied once from a laptop; state migrated to S3.
  - `platform/`: serving bucket `latam-bank-serving-762197749808-use1` (TLS-only, private), warehouse, role, databases and schemas, storage integration `SI_SERVING` + AWS role `snowflake-serving`, file format, stages, role `pipeline-runner` + Snowflake user `PIPELINE_SVC`. A Snowflake login and stage-listing smoke test (`tests/test_infra_smoke.py`) runs after each apply.
  - `app/`: ECR repo `latam-bank-web`, ECS cluster `latam-bank` on Fargate Spot, service `latam-bank-web` running a Node placeholder on port 3000 (public IP, team-IP allowlist, no ALB); `bin/app-url` prints its URL.
  - Moved from us-east-2 to us-east-1 the same day (state bucket, serving bucket, workflows).
- 2026-10-01: **Data pipeline, units 01–11:**
  - 01 scaffold (`pyproject.toml`, `pipeline/connect.py` with workload identity → snow CLI connection → key pair);
  - 02 RAW and META tables (`infra/snowflake/02_raw_tables.sql`, `pipeline/setup.py`); the other Snowflake objects are Terraform;
  - 03–04 loader with ETag manifest and batched `COPY` (`pipeline/load.py`);
  - 05–07 dbt sources with freshness, staging with typing, dedup and quarantine, curated marts with enforced contracts, `dq_results` (`pipeline/dq_results.py`);
  - 08 parquet export with the atomic `latest.json` pointer (`pipeline/export.py`);
  - 09 fixture drop end-to-end proof (`fixtures/make_fixture.py`, `tests/test_fixture_drop.py`);
  - 10 workflows: `ci.yml` (offline checks) and `pipeline.yml` (daily 06:00 UTC + push to `main`: load → dbt build → export);
  - 11 pipeline README (`README.md` → Data pipeline).
  - Live state (checked 2026-10-04 with `gh run list --workflow pipeline.yml`): the last five runs all succeeded: two pushes on 2026-10-01 (including the us-east-1 move) and the daily schedule since then, the latest about 10 hours before the check (run `37199535018`, 1m44s). Load → `dbt build` → export works live, and `serving/latest.json` is refreshed daily.
- 2026-10-04: specs and context updated to the deployed reality: region us-east-1, web on ECS Fargate Spot, Terraform-owned serving bucket (see Architecture Decisions, 2026-10-04). CLAUDE.md gained Repo Rules (no Claude attribution in commits or PRs; tests first for every feature).
- 2026-10-04: **everything is Terraform.** Deployment units 77, 81–90 and UI units 53, 59, 60 rewritten from CDK to Terraform roots (Architecture Decisions, 2026-10-04 #7).
- 2026-10-04: Carlos's IP `38.25.85.60/32` added to `allowed_cidrs` in `infra/terraform/app/main.tf` (test updated first; `terraform test` 3/3 passed). Live after `infra.yml` applies it on `main`.
- 2026-10-04: **Unit 12: Agent core scaffold** (`agent/`):
  - `agent/pyproject.toml` with pinned dependencies (anthropic[bedrock]>=1.9, bedrock-agentcore>=1.24, langgraph>=1.2, langgraph-checkpoint-aws>=1.2, pyjwt[crypto]>=2.9, etc.);
  - `agent/src/bankagent/__init__.py`, `settings.py`, `context.py`, `ids.py`: Settings from env, SessionContext with scope checks, time-sortable IDs;
  - `agent/tests/test_scaffold.py`: 4 tests (settings defaults, serving URI required, scope enforcement, ID prefix and uniqueness);
  - Verified pinned library APIs import (AnthropicBedrockMantle, BedrockAgentCoreApp, RequestContext, PingStatus, DynamoDBSaver, interrupt, Command, InMemorySaver);
  - Default region is us-east-1 (per Architecture Decision 2026-10-04 #1);
  - All tests pass: 4/4 in agent/, 43/43 in root offline suite.
- 2026-10-04: **Unit 13: Jev Client** (`agent/src/bankagent/decisions/`):
  - `agent/src/bankagent/decisions/jev.py`: `JevClient` with strict validation, typed answers (`ChoiceAnswer`, `NoulAnswer`), one retry on 5xx/timeout, state hashing;
  - `agent/tests/test_jev.py`: 9 tests covering typed answer parsing, validation errors (missing/invalid choice/noul), retry behavior (5xx, 4xx, timeout), and empty key rejection;
  - `agent/scripts/smoke_jev.py`: Live smoke test script with synthetic data (requires owner approval);
  - `agent/docs/smoke-results.md`: Placeholder for live smoke results;
  - All tests pass: 13/13 in agent/, 43/43 in root offline suite.
  - Live smoke test ran successfully (583ms latency, correct intent/transaction classification).
- 2026-10-04: **Unit 14: Identity Tokens** (`agent/src/bankagent/auth/`, `agent/src/bankagent/identity/`):
  - RS256 JWT token generation and verification (`auth/tokens.py`):
    - `generate_keypair()`, `jwks_from_public()`, `issue_token()`, `verify_token()`
    - `JwksCache` for caching IdP JWKS with TTL
    - `AuthError` exception for authentication failures
  - Mock OIDC identity service (`identity/app.py`, `identity/users.py`):
    - `DemoUser` model and `load_users()` for YAML-based user configuration
    - FastAPI app with routes: `POST /auth/login`, `POST /auth/otp`, `GET /.well-known/openid-configuration`, `GET /jwks.json`
    - Login → OTP → token flow with single-use tickets
    - Session IDs prefixed with "S-", 15-minute TTL, scopes from config
  - 11 comprehensive tests covering full login flow, token verification, error cases (wrong password/OTP, expired/tampered tokens, wrong audience/issuer/unknown kid)
  - All tests pass: 24/24 in agent/, 43/43 in root offline suite
- 2026-10-04: **Unit 15: Dispute Policy** (`agent/src/bankagent/policy/`):
  - `dispute_policy.yaml`: labeled synthetic policy (v1) with rules for status, type, window, duplicates, reasons, and human review triggers;
  - `dispute.py`: pure evaluation function returning `PolicyResult` with pass/fail per rule; handles USD amount fallback, fraud score thresholds (>30), escalation signals;
  - 20 tests covering happy path, status redirects, non-disputable types, window boundaries, duplicates, human review triggers (unauthorized, fraud, amount), edge cases (fraud_score=30, amount=500), USD handling, and error cases;
  - All tests pass: 44/44 in agent/, 43/43 in root offline suite.
- 2026-10-04: **Unit 16: Serving Reader and Read Tools** (`agent/src/bankagent/data/`, `agent/src/bankagent/tools/`):
  - `data/contract.py`: serving contract with column order per table (dim_customer, dim_product, fct_transaction, fct_complaint, seed_decline_reason);
  - `data/serving.py`: `ServingData` class with DuckDB-based queries over parquet, `Pointer` for run metadata, JSON-safe type conversion (Decimal→float, date→ISO);
  - `tools/read.py`: Customer-scoped read tools (`get_accounts`, `list_transactions`, `get_transaction`, `explain_decline`, `list_complaints`) with scope enforcement and `ToolResult` receipts;
  - `tests/fixtures/serving_fixture.py`: labeled synthetic test data matching serving contract exactly (2 customers, 2 products, 10 transactions, 1 complaint, 5 decline reasons);
  - 13 tests covering pointer reading, contract validation, JSON-safe values, SQL injection prevention, customer scoping, transaction ordering, decline explanations, and scope enforcement;
  - All tests pass: 57/57 in agent/, 43/43 in root offline suite.
- 2026-10-04: **Unit 17: DynamoDB Tables and Repositories** (`agent/src/bankagent/store/`):
  - `store/codec.py`: DynamoDB codec with Decimal/float conversion and null dropping;
  - `store/tables.py`: table definitions for 4 tables (checkpoints, disputes, handoffs, decision_records) with idempotent creation;
  - `store/repos.py`: DisputeRepo, HandoffRepo, DecisionLog with conditional puts, consistent reads, GSI queries, 90-day TTL;
  - `scripts/create_tables.py`: idempotent table creation script;
  - `docker-compose.yml`: DynamoDB Local for testing;
  - 6 tests covering table creation, conditional puts, GSI queries, TTL, and codec roundtrip;
  - All tests pass: 63/63 in agent/, 43/43 in root offline suite.
- 2026-10-04: **Unit 19: Jev Question Sets, Thresholds, and Routing** (`agent/src/bankagent/decisions/`):
  - `questions.py`: Load versioned question sets from YAML (understand.v1, verify_reply.v1);
  - `thresholds.py`: Load versioned thresholds from YAML with intent, target, handoff, injection, and confirmation thresholds;
  - `understand.py`: Build understand requests with candidate transaction aliases (c1..cN), parse Jev responses into Understanding dataclass;
  - `verify.py`: Build verify_reply requests for claim validation, parse Jev responses into VerifyOutcome;
  - `routing.py`: Code routing function that applies thresholds to Jev answers, handles escalation (unauthorized/legal/human), injection attempts, confirmation flows, and clarification limits;
  - `questions/understand.v1.yaml`: Question set for intent classification, target transaction, dispute reason, and escalation nouls;
  - `questions/verify_reply.v1.yaml`: Question set for claim verification and promise validation;
  - `thresholds.v1.yaml`: Labeled synthetic thresholds (not calibrated; tuned in spec 2);
  - 27 new tests in test_decisions.py and test_routing.py covering request building, alias security, candidate selection, parsing, routing logic, escalation, and edge cases;
  - All tests pass: 111/111 in agent/ (84 existing + 27 new).
- 2026-10-04: **Unit 20: OpenAI on Bedrock** (`agent/src/bankagent/llm/`):
  - `llm/models.yaml`: per-role model configuration (extract: Haiku 4.5 `anthropic.claude-haiku-4-5-20251001-v1:0`, compose: Sonnet 5.5 with effort=low);
  - `llm/config.py`: `RoleConfig` dataclass and `load_models()` with environment variable overrides (LLM_EXTRACT_MODEL, LLM_COMPOSE_MODEL);
  - `llm/client.py`: `call_json()` for structured JSON output with prompt caching (ephemeral_cache_control), timeout handling, and error mapping (LLMError, LLMRefusal);
  - `llm/extract.py`: `extract()` function with extraction schema (language_detected, english_gloss, multi_intent, mentions, customer_statement), untrusted message wrapping in `<customer_message>` tags;
  - `llm/compose.py`: `compose()` function with compose schema (reply_text, claims) and feedback loop support, `open_questions()` for handoff packet generation;
  - `llm/templates.py`: ES/PT template functions for fixed reply blocks (confirmation_summary, handoff_notice, dispute_filed, auth_message, fallback_reply), money formatting (fmt_money with COP no-decimals rule), intent/reason labels;
  - `tests/fakes.py`: `FakeLLM` test double with configurable language, multi_intent, mentions, refusal, and failure modes;
  - `scripts/smoke_bedrock.py`: Live smoke test script for Bedrock API (requires owner approval);
  - 14 new tests in test_llm.py and test_templates.py covering model config, extract/compose request shapes, error handling (refusal, connection errors, invalid JSON, truncation), template rendering (ES/PT), money formatting, and fallback logic;
  - All tests pass: 125/125 in agent/ (111 existing + 14 new), 43/43 in root offline suite.
- 2026-10-05: **Unit 21: LangGraph Workflow and Agent Service** (`agent/src/bankagent/graph/`, `agent/src/bankagent/service.py`):
  - `graph/__init__.py`: graph module marker
  - `graph/state.py`: `AgentState` dataclass extending `MessagesState` with all workflow state fields (turn_id, message, language, run_id, as_of, candidates, allowed_ids, extraction, route, counters, reasons, decisions, goal, awaiting, clarification, pending, intent, target_txn_id, dispute_reason, escalated, txn, statement, confirmation_summary, policy_checks, filed, receipts, actions, queue, queued_offer, recent, reply)
  - `graph/deps.py`: `Deps` dataclass injecting all dependencies (read/write tools, store, policy, jev, llm_client, models, thresholds, question sets, gloss_mode, clock)
  - `graph/nodes.py`: `Nodes` class with 12 node implementations (load_context, understand, answer_inquiry, resolve_transaction, check_eligibility, confirm, file_dispute, verify, clarify, handoff, reply, await_customer), each implementing one step of the workflow with error handling and decision logging
  - `graph/build.py`: `build_graph()` function wiring nodes into `StateGraph` with conditional edges based on `state["route"]["next"]`, interrupt for multi-turn confirmation/clarification
  - `service.py`: `AgentService` class wrapping compiled graph with `handle_turn()` and `state()` methods, turn budget enforcement, recursion limit, error recovery with fallback template
  - `tests/fakes.py`: added `FakeJev` test double with scripted understand/verify responses, choice/noul answer builders
  - `tests/harness.py`: test harness with `make_harness()` factory, `Harness` dataclass, pre-defined session contexts (CTX_ES, CTX_ES2, CTX_PT, CTX_READ_ONLY)
  - `tests/test_graph_paths.py`: 12 scenario tests covering main conversation paths (account inquiry ES/PT, decline explanation, dispute flow with confirmation, ambiguous intent clarification, unsupported request, unrecognized charge handoff, over-limit human review, legal threat, declined payment dispute, multi-intent queue, unsupported language, run_id persistence)
  - `tests/test_graph_failures.py`: 15 failure scenario tests (Jev down once/twice, Jev down during confirmation, unclear confirmation 3x, modify during confirmation, duplicate dispute, injection refused then handed off, compose failure, unverified claims, verify outage, foreign ID blocked, serving unavailable, missing dispute scope, turn budget exhausted, extract failure, recursion limit)
  - All 27 new tests pass; total 151/151 in agent/ (124 existing + 27 new), 43/43 in root offline suite
- 2026-10-05: **Unit 22: AgentCore Runtime Entrypoint** (`agent/src/bankagent/`):
  - `runtime.py`: Production wiring with DynamoDBSaver checkpointer (30-day TTL), real Jev client, Claude on Bedrock, DuckDB over serving set, and DynamoDB store;
  - `app.py`: AgentCore entrypoint with `/ping` and `/invocations` endpoints on port 8080, JWT re-verification (defence in depth), Bearer token support (Authorization header or session_token payload fallback), message validation (max 2000 chars), customer_id from JWT only (never from payload), graceful identity outage handling;
  - `handle()` function: pure, testable request processing with error codes (auth_required, session_expired, invalid_message, identity_unavailable);
  - 13 comprehensive tests covering token validation, message rejection, payload security, HTTP contract, and runtime wiring;
  - All tests pass: 178/178 in agent/ (165 existing + 13 new), 43/43 in root offline suite.
- 2026-10-05: **Unit 26: Resolver Features and Splits** (`agent/src/bankagent/resolver/`):
  - Added `numpy>=2.0` and `rapidfuzz>=3.9` as runtime dependencies;
  - Added `resolver` dependency group: `scikit-learn>=1.5`, `lightgbm>=4.5`, `mlflow>=3.1`, `matplotlib>=3.9` (offline training/evaluation only, excluded from runtime image via `--no-default-groups`);
  - `resolver/features.py`: Pure feature function with 13 features (merchant_mentioned, merchant_sim, merchant_missing_on_cand, amount_mentioned, amount_log_err, amount_rank, date_mentioned, days_outside, type_match, channel_match, city_match, recency_pct, is_purchase); `fold()` for accent-insensitive text normalization; `mentions_present()` to detect if customer mentioned anything;
  - `resolver/splits.py`: Leakage-safe customer split using SHA256 hash (first byte mod 10 → 0-7 train, 8 dev, 9 test); anchor date ranges (train: 2023-09-01 to 2025-09-30, dev: 2025-10-01 to 2026-01-31, test: 2026-02-01 to 2026-06-17); hard-slice rule for deterministic case classification (easy/hard/nil);
  - `tests/resolver_data.py`: Synthetic transaction and mentions helpers for testing;
  - 14 comprehensive tests covering: accent-insensitive merchant matching, amount error calculation with local vs USD fallback, date range handling (including reversed ranges), hint matching (type/channel/city with case/whitespace tolerance), degenerate amounts (0, negative, boolean, string), customer split determinism and distribution, anchor date non-overlap, hard-slice rules;
  - All tests pass: 138/138 in agent/ (124 existing + 14 new);
  - Followed TDD: tests written first, all initially failing with ModuleNotFoundError, then implementation added to make them pass.
- 2026-10-05: **Unit 27: Resolver History Sampler** (`agent/src/bankagent/resolver/histories.py`):
  - `resolver/histories.py`: Deterministic history sampler that pulls customer 60-day candidate windows from a pinned serving run; `History(split, customer_id, anchor, candidates)` dataclass; `TransactionSource(serving_dir)` wraps a serving directory with `.run_id`, `.customers(split)` (filtered by `customer_split`) and `.windows(pairs)` (DuckDB join over fct_transaction, TXN_FIELDS only, newest-first order matching `ReadTools.list_transactions`); `sample_histories(source, split, n, seed, min_candidates=2)` returns n histories with at least 2 candidates in the window, deterministic for a given seed (random seeded with `f"{seed}:{split}"`, distinct (customer, anchor) pairs, up to 10 batches);
  - `tests/fixtures/resolver_serving.py`: Labeled synthetic fixture with `RUN_ID = "resolver-fixture-1"`, 200 customers `CLI-HIST%08d` from 2023-07-01 to 2026-06-17 (~one txn every 9 days per customer), six merchants, weighted transaction types, multiple currencies (USD/COP/ARS);
  - `tests/conftest.py`: appends the `history_serving` session-scoped fixture;
  - 2 tests: `test_histories_respect_split_window_and_order` (verifies split membership, anchor within split range, candidates newest-first, 60-day inclusive window, scope and field shape); `test_histories_are_deterministic_and_splits_disjoint` (verifies determinism, disjoint customer sets across splits, and JSON-safe amount types);
  - All tests pass: 140/140 in agent/ (138 existing + 2 new);
  - Followed TDD: tests written first, all initially failing with `ModuleNotFoundError`, then implementation added to make them pass.
- 2026-10-05: **Unit 28: Resolver Simulator** (`agent/src/bankagent/resolver/simulate.py`, `simulate.yaml`):
  - `resolver/simulate.yaml`: `simulate.v1` style rates, documented as **assumptions** (not measurements; real-text dev/test reveal any mismatch): hard_share 0.50, not_in_list 0.10, no_detail 0.05, extract_error 0.05, merchant (purchases) exact 0.40 / noisy 0.20 / absent 0.40, amount exact 0.30 / rounded 0.30 / approx 0.15 / usd 0.05 / absent 0.20 (`amount_approx_pct` 0.10), `currency_mentioned` 0.50, date exact 0.20 / relative 0.35 / off_by_one 0.10 / absent 0.35, hints type 0.60 / channel 0.40 / city 0.40 with `hint_wrong` 0.03;
  - `resolver/simulate.py`: deterministic case generator over `History` lists: `load_sim_config(path=DEFAULT_CONFIG)` (sha256 of the YAML, `ValueError` when a distribution doesn't sum to 1), `simulate(histories, cfg, seed)` → one case per history `{case_id, split, anchor, slice, target_id | None, target, candidates, mentions, style}` with `mentions` exactly `MENTION_KEYS` and `style` per-field plus `no_detail`, `extract_error`, `nil`, `date_label`; stratified target draw (≈50% hard), `not_in_list` drops the target (labels 0), `no_detail` empties all mentions, `extract_error` swaps one mentioned field with another candidate's value; helpers `relative_ranges(anchor)`, `relative_range(d, anchor)` (this/last week, this/last month, tightest first) and `round_significant(a)` (two significant figures);
  - `tests/test_resolver_simulate.py`: 7 tests pinning the review focus (config hash + validation, same-seed determinism, nil excludes the target, style rates within ±2 points over 10k draws, hard oversampling ≈50%, rounding + relative ranges, relative dates carry their label);
  - All tests pass: 187/187 in agent/ (180 existing + 7 new);
  - Followed TDD: tests written first, all initially failing with `ModuleNotFoundError`, then implementation added to make them pass.
- 2026-10-05: **Unit 24: Container Image, Local Stack and Terminal Chat** (`agent/`):
  - `Dockerfile` + `.dockerignore`: ARM64 image (`ghcr.io/astral-sh/uv:python3.12-bookworm-slim`) whose default command serves `/ping` + `/invocations` on 8080 (`python -m bankagent.app`); the same image runs the mock IdP on 8081 (`python -m bankagent.identity.app`). Synced with `uv sync --frozen --no-default-groups` (no dev/resolver tooling in the runtime image, per code-standards); DuckDB `httpfs`/`aws` extensions installed at build time;
  - `docker-compose.yml` (replaces the Task 6 version): `dynamodb` (DynamoDB Local), `init-tables` (`scripts/create_tables.py`), `identity` and `agent`. Region us-east-1 (Architecture Decisions 2026-10-04 #1 overrides the plan's us-east-2), `JEV_API_KEY` required from the shell (never committed), serving mounted read-only at `/serving`, `~/.aws` mounted read-only **except** `~/.aws/sso/cache` (botocore writes its refreshed SSO token there — the plan's fully read-only mount made every `/invocations` fail at runtime build);
  - `scripts/chat.py`: terminal client — login → OTP through the IdP, then chat with `/invocations`; `/quit`/`/exit` to end;
  - `tests/test_container_contract.py` (marker `container`, no model calls): the four pinned tests `test_ping_is_healthy`, `test_invocation_without_token_asks_to_log_in`, `test_identity_publishes_discovery_and_jwks`, `test_valid_token_with_empty_message_is_rejected_before_any_model_call`;
  - **Bug fix in unit 14 (with a test):** `bankagent/identity/app.py`'s module entrypoint loaded **no** users and required the agent's `SERVING_URI`, so `python -m bankagent.identity.app` could not serve the demo identities the stack mounts. It now builds from `DEMO_USERS` + `IDP_ISSUER`/`IDP_AUDIENCE`/`IDP_KID` (`create_app_from_env`), pinned by `test_module_entrypoint_serves_demo_users_and_settings_from_env` in `tests/test_identity.py`;
  - Verified: `docker compose build && docker compose up -d` brings the four services up (the four DynamoDB tables created), `uv run pytest -m container` → 4 passed against it, `uv run pytest` → 191 passed, and the chat client logs in as `demo01` and exits cleanly;
  - All tests pass: 191/191 offline in agent/ (190 at branch point + 1 bug-fix test), 4/4 container against the stack.

## In Progress

- None.

## Next Up

Unit ranges, in build order (see `feature-specs/README.md` for the full list and dependencies):

| Units | Subsystem | Status | First dependency |
| --- | --- | --- | --- |
| 01–11 | Data pipeline | **done**, running daily and green | none |
| 12–25 | Agent core | 12–24 **done**; 25 next | none (16 uses a synthetic fixture; 23 uses the local drop) |
| 26–39 | Transaction resolver | 26–28 **done** (features, splits, history sampler, simulator); 29 next | 12, 16 |
| 40–52 | Evaluation (40–42, the as-is diagnosis, have no dependencies) | not started | 43+ need agent core 12–24 |
| 53–76 | UI | not started | agent core 12–22 |
| 77–90 | Deployment | not started; Terraform `bootstrap`, `platform` and the `app` web shell already exist | 77 has none; the rest follow the agent core and UI |

## Open Questions

### Raised 2026-10-04

- ~~CDK or Terraform for the remaining stacks?~~ **Resolved 2026-10-04: everything is Terraform** (Architecture Decisions, 2026-10-04 #7).
- **Web image pattern** (SSM `/fh26/<name>/image` owned by the root, overwritten by the deploy workflow): Carlos is confirming it with Andrés.
- **Terraform provider coverage** for the AgentCore runtime, AppSync Events and Transaction Search: checked in unit 77, with the `awscc` or AWS CLI fallbacks chosen in advance (units 83, 84, 88).
- **Web access:** `allowed_cidrs` now holds Andrés's and Carlos's IPs (home IPs can change: re-run `curl checkip.amazonaws.com`). The demo-day change (ALB + HTTPS, switch to on-demand `FARGATE`) needs the owner's approval.
- **`gha-deploy` has `AdministratorAccess`** and trusts pull requests too. Unit 88 adds the read-only `gha-plan` role and narrows `gha-deploy` to `main`, before the repo goes public.
- **Repo:** `Carlos310197/Factored-Hackathon-2026` is private; make it public (and rename to `factored-hackathon-2026-<team>` if required) before submission.

### From the data pipeline spec

#### Open items · pipeline §10

- Confirm in Slack `#technical-help` that dataset records may be loaded into Snowflake (third party) and sent to an external LLM. Synthetic data, but the brief says to follow the published data-use terms.
- Carlos to confirm the workflow and the Snowflake choice.
- ~~Create the Snowflake trial, our S3 bucket, and the public GitHub repo.~~ **Resolved 2026-10-01:** Snowflake account `RLQHFPF-AXC97788` (AWS us-east-1), serving bucket `latam-bank-serving-762197749808-use1` (Terraform), repo `Carlos310197/Factored-Hackathon-2026` (private until submission).
- ~~Who owns the Snowflake account and the AWS account.~~ **Resolved:** the team created both; AWS account `762197749808` (SSO profile `hackathon-sso`).

### From the agent-core spec

#### Open items and risks · agent-core §12

- **Data-use approval:** confirm with the organizers (Slack `#technical-help`) that dataset records may be sent to Amazon Bedrock and to TypeSafe (Jev). This extends the pipeline spec's open item.
- **Jev route:** TypeSafe's direct route is mock-tested only upstream, and the Decisions endpoint is alpha → live smoke test on day 1; pin `jev-1.13.0`.
- **Jev language quality:** Spanish and Portuguese accuracy is unknown (English is its strongest) → measured in spec 2, with the gloss setting as the lever.
- **AgentCore:** confirm whether the bearer token reaches the container, availability in us-east-1, and cold-start latency.
- **Bedrock:** exact model IDs and availability of Haiku 4.5 and Sonnet 5.5 in us-east-1; structured-output support on each.
- **Pipeline:** the export sort-order change (§9.3).
- **Schedule:** submissions close 2026-10-05, so specs 2 and 3 must be written in parallel with this implementation.

### From the UI spec

#### Open items and risks · ui §14

- ~~**Amplify SSR:** the compute role and request timeout are unverified.~~ **Not applicable (2026-10-04):** the web runs on ECS Fargate Spot. The 202 + push fallback stays available.
- **AppSync Events:** availability in us-east-1, and the `onSubscribe` handler's access to authorizer claims. Checked in plan task 1. If the handler can't see the claims, the Lambda authorizer enforces the channel path instead.
- **Identity service reachability:** AgentCore's authorizer and our AppSync Lambda authorizer both need its JWKS over HTTPS. Hosting it is a dependency of the deployment work.
- **Agent-core schedule:** §4 adds tables, a gate and contract fields to a plan that's already being implemented. They must land before the UI's integration tasks.
- **Scenario data:** each scenario needs a demo identity whose real data triggers it (for example a transaction with `fraud_score` > 30, or a duplicate-looking pair). The selection script might not find all of them in the 60-day window; any gap is reported, never fabricated.
- **Jev alpha endpoint:** a live demo depends on it. There's no silent fallback (agent-core §4.4); a failed turn shows as a failure in the trace.
- **Submission deadline** 2026-10-05.

### From the deployment spec

#### Open items and risks · deployment §12

Each is checked in plan task 1, with the fallback chosen in advance.

| Item | Fallback |
|---|---|
| *(updated 2026-10-04)* `hashicorp/aws` support for `aws_bedrockagentcore_agent_runtime` (+ endpoint) with a JWT authorizer and header allowlist | `awscc_bedrockagentcore_runtime`; last resort `terraform_data` + AWS CLI |
| Whether a JWT-authorized runtime also accepts SigV4 calls | Bearer-only invocation from the BFF (§4.1) — settled by deployment plan #1 |
| *(updated 2026-10-04)* `aws_appsync_api` (Event API) and `aws_appsync_channel_namespace` with `code_handlers` in `hashicorp/aws` | the `awscc` equivalents |
| AppSync Events in us-east-1 | Already flagged in UI plan task 1 |
| ~~Amplify SSR timeout~~ | Not applicable: ECS Fargate Spot (2026-10-04) |
| ~~Amplify needs a GitHub token~~ | Not applicable: the web image is built in CI and pushed to ECR (2026-10-04) |
| Fargate Spot interruption during the demo | Switch the service to on-demand `FARGATE` for demo day (with the ALB) |
| Schedule: application code still unwritten, one day to the deadline | Deploy the agent and web as soon as they exist; the infrastructure they need for state, data and hosting is already up |

## Schedule and Risks

### Resolver

**Schedule** (submission 2026-10-05):

| Day | Work | Depends on |
|---|---|---|
| 09-30 | `features.py`, `splits.py`, `simulate.py`; `make_test_sheet.py` → **sheet sent to Andrés** | local drop |
| 10-01 | training, MLflow, `model.py` | — |
| 10-02 | dev set, calibration, thresholds | agent-core Task 9 with the hints; data-use approval |
| 10-03 | agent integration (`understand.v2`); **test set due from Andrés**; freeze | agent-core Tasks 8 and 10 |
| 10-04 | single test run, report, error analysis, human ceiling | Jev live |

**Risks:**
- **Andrés's time** (about 3–4 hours for 150 messages). Fallback: 100 messages, with the n disclosed.
- **Jev unavailable on 10-04.** B0 vs B1 is still a valid learned-vs-baseline result; B2 and P are reported as not run.
- **The `extract` hints miss Task 9.** The dev set cannot be built until they land.
- **Simulator mismatch.** The dev and test sets are real text, so a mismatch shows up as a gap between the simulated-validation and dev metrics. It is reported, not hidden.
- **Portuguese.** PT messages describe the histories of Spanish-speaking customers. This is reported as a data limitation.

### Evaluation

#### Schedule and risks · evaluation §11

| Date | Work | Depends on |
|---|---|---|
| 10-01 | as-is runner, report and charts | local drop |
| 10-02 | goal generator, persona, harness, classifier; dev-goal iteration | agent-core `handle_turn()` |
| 10-03 | freeze; held-out run ×3; judge validation | Jev and Bedrock live |
| 10-04 | eval report, charts, deck numbers | — |

**Risks:**
- **Agent-core not ready by 10-02.** The as-is report and the harness still ship; the held-out run moves to the morning of 10-04.
- **Data use.** Goal cards send transaction fields to the OpenCode persona provider, in addition to Bedrock and TypeSafe. This extends the open data-use item (agent-core §12) to the persona provider.
- **Persona realism.** A simulated customer is not a real one; the report states it, and the discard count shows how often it went off-script.
- **Small n.** 120 goals give wide intervals on rare classes; zero unsafe outcomes observed does not establish zero risk, and the report says so.
- **Jev alpha endpoint** on run day (§7).

## Architecture Decisions

Decisions that change or settle the copied spec text. **They take precedence over the spec text in `context/` and `feature-specs/`.** Numbering follows each plan, so feature specs cite them as "agent-core plan #2", "UI plan #1", and so on.

### 2026-10-01: Documentation structure

- `context/` plus numbered `feature-specs/` are the working specs. The UI spec's decision "Process: No `context/` or feature-spec files" is superseded.
- `docs/design/` (specs) and `docs/reference/plans/` (plans) are frozen. Plans are reference implementations, read by line range only.
- Plan steps that wrote results into a plan or a spec now write them here.

### 2026-10-04: Deployed infrastructure (region, web hosting, Terraform)

These record what Andrés deployed on 2026-10-01 (`docs/design/2026-10-01-infra-iac-design.md`, `infra/terraform/`) and override the copied spec text everywhere.

1. **Region us-east-1** for every AWS resource of ours (state and serving buckets, ECS, ECR, and later DynamoDB, AgentCore, Bedrock, AppSync, the identity API) and for Snowflake. Only the organizer bucket stays in us-east-2, so only the daily load crosses regions. Every "us-east-2" in the copied spec text means us-east-1.
2. **The web runs on ECS Fargate Spot, not Amplify Hosting.** Terraform `infra/terraform/app` owns the ECR repo `latam-bank-web`, cluster `latam-bank` (`FARGATE_SPOT` default), service `latam-bank-web` (one 0.5 vCPU / 1 GB X86_64 task on port 3000, circuit breaker with rollback), task role `latam-bank-web-task` and execution role.
   - No ALB for now: the task has a public IP, the security group admits only `allowed_cidrs`, and `bin/app-url` prints the URL. Demo day adds an ALB with HTTPS and switches to on-demand `FARGATE`.
   - Consequences: no Amplify app, compute role, `amplify.yml`, GitHub token or SSR timeout check. The BFF's AWS access is the ECS task role. The web image is built in CI and tagged with the git SHA; the running tag is kept in SSM `/fh26/web/image` (owned by `app`, value ignored by Terraform), so no apply can roll the image back. `app` moves from `infra.yml`'s apply to `deploy.yml` (unit 89).
   - Units changed: 53, 76, 77, 85 (rewritten), 86, 88, 89; `code-standards.md` → Deployment; `architecture-context.md`.
3. **Infrastructure tooling:** Terraform, applied by GitHub Actions (see #7).
4. **Accounts and repo exist:** AWS `762197749808` (SSO profile `hackathon-sso`), Snowflake `RLQHFPF-AXC97788`, repo `Carlos310197/Factored-Hackathon-2026`.
5. **Auth to Snowflake is AWS workload identity**, not GitHub OIDC directly: GitHub → `pipeline-runner` → `PIPELINE_SVC`, and GitHub → `gha-deploy` → `TF_DEPLOY`. No Snowflake secret in GitHub. The key pair stays only as the dbt fallback.
6. **Names:** the existing resources keep their `latam-bank-` / `fh26` names; the resources the new roots add (tables, runtime, Lambdas, APIs, alarms, dashboard) use `lb-demo-`.
7. **Everything is Terraform** (owner decision, 2026-10-04). No CDK, CloudFormation stacks or cdk-nag anywhere.
   - The spec's six CDK stacks become roots under `infra/terraform/`: `data`, `identity`, `agent`, `realtime`, `app` (exists: the web), `ops`, next to the existing `bootstrap` and `platform`. One state per root (`<root>/terraform.tfstate`); cross-root values only through `terraform_remote_state`; `deploy.yml` applies them in that order.
   - Tests: `terraform test` with mocked providers per root (replaces `aws_cdk.assertions`); pytest over the HCL sources for IAM wildcards, log retention and table protection (`python-hcl2`); `trivy config` (replaces cdk-nag); the stateful guard reads `terraform show -json` of the `data` plan (replaces the `cdk diff` text guard).
   - Images: agent and identity images go to ECR repos in `data`, the web's to `latam-bank-web`; the running tag of each is an SSM parameter `/fh26/<name>/image` that the deploy workflow overwrites and Terraform ignores (`ignore_changes = [value]`).
   - Bootstrap: extends Terraform `bootstrap/` (secret containers with no version in state, values set by `put-secrets.sh`; a read-only `gha-plan` role for PR plans; Transaction Search). `cdk bootstrap`, the `GitHubStack` and `infra/bootstrap.sh` are dropped.
   - Realtime: `infra/realtime/` keeps the TypeScript handler code and its Vitest tests only; esbuild bundles it, and the `realtime` root deploys it. The UI plan's TypeScript CDK app is not built.
   - Failure handling changes: Terraform doesn't roll back a failed apply; the deploy stops and the next push converges (architecture-context → Failure handling · deployment §7).
   - Units rewritten: 77, 81 (renamed `81-terraform-data-root.md`), 82–90; UI units 53, 59, 60; `code-standards.md` → Testing · deployment and Deployment; `architecture-context.md` → Stack, Decisions, System Boundaries, Terraform roots, Access Controls, Failure Handling; `project-overview.md` → definition of done.

### Agent-core plan (2026-09-29)

**Spec adjustments found while planning** (verified against the installed libraries on 2026-09-29: bedrock-agentcore 1.24.0, anthropic 1.9.0, langgraph 1.2.12, langgraph-checkpoint-aws 1.2.3, pyjwt 2.15.1):

1. **Refusals (§6):** `anthropic.BetaRefusalFallbackMiddleware` only handles `client.beta.messages` requests, and this plan uses `client.messages.create`. So refusals are handled in code: `stop_reason == "refusal"` → `LLMRefusal` → template reply (or handoff). No fallback model.
2. **Bearer token in AgentCore (§3.2, §12):** AgentCore forwards `Authorization` to `context.request_headers` when the runtime has a `CUSTOM_JWT` authorizer and `requestHeaderAllowlist: ["Authorization"]`. The entrypoint reads it from there, falls back to `payload["session_token"]`, and always re-verifies.
3. **`/ping` (§8):** `bedrock_agentcore.runtime.PingStatus` only has `HEALTHY` and `HEALTHY_BUSY`, so an unhealthy status can't be reported. When data is unreadable, the reply says so and offers a human.
4. **Checkpoints table (§7.2):** `DynamoDBSaver` requires `PK` (S) + `SK` (S) keys and a `ttl` attribute, created exactly that way in Task 6.

### Resolver plan (2026-09-29)

**Spec adjustments found while planning:**

1. **Probabilities include a "none of these" option (§4.2).**
   - **Problem:** a softmax over the candidates alone gives a lone candidate `match 1.00` even when it doesn't fit. Customers have a median of 2 transactions in the window, and every `not_in_list` case is at risk.
   - **Change:** probabilities are a softmax over `[z₁/T … zₙ/T, 0]`, where the extra 0 is "none of these". This is the exact posterior of a pointwise model when at most one candidate is the target.
   - **Effects:** `Scores.p_none` is added, the temperature is fitted on every dev row including `not_in_list` rows, and `understand.v2` tells Jev the scores need not sum to 1.
2. **The LightGBM comparison model is a pointwise binary classifier, not `lambdarank` (§4.2).** Ranking scores have no absolute meaning, so they can't feed the "none of these" softmax or `best_raw_fit`. The objective now matches the logistic regression, which makes the comparison cleaner and removes the second "fit" model.
3. **Features: 13, not about 10 (§4.1).** `merchant_mentioned`, `amount_mentioned` and `date_mentioned` are added. Without them, "not mentioned" (feature 0) would look like "perfect match" (error 0) to the absolute fit. They're constant within a case, so they don't change the ranking.
4. **`Resolver.score(candidates, mentions)` drops the unused `as_of` argument (§3.1).** Mentioned dates are already absolute (`extract` resolves them), and recency comes from candidate order.
5. **One CLI instead of separate scripts (§3.1).** `scripts/resolver.py` has the subcommands `train`, `test-sheet`, `dev-set`, `finalize`, `jev`, `tune`, `ingest-test`, `ceiling-sheet` and `report`. Commands that call Bedrock or Jev refuse to run without `--live`.
6. **The dev writer is a Claude role** (`dev_writer` in `llm/models.yaml`, `devwriter.v1`, Sonnet 5.5, effort `low`). The `extract` prompt changes, so its version moves to `extract.v2`.
7. **Paths.**
   - Artifact: `src/bankagent/resolver/artifacts/v1/`, with `MODEL_CARD.md` inside.
   - Datasets: `agent/resolver/data/`.
   - Reports: `agent/resolver/reports/`.
   - Jev runs: `agent/resolver/runs/jev/`.
   - Training runs: `agent/resolver_runs/` (gitignored).
   - MLflow: `agent/mlruns/` (gitignored).
   - Training history: `agent/.serving-full/` (gitignored), built with `build_local_serving.py --since 2023-06-17`.
8. **The artifact carries 20 self-check rows** with their expected logits. `Resolver.load` refuses an artifact that doesn't reproduce them.
9. **B0 acts only on filter-relevant mentions** (merchant, amount, dates), because `select_candidates` ignores hints. The outcome `ask_nil` (asking on a `not_in_list` case) is split out so that "top-3 recall when asking" excludes those cases, as §6.2 requires. A Jev error on an evaluation case counts as an ask with no options, as the agent would clarify.
10. **Country slice:** histories carry no customer attributes, so a case's country is the customer's most frequent transaction country. The report labels it as such.
11. **Test-set hash:** the SHA-256 is taken over Andrés's completed CSV, the human-authored artifact.
    - An `extract` failure on a test message keeps the row with empty mentions, because the fixed set can't drop rows.
    - A dev row whose writer or `extract` call fails is skipped, and the skip is counted.
12. **The resolver runs only when `extract` succeeded.** No mentions means no scores, and the node uses `understand.v1`.
13. **Runtime image:** built with `--no-default-groups`, so it ships numpy and rapidfuzz only. If LightGBM wins (§4.3), Task 14 moves `lightgbm` into the runtime dependencies.

### UI plan (2026-09-30)

**Spec adjustments found while planning:**
1. **`summary.product_last4` is dropped** (§4.7). The graph's `txn` has `product_id`, not a card number, and adding a product lookup to the confirm path isn't worth it. The card shows merchant, date, amount and reason.
2. **`turn_end` payload** is `{duration_ms, awaiting}` (§4.6). The route comes from the turn's existing `understand`/`route` record, so it isn't duplicated.
3. **Two keys added to the understand `jev` record** (a new §4.10), because the trace needs them and the record didn't carry them:
   - `thresholds`: the flat numeric thresholds applied;
   - `aliases`: `c1…cN` → `{transaction_id, merchant, amount, currency, date}`.
4. **Idempotency markers** live in `conversation_messages` as items with `sk = "~idem#<message_id>"` and `kind = "idem"`. They sort after every message, the listing filters them out, and the publisher ignores them.
5. **Demo identities** gain `demo_password`, `role`, `display_name`, `scenarios` and `short_ttl_allowed` in `config/demo_users.yaml`. The IdP serves the picker list only when `IDP_DEMO_MODE=1`.
6. **Staff tokens use audience `bankagent-staff`.** The agent never accepts them: its verifier requires audience `bankagent`. Realtime tokens use audience `realtime`.

Added in the plan's Phase C (they continue the same numbering):

**Spec adjustment 7 (channel paths):** AppSync Events channels are `/<namespace>/<segment…>`, so the queue channel is **`/queue/all`**. The spec's "`/queue`" means this channel everywhere.

**Spec adjustment 8 (queue rows):** `handoff.v1` has no top-level amount, so queue rows and `/queue` events show priority, reasons, language, age and holder. The amount appears in the packet's verified facts.

### Deployment plan (2026-10-01)

**Spec adjustments found while planning:**
1. **The BFF calls AgentCore with the Bearer token only** (UI plan Task 13 uses `fetch` with `Authorization`; no SigV4). This settles spec §4.1's open item: the web's ECS task role (formerly the Amplify compute role) has **no** `InvokeAgentRuntime` permission.
2. **There's no cookie-signing key.** The UI plan stores the IdP-signed JWT in the cookie directly. Spec §3 and §4.3's "cookie-signing key" is dropped.
3. **The serving bucket and Snowflake role already exist and are Terraform-managed** *(updated 2026-10-04)*. Terraform `infra/terraform/platform` owns the bucket `latam-bank-serving-762197749808-use1` (us-east-1), its public-access block and TLS-only bucket policy, the AWS role `snowflake-serving`, and the storage integration `SI_SERVING` with its stages. `LbDemo-Data` only references the bucket by name and attaches **no** bucket policy (it would overwrite Terraform's).
   - The lifecycle backstop is dropped: the export already keeps only 3 runs.
   - Bootstrap step 6 (Snowflake) becomes a check that the integration still lists the stage; `infra.yml`'s smoke test already does this after every `platform` apply.
4. **The identity Lambda is a container image** built from `agent/Dockerfile.identity`, served with Mangum. The labeled demo identities (`config/demo_users.yaml`) are gitignored because they name real dataset customer ids. So the Lambda reads them from `s3://<serving bucket>/identity/demo_users.yaml`, uploaded by `agent/scripts/seed_demo.py`.
5. **Names:**
   - the table prefix is `lb-demo`, so tables are named `lb-demo-<name>`;
   - the AgentCore runtime name is `lb_demo_agent`, because runtime names allow only letters, digits and `_`;
   - ~~the stacks are `LbDemo-<Part>`~~ *(2026-10-04)*: Terraform roots `infra/terraform/<root>` instead (2026-10-04 #7).
6. **DynamoDB throttling is six per-table alarms** (read plus write throttle events), joined by the composite alarm. One CloudWatch alarm can hold at most 10 metrics, and `SEARCH` isn't allowed in alarms.
7. **Metrics are emitted twice:** with their `Language` dimension, and with the same dimension set minus `Language` (EMF dimension sets). Alarms use the language-free series; the dashboard splits by language.
8. **`sessions` TTL:** `TABLE_SPECS["sessions"]["ttl"]` becomes `"ttl"`, and `SessionRepo.ensure` writes it (90 days), as spec §4.5 requires.
9. **The `turn_end` payload gains `language`,** so metrics can carry the `Language` dimension. The UI view model ignores extra keys.
10. **Route classes for `TurnCount`** are derived in code from the turn's records, in this order:
    1. any handoff → `handoff`;
    2. goal `abstain` or `refuse_injection` → `abstain`;
    3. any `error` or `template` record → `safe_fallback`;
    4. route `clarify` → `clarify`;
    5. otherwise → `act`.
11. **The agent's Bedrock IAM actions** depend on which signing service `AnthropicBedrockMantle` uses. Task 1 records it, and Task 7 uses it.
12. **The GitHub deploy role** (spec §4.2). *(Updated 2026-10-04.)* The deployed role is Terraform's `gha-deploy` with `AdministratorAccess`; it applies every root except `bootstrap`. When it's narrowed, it keeps the resource types the roots manage, plus: ECR push to `latam-bank-web`, `lb-demo-agent` and `lb-demo-identity`, `ssm:PutParameter` on `/fh26/*/image`, `ssm:PutParameter` on `/fh26/web/image`, ECS service and task-definition updates for `latam-bank-web`, and `bedrock-agentcore:GetAgentRuntime`/`GetAgentRuntimeEndpoint`, because the `web` and `verify` jobs call those APIs directly. The Amplify permissions are dropped.
13. **Workflow names:** the data pipeline plan already owns `.github/workflows/ci.yml`, and `infra.yml` owns the Terraform roots, so the app's workflows are `app-tests.yml` (reusable), `app-ci.yml` (pull requests) and `deploy.yml`.

**Supersedes in the UI plan** (Task 8 adds a note to that file):
- Task 7 Step 6: the TypeScript `RealtimeStack` and `bin/app.ts`;
- Task 7 Steps 8–9 and Task 8 Steps 5 and 7: the TypeScript stack, its synth, deploy and probe deploy commands (now the Terraform `realtime` root, unit 84);
- Task 24 Steps 2–3: the hand-made BFF IAM policy and the console-created Amplify app.
- *(2026-10-04)* Also Task 24 Step 1 (`amplify.yml`) and the whole Amplify `LbDemo-Web` stack of deployment plan Task 9: the web is the Terraform ECS service (Architecture Decisions, 2026-10-04 #2).

The handler code and its Vitest tests from UI Tasks 7–8 stay. The probe script stays, and is run against the deployed `realtime` root in unit 90.

**Supersedes in the deployment plan** *(2026-10-04)*: every CDK construct, `cdk.json`, `infra/app.py`, `infra/lb_infra/`, `infra/tests/` (CDK assertions), cdk-nag, `cdk bootstrap`/`synth`/`diff`/`deploy`, and the `GitHubStack`. The plan's tasks remain the reference for resource settings, thresholds and test intent only.

## Spec Changelog

Records that the specs say to fill in at fixed points. Fill them here.

### Resolver

**Changelog:**
- 2026-09-29: draft.
- Test-set SHA-256: to be filled at freeze (§5.4).
- Adoption decision: to be filled after the test run (§6.4).

### Evaluation

**Changelog:**
- 2026-10-01: draft.
- Held-out goal set SHA-256: recorded at freeze (§4.3).

## Session Notes

- 2026-10-04: tracker brought up to date with the repo (pipeline 01–11 and Terraform infra done); specs moved to us-east-1 and ECS Fargate Spot. Offline suite 43 passed.
- 2026-10-04: deployment specs converted to Terraform-only; Carlos added to `allowed_cidrs`. Terraform isn't installed on Carlos's laptop (a 1.15.2 binary was downloaded to a temp folder for the test run); install it (`brew install hashicorp/tap/terraform`) before Terraform units.
- 2026-10-05: unit 28 (resolver simulator) landed in worktree `worktree-resolver-simulator`, branch `feature/28-resolver-simulator`. The simulator's rates are assumptions (simulate.yaml says so); unit 32 must generate 30,000 training and 3,000 simulated-validation cases from `sample_histories` + `simulate` (spec §5.1 sizes). Baseline at branch point was 180 agent tests; 187 with the 7 new ones.
- 2026-10-05: unit 24 (container image, local stack, terminal chat) landed in worktree `worktree-container-local-stack`, branch `feature/24-container-local-stack`. To run the stack from `agent/`: generate the gitignored local artifacts (`uv run python scripts/build_local_serving.py --data-dir <repo>/data/data --out .serving`, then `uv run python scripts/pick_demo_users.py`), `export JEV_API_KEY=…` and `AWS_PROFILE=<your profile>`, `docker compose up -d`, then `uv run pytest -m container`. No `default` AWS profile exists on the laptop, so `AWS_PROFILE` must be exported (the compose defaults to `default`). Baseline at branch point was 190 agent tests; 191 with the identity entrypoint fix.
