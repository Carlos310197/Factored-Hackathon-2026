# Progress Tracker

Update this file whenever the current phase, the active unit or the implementation state changes. Record what is actually implemented.

## Current Phase

- **Data pipeline built (units 01–11)**, **Terraform infrastructure deployed** (state, OIDC, serving bucket, Snowflake objects, ECS web hosting shell), **Agent core units 12–25 complete** (scaffold, Jev client, identity tokens, dispute policy, serving reader and read tools, DynamoDB store, write tools and handoff packet, Jev question sets/thresholds/routing, OpenAI on Bedrock, LangGraph workflow and agent service, AgentCore runtime entrypoint, local serving builder and demo identities, container image + local compose stack + terminal chat, and unit 25: live checks, the definition-of-done run and the README) and **Transaction resolver units 26–37 complete** (features and splits, history sampler, simulator, extract hints and `understand.v2`, test sheet and CLI, model, training, dev-set builder, finalize, systems and tuning, Jev runs and report, graph integration). Agent core is done (12–25); the resolver's remaining units 38–39 are live runs. **Evaluation units 40–51 complete** (as-is diagnosis run on the local drop; `eval/` goal generator, persona, conversation runner, run CLI, classifier, metrics, judge and report, offline code, then unit 51's dev run and held-out freeze; 52 is `[live]`). **UI units 53–75 and deploy 78, 80–85 are live** (agent, web, IdP, realtime in us-east-1); unit 76 UI polish pass done 2026-10-05 (branch `feature/76-ui-polish`). Not started: `ops` root, 79, 86–90.
- Region: **us-east-1** for all our AWS resources and Snowflake. The organizer bucket (theirs) stays in us-east-2.
- Offline suite: `uv run pytest -m "not snowflake"` → 43 passed, 6 deselected (2026-10-05). Agent suite: `cd agent && uv run pytest` → 195 passed (2026-10-05). Container contract: `cd agent && uv run pytest -m container` → 4 passed against `docker compose up` (2026-10-05).
- Submission deadline: **2026-10-05**.

## Current Goal

- Transaction resolver is complete (units 26–39, both runs, human ceiling).

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
- 2026-10-04: a second team IP added to `allowed_cidrs` in `infra/terraform/app/main.tf` (test updated first; `terraform test` 3/3 passed). Live after `infra.yml` applies it on `main`.
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
  - `app.py`: AgentCore entrypoint with `/ping` and `/invocations` endpoints on port 8080, JWT re-verification (defence in depth), Bearer token support (Authorization header or session_token payload fallback; superseded by unit 56: header only), message validation (max 2000 chars), customer_id from JWT only (never from payload), graceful identity outage handling;
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
- 2026-10-05: **Unit 25: Agent Live Checks, Definition-of-Done Run and README** (`agent/scripts/smoke_serving.py`, `agent/README.md`, `agent/docs/smoke-results.md`; worktree `worktree-agent-live-checks`, branch `feature/25-agent-live-checks`):
  - `scripts/smoke_serving.py`: per-turn serving read latency (`list_transactions` + `get_accounts`, 60-day window) against `SERVING_URI` (local dir or `s3://`). Measured: **local p50 12 ms / p95 14 ms** (20 customers, local dev set `local-20261005064514`) and **S3 p50 801 ms / p95 818 ms** (10 customers, pipeline export `37199535018-1`) — under the 2000 ms that would flag the spec §7.1 fallback;
  - Bedrock smoke (`scripts/smoke_bedrock.py`, synthetic input): extract `openai.gpt-oss-20b` 2617 ms, compose `openai.gpt-oss-120b` 1847 ms. All three live smoke results (Jev 2026-10-04, Bedrock, S3) are now recorded in `agent/docs/smoke-results.md`;
  - **Definition-of-done run (spec §11) recorded** in `agent/docs/smoke-results.md`: all 8 scenarios passed against the real serving set and real Jev + Bedrock (`docker compose up` + `scripts/chat.py`, fresh session per scenario) — ES account inquiry, PT decline explanation (real declined purchase), ES dispute filed after confirmation with read-back verification (`DSP-1791184095032DD240BD5`), ambiguous → clarify, unsupported → abstain, unauthorized → handoff with a `handoff.v1` packet that validates (`HND-17911841872171CD714E4`, priority critical), injection refused then handed off on repeat, expired token rejected (`auth_required`, no model call). Decision-record kinds per turn recorded alongside;
  - **Bug fix (unit 21's code) with a test:** `Deps.clock`'s `default_factory=time.monotonic` stored a float instead of the callable, so every `/invocations` failed with `TypeError: 'float' object is not callable` (the harness always injected an explicit clock, hiding it). Fixed in `graph/deps.py`, pinned by `test_default_clock_wiring_survives_a_turn`;
  - **Bug fix (unit 20's code) with tests:** malformed model JSON (decoder restart / split value mid-object) was silently salvaged by `llm/client.py`, producing replies missing their first clause (seen live twice). The boundary now rejects both shapes (`ambiguous JSON output`, duplicate keys → `invalid JSON output`) and the reply falls back to the fixed template; preamble tolerance kept (`test_restarted_json_object_is_rejected_not_salvaged`, `test_duplicate_keys_in_json_object_are_rejected`, `test_json_with_text_preamble_still_parses`);
  - `agent/README.md`: setup, environment, models (gpt-oss on Bedrock Mantle), AgentCore authorizer notes, data/privacy, live-smoke rules and known limitations;
  - Data-use gate cleared with the owner (organizers confirmed; the run used the real serving set, no fixture). Scenario data rule applied: the double-charge scenario uses `demo21` (`CLI-NS0BYNOKEL6S`, real duplicate pair at Tienda Don José 2026-06-15/16, picked by query and appended to the gitignored `config/demo_users.yaml`) because no generated demo identity has a repeat merchant pair; the PT decline uses `demo16` (real declined purchase at Gasolinera Express);
  - All tests pass: 195/195 offline in agent/ (191 at branch point + 1 `Deps.clock` regression test + 3 LLM-boundary tests), 43/43 in root offline suite, 4/4 container against the stack.

- 2026-10-05: **Unit 29: Agent-Core Changes I** (`agent/src/bankagent/llm/`, `decisions/`):
  - `llm/extract.py`: `extract.v2`, `mentions` gains nullable `type_hint` (`purchase|withdrawal|transfer|payment|deposit`), `channel_hint` (`atm|pos|app|web|branch`) and `city`; `llm/models.yaml`: `extract` is `extract.v2` and the new offline `dev_writer` role (`devwriter.v1`, effort `low`, same gpt-oss-120b model as `compose`, override `LLM_DEV_WRITER_MODEL`);
  - `decisions/understand.py`: public `matches_mentions(t, m)` (merchant substring, amount within 1%, date inside range) shared with `select_candidates`; this fixes `select_candidates`, whose private filter compared amounts for exact equality; `describe_txn(t, score=None)` appends ` · match 0.93`; `build_understand_request(..., scores=None)` adds `match` to the criteria and candidate state only when scores are given;
  - `decisions/questions/understand.v2.yaml`: v1 plus the match-score instruction on `target_transaction` (adds that the scores need not sum to 1, per resolver plan #1); the graph still uses v1 until unit 37;
  - Tests first: `test_extract_schema_has_nullable_hints`, `test_dev_writer_role_is_configured`, `test_matches_mentions_is_the_prefilter_rule`, `test_scores_are_shown_only_when_given`; agent suite 199 passed (195 + 4).

- 2026-10-05: **Units 30–37: resolver tooling, model, training, evaluation, graph integration** (one worktree `worktree-transaction-resolver`, branch `feature/29-39-transaction-resolver`; units 31/32/34, 35, 36 and 37 were built by parallel subagents, each committed alone):
  - 30 `records.py`, `testset.py`, `scripts/resolver.py` (all nine subcommands; `dev-set`, `ingest-test`, `jev` refuse without `--live`), `tests/resolver_llm.py::ScriptedLLM` (OpenAI `chat.completions` shape, not the plan's Anthropic one). The real blind test sheet was generated from the full-history local serving set (`.serving-full`, gitignored): `agent/resolver/data/test_sheet_v1.{csv,json}` (75 hard / 60 easy / 15 nil, ES 76 / PT 74 since odd-sized slices can't balance) plus `TEST_SHEET_README.md`. **Still to do: send the CSV and README to Andrés.** Root `.gitignore` gained `!agent/resolver/data/` because the `data/` rule hid the committed datasets;
  - 31 `model.py` (JSON artifact, none-of-these softmax, 20-row self-check refusing tampered artifacts); 32 `train.py` + `tracking.py` (grids, MLflow file store); 34 `finalize.py` (finalist choice with the 0.02 tie to logreg, temperature fit, promotion, model card). Plan code used unchanged. `test_resolver_train.py` takes about 40 s (MLflow; set `MLFLOW_DISABLE_AGENT_HINT=1`);
  - 33 `devset.py` (writer sees only the details; LLM failures skipped, not fatal), adapted to the OpenAI request shape;
  - 35 `systems.py`, `metrics.py`, `tune.py`: B0/B1/Jev decision rules, outcomes, bootstrap CIs, threshold search. `write_thresholds_v2` rewrites the whole `target_transaction` block of `thresholds.v1.yaml` as an inline mapping, because the repo's v1 file writes it as an indented block;
  - 36 `jev_runs.py`, `evaluate.py`: resumable cached Jev runs, `tune_systems`, `evaluate`, adoption rule as code (P replaces B2 iff mean wrong-action(P) ≤ B2's and mean hard-slice resolved-within-one-step(P) > B2's), error sheet, plots, report. The offline flow `finalize --promote` → `tune` → `report` ran end to end in a temp directory;
  - 37 `Deps.resolver` / `Deps.understand_qs_scored` (default `None`), `Settings.resolver_artifact` / `thresholds_file` (default off), `runtime.load_resolver` (never raises), `kind: model` decision records, and fallback to `understand.v1` with one `kind: error` record on any resolver failure. The Dockerfile needed no change: `--no-default-groups` already keeps lightgbm, scikit-learn, mlflow and matplotlib out of the image;
  - Tests: agent suite 242 passed (195 → 242), root offline suite 43 passed. Not run: units 38 and 39 (`[live]`), which need the owner's approval for each Bedrock/Jev run.

- 2026-10-05: **Units 40–50: evaluation, offline code** (one worktree `worktree-evaluation`, branch `feature/40-50-evaluation`, built while resolver units 38–39 run; each unit committed alone; units 51–52 are `[live]` and wait for 39's adoption decision):
  - 40 `analysis/` as-is project: `asis.load` (DuckDB views, backup prefix refused, no PII columns), `asis.metrics` demand/quality/satisfaction, synthetic fixture. Plan code used unchanged; `cd analysis && uv run pytest` → 6 passed. `.gitignore` now tracks `analysis/pyproject.toml`, `uv.lock`, `asis/` and `reports/` (the old profiling scripts in `analysis/` stay untracked, as before).
  - 41 `asis.metrics` capacity/disputes/digital/transcripts/fairness/`collect`, `asis.artifacts` (seven detectors + `detect_all`). Plan code unchanged; `cd analysis && uv run pytest` → 13 passed. `SHIFT_HOURS` is an assumption (the data has no schedule).
  - 42 `reconcile.py`/`.sql`, `charts.py`, `report.py`, `run.py`. Real run on the local drop (offline, about 6 min, DuckDB rescans the CSVs per query): `analysis/asis/out/asis_metrics.json`, `reports/asis-2026-10-05.md`, `reports/figures/asis-*.png`; two runs gave identical metrics. Spot checks match spec §2 (Transaccional FCR 0.9165, n 80,264; 230,196 interactions; 22,552 complaints; Portuguese agents 10.75% of 1,200; dispute first response p50 37 h). Reconciliation is **not reconciled** (no curated marts yet; `reconcile.sql` is ready for when they exist). `cd analysis && uv run pytest` → 25 passed.
  - 43 `eval/` project (`evalkit`, depends on `bankagent` by path): `config`, `splits` (same rule as the resolver), `universe`, `goals` (21 groups, seeded, labels from `DisputePolicy.evaluate()`, the generator names the group it cannot fill, review sheet, `freeze`). Plan code unchanged apart from `agent.region`. `cd eval && uv run pytest` → 12 passed. The real goal sets are generated in unit 51.
  - 44 `evalkit.persona`: OpenAI-compatible persona client (one retry on 5xx, errors raise, `[DONE]` detection) and the rule checks (`too_long`, `id_leak`, `out_of_character`, `wrong_language`); mocked HTTP only. Offline suite 19 passed. `persona.model` stays empty in `config.yaml` until the owner picks an OpenCode-served model.
  - 45 `evalkit.faults` (`jev_down`, `serving_down`, `dynamo_throttle` via a failing proxy; the real store is never touched) and `evalkit.conversation` (`TokenIssuer` incl. short-TTL expired tokens, `snapshot`, `run_conversation` with discard, max-turns and harness-error end reasons). Offline suite 29 passed.
  - 46 `evalkit.agent_runtime` (one table prefix per goal repetition, so a second rep never sees the first rep's dispute) and `evalkit.run` (resumable `(goal_id, rep)` pairs, run manifest with the goal-set hash, 8 workers; refuses without `--live`). Offline suite 34 passed.
  - 47 `evalkit.classify`: one class per conversation from the store diff, decision records and replies; `unsafe` overrides and records its types; the customer's own earlier `DSP-` is not a false claim; a zero-turn or never-expired conversation is `persona_discarded`. The judge never decides a class. Offline suite 50 passed.
  - 48 `evalkit.metrics` (headline, family and slice metrics, goal-clustered bootstrap, variability, cost with `incomplete`/`not defined` states) and `evalkit.compare` (legacy-vs-new rows with the different-workloads label, fairness rows, projected savings that needs every input). All nine `REQUIRED_KEYS` exist in the real `asis_metrics.json` from unit 42. Offline suite 58 passed.
  - 49 `eval/judge_rubric.md` (judge.v1) and `evalkit.judge` (packet usefulness 0–2 ×4, reply language and faithfulness pass/fail, `human_sheet`, Cohen's κ, `validate`; the judge never decides a class). The plan's test stub was Anthropic-shaped; the agent's `call_json` now uses the OpenAI `chat.completions` shape (ADR 2026-10-05), so the stub in `test_judge.py` was adapted and the judge code is unchanged. Offline suite 62 passed. The 40-label human validation is unit 52.
  - 50 `evalkit.report`: `suggest_cause`, `build`, `render` (all nine report sections, the different-workloads label on every legacy row, projections in their own section), `charts` (one series colour, one accent, direct labels) and the CLI that writes `classifications.jsonl`, `error_analysis.csv` and `reports/eval-<date>.md`. Offline suite 65 passed.
  - Offline totals: `cd analysis && uv run pytest` → 25 passed; `cd eval && uv run pytest` → 65 passed. Units 51–52 (`[live]`) are not started: they need the owner's approval for every persona, Bedrock and Jev run, an OpenCode `persona.model`, `OPENCODE_API_KEY`, a local serving set, DynamoDB Local, and (for 52) the held-out freeze and Carlos's 40 judge labels. Hold 51 until unit 39 records the resolver adoption decision, so the eval runs against the final agent.
  - 54 (UI) `sessions` and `conversation_messages` tables (90-day TTL on messages), `SessionRepo` and `MessageLog` (claim/store_reply/append/list, idempotency markers `~idem#<id>`), `Store.sessions`/`Store.messages`, Streams (`NEW_IMAGE`) on `handoffs`, `decision_records`, `conversation_messages` (turned on for existing tables too). Offline agent suite 246 passed.
  - 55 (UI) IdP: `issue_token(extra=)`, customer tokens carry `role`, `DemoUser` role/display_name/demo_password/scenarios/short_ttl_allowed, `POST /auth/staff/login` (aud bankagent-staff), `POST /auth/realtime-token` (aud realtime, exp ≤ source), `GET /auth/demo-users` (IDP_DEMO_MODE=1 only), 30 s `short_ttl` OTP tokens. 9 new tests; agent suite 255 passed.
  - 57 (UI) `decisions/trace_payload.py` (`thresholds_map`, `alias_view`, `confirmation_payload`): understand `jev` record gains `thresholds` and `aliases`; reply gains `summary` {merchant, date, amount, currency, reason_code} when awaiting confirmation (no product_last4, AD #1). Agent suite: 267 passed.
- 2026-10-05: **UI unit 56**: entrypoint control gate, idempotent turns per message id, message log, `turn_end` record (`app.py`, `service.py`).
- 2026-10-05: **UI unit 57**: trace payloads (thresholds + aliases on the understand record, confirmation summary). Aliases use the filtered candidates passed to `build_understand_request`.
- 2026-10-05: **UI unit 59**: `infra/realtime/` (Node + Vitest, no CDK): `handlers/namespace.js` and `authorizer/{rules,index}.ts` with the same `channelAllowed` rule (`/queue/all`, AD #7), `verifyRealtime`/`decide` (RS256, aud `realtime`, ttlOverride 0), `scripts/probe-subscribe.ts` (never run here). `npm test`: 32 passed. Infrastructure is unit 84.
- 2026-10-05: **UI unit 60**: `infra/realtime/publisher/{map,publish,index}.ts`: stream records to `/session/<sid>`, `/queue/all`, `/trace/<sid>` events (idempotency markers and REMOVE ignored, `turn_end` adds `turn_complete`), SigV4 publish in batches of 5, per-record `batchItemFailures`. Offline: `cd infra/realtime && npm test` passes (59 tests).
  - 61 (UI) `web/` scaffold: Next.js 16.3.8, Tailwind v4 `@theme` tokens for worlds B and C, Schibsted/Hanken fonts, `output: "standalone"` (container on ECS), Vitest 5 + Playwright configs, `lib/ids.ts` `newClientMessageId`. `/` redirects to `/chat`. `cd web && npm test` 1 passed; lint and build pass.
  - 63 (UI) `web/lib/server/{env,jwt,session,http,idp}.ts`, `web/proxy.ts` and `/api/auth/{login,otp,staff-login,logout,realtime-token,demo-users,debug-claims}`: RS256 verification via JWKS (issuer, audience, role, expiry), httpOnly `cust_session`/`staff_session` cookies, IdP client, presence-only page guard. `server-only` aliased to an empty module in Vitest. Default `AWS_REGION` is us-east-1 (plan said us-east-2). `env()` is not memoized (tests toggle DEMO_MODE) and requires IDP_URL/IDP_ISSUER in production; IdP 4xx map to 400/401, 5xx and malformed replies to 503. `npm test` 25 passed, lint, tsc and build clean.
  - 64 (UI) `web/lib/server/{ddb,sessions,messages,handoffs,records}.ts`: DynamoDB access per the plan's Task 12 (atomic claim, transactional takeover/return/resolve with a system message carrying `meta.control`/`agent_name`, which the realtime publisher turns into a control event; idempotency markers filtered by `kind = message`). Tests in `tests/unit/ddb.test.ts` need DynamoDB Local and skip without `DYNAMODB_ENDPOINT`; tsc, lint and `npm test` (25 passed, 6 skipped) clean.
  - 65 (UI) `web/lib/server/agentcore.ts` (`runtimeSessionId`, `invokeAgent` with Bearer + runtime-session + custom-message-id headers, `AgentError`), `POST /api/chat` (takeover gate, idempotent claim, `CHAT_ASYNC` 202, 401/502/504 mapping) and `/api/sessions/[sid]/messages` (GET owner-or-agent, else 404; POST takeover holder, else 409). Web suite 45 passed with DynamoDB Local; lint and build pass.
  - 70 (UI) `/chat` (world B, assistant-ui `useExternalStoreRuntime` over the Zustand store): `ChatScreen`, `MessageView`, `Chips`, `ConfirmCard`, `Receipt`, `AsOfBanner`, `ExpiredSheet`. `useChannel` `onResync` is `syncHistory(store, sid)` (a history 401 expires the session and opens the sign-in sheet). Web suite 114 passed; tsc, lint, build clean.
  - 71 (UI) Staff console (world C): `/login?staff=1` (`StaffLogin`, demo staff picker, `safeNext` with `/agent` fallback), `/agent` and `/agent/[handoffId]`, live `Queue` (290px, Open/Mine/In takeover/Resolved, priority marker plus word, plain reasons, language, age, holder, no amount, one-time highlight on new open rows, arrow keys), `CaseHeader` (HND id, customer id, language, data as-of, session, opened time, status pill, lifecycle actions hidden when not allowed, resolve dialog with outcome + note), `lib/staff/actions.ts`; tabs are placeholders for 72-73.
  - 72 (UI) `components/trace/Gauge.tsx` (shared meter, colour from the bar via `lib/trace/signals.ts`; unit 73 reuses it), `PacketTab` (request original + EN, facts and actions with receipt ids, failed policy first, open questions, "Why it came to you" gauges from `whyBars`), `ConversationTab` (history + live via `useChannel`, deduped by id in the chat store, system lines via `systemLine`; composer enabled only when `control == human:<me.sub>`, language reminder) and `ConsoleWithTabs` wiring (trace fetched once per case for `whyBars`; Trace tab still a placeholder for 73).
- 74 (UI) `/demo` stage: `app/demo/page.tsx` (staff-guarded, demo mode), `components/demo/{DemoStage,PhoneFrame,SignInPanel,ScenarioRail,HandoffTicker}.tsx`, `lib/demo/scenarios.ts` (8 scenarios, tag names from `tag_scenarios.py`). Three acts, claims via debug-claims, live trace in demo mode, queue ticker.
- 75 (UI) web E2E and a11y: `web/e2e/{fixtures,customer.spec,console.spec,demo.spec}.ts`, guarded E2E cookies in `lib/server/session.ts` (only with `E2E_MOCK=1` and `DEMO_MODE=1`), `tests/unit/e2e-guard.test.ts`. `npm run e2e`: 13 passed (desktop + phone). Axe: no serious/critical on `/login`, `/chat`, `/agent/<id>`, `/trace/<sid>`, `/demo`.
- 80 (deploy) identity Lambda: `agent/src/bankagent/identity/lambda_handler.py` (`build(env, s3, secrets)`, `handler`; key from Secrets Manager, users from `DEMO_USERS_S3_URI`, 503 `identity_unavailable` on cold-start failure, not cached), `agent/Dockerfile.identity` (ARM64 Lambda image, IdP deps only), `mangum` added, `agent/tests/test_identity_lambda.py` (moto).

- 88 (deploy, secrets part only) `infra/terraform/bootstrap/secrets.tf` (containers `lb-demo/jev`, `lb-demo/idp-signing-key`, no versions, `prevent_destroy`; outputs `jev_secret_arn`, `idp_signing_secret_arn`), `put-secrets.sh` (silent prompt for Jev, openssl RSA 2048 PEM for the IdP key, both over stdin), tftest run `secrets_are_containers_only_and_protected`. Still open in 88: `gha-plan` role, Transaction Search, `gha-deploy` trust narrowing, `seed_demo.py`, `infra.yml` PR jobs.

- 81 (deploy) `infra/terraform/data/`: six `lb-demo-*` tables via `for_each` over `tables.json` (exported from `TABLE_SPECS`/`STREAM_TABLES` by `agent/scripts/export_table_specs.py`; drift test `test_table_specs_export.py`), PITR, deletion protection, `prevent_destroy`, NEW_IMAGE streams on handoffs, decision_records, conversation_messages (`stream_arns` has exactly those three); ECR `lb-demo-agent`/`lb-demo-identity` (immutable, scan, keep 10); SSM `/fh26/{agent,identity}/image` placeholders with `ignore_changes = [value]`; serving bucket by data source only. Unit 78 will add the `sessions` TTL later (in-place update; re-run the export). `terraform validate` and 6 tftest runs pass; provider warns GSI `range_key` is deprecated in favour of `key_schema` (harmless).
- 82 (deploy) `infra/terraform/identity/`: `lb-demo-identity` arm64 image Lambda (512 MB, 10 s, X-Ray) behind a `$default` AWS_PROXY HTTP API (10/s, burst 20, permission scoped to the API). Image URI read from the `/fh26/identity/image` parameter via `data` remote state; signing secret referenced by name (`data.aws_secretsmanager_secret`). `IDP_ISSUER` = `api_endpoint`, `IDP_DEMO_MODE=1`, outputs `issuer`, `jwks_url` (`<issuer>/jwks.json`), `api_id`, `function_name`. `terraform test`: 4 runs pass (offline, mocked).

- 78 (deploy) agent deployed settings: `load_settings()` reads the Jev key from `JEV_SECRET_ID` (raw string, stripped) when `JEV_API_KEY` is unset and logs an error instead of raising on failure (empty key, no crash loop); `Settings.git_sha` from `GIT_SHA` (default `dev`); `sessions` TTL 90 days (`SessionRepo.TTL_DAYS`, attribute `ttl`); `DecisionLog.append(trace_id=)` stores `trace_id` only when given; `turn_end` payload carries `language`. `tables.json` regenerated and `data.tftest.hcl` TTL assertions flipped (sessions now has TTL): the controller must apply the in-place TTL update on the `data` root. 284 agent tests pass, `terraform test` in `data` passes. The local `.env` rename (`TYPESAFE_API_KEY` to `JEV_API_KEY`) was not done: no `.env` in the worktree.
- 2026-10-05: **Unit 38: Resolver Real Run I** (owner approved the Bedrock dev-set build and the Jev dev runs; run with `AWS_PROFILE=hackathon-sso`, the default profile is the organizers' S3-only user and gets a 403 on Bedrock Mantle):
  - Train (offline, `train --serving .serving-full`, 30k train / 3k simulated-validation cases, 17 grid points, MLflow in `agent/mlruns`): logreg C=1 simulated-validation top-1 0.919 (hard 0.905), LightGBM 31 leaves / lr 0.1 / 500 trees top-1 0.927 (hard 0.894);
  - Dev set: `agent/resolver/data/dev_v1.jsonl`, 300 rows (150 ES / 150 PT), 158 cases skipped after LLM errors (mostly gpt-oss output truncated at `max_tokens`). **Slice mix is skewed**: 186 easy / 84 hard / 30 not_in_list, because the skipped cases were disproportionately hard; the simulator targets about 50% hard. 17 extractions had no mentions. No scientific-notation amounts, no `CLI-`/`PRD-` ids. Carlos has not yet reviewed 30 rows for realism (spec §5.3 item 5), so the regeneration count `k` is not recorded;
  - Finalize (`finalize --promote`): **logreg chosen**, dev hard-slice top-1 0.917 vs LightGBM 0.833, temperature **1.337**; dev ECE 0.168 (logreg), nil AUC 0.873. Artifact and `MODEL_CARD.md` in `src/bankagent/resolver/artifacts/v1/`. LightGBM stays a resolver-group dependency;
  - Jev on dev (1 run each, 300 calls per system, 0 errors): `resolver/runs/jev/dev/{B2,P}_r1.jsonl`;
  - Tune (≤ 2% dev wrong-action): B1 τ=0.62 φ=0.30 (coverage 0.637, resolved-in-one-step 0.853); B2 t=0.59 m=0.18 (0.747, 0.910); **P t=0.74 m=0.48** (0.767, 0.947). `decisions/thresholds.v2.yaml` written; figures `dev_coverage_curve.png` and `dev_reliability.png`. These are dev numbers, not the adoption decision: that is unit 39 on the frozen test set;
  - Bugs fixed on the way, with tests: the dev writer is now a plain-text call (the model returned `{ {"message": ...}` 9 times out of 10 in JSON mode) and writes amounts in plain digits (`:g` produced `3.39847e+07`); `call_json` now accepts a bare doubled opening brace `{ {` (no content dropped; a restart after content stays rejected, unit 25's regression test still passes). The same doubled brace made the production `extract` fail about 70% of the time on `openai.gpt-oss-20b`, so this also helps the agent. Open: `extract` still hits `truncated output` on roughly 20% of calls at `max_tokens: 1024`;
  - Tests: agent suite 245 passed.

- 2026-10-05: **Unit 39: Resolver Real Run II** (worktree `worktree-resolver-real-run-test`, branch `feature/39-resolver-real-run-test`; owner approved the Bedrock ingest and the Jev test runs):
  - **Process note:** PR #28 merged at its first push, so the unit 38 commits (artifact, dev set, tuned thresholds, the `{ {` JSON fix) were not on `main`; the first test ingest ran without the fix (92 of 150 extractions failed) and was discarded. Those commits are now merged into this branch and the 150 Bedrock calls were redone (so 300 `extract` calls in total were spent on the test set; no Jev call had been made, so the evaluate-once rule is intact). The discarded file is not in the repo;
  - Test set frozen before any evaluation (SHA-256 in Spec Changelog → Resolver), ingested to `agent/resolver/data/test_v1.jsonl` (150 rows, transaction fields only). **41 of 150 rows (27%) have extraction errors** (34 truncated output, 7 restarted JSON) and run with empty mentions, as the live agent would; every system reads the same extraction. The dev set excluded such cases, so dev-tuned thresholds never saw them;
  - Jev test runs: B2 and P, 3 repeats, 900 calls, 0 errors (`resolver/runs/jev/test/`);
  - Result (`resolver/reports/eval-2026-10-05.md`, `errors.csv`): wrong-action 0.7% for both B2 and P (1 of 150); hard-slice resolved-within-one-step P 96.0% vs B2 95.6% (paired P−B2 95% interval −1.3 to +10.7 points, so **not established at n = 150**); coverage 76.2% vs 76.0%; B0 28.0% / B1 43.3% coverage with 0 wrong actions; on the 15 not_in_list cases P resolved 57.8% in one step vs B2 80.0% and B2 acted wrongly once (small sample); P adds about 117 median Jev input tokens per call, latency unchanged (p50 about 280 ms);
  - **Adoption decision: adopt P** (the rule fixed in code: wrong-action(P) ≤ B2 and hard-slice resolved-one-step(P) > B2, both on point estimates). `agent/docker-compose.yml` now sets `RESOLVER_ARTIFACT` and `THRESHOLDS_FILE` (pinned by `tests/test_compose_resolver.py`); `agent/README.md` documents the resolver, the evidence and the `extract` failure rate. The Terraform `agent` root (units 83+) must set the same two variables when it is built;
  - Error analysis in the report labels every cause "unconfirmed": 9 failed cases for P (6 simulator-gap/other, mostly not_in_list cases where P asked instead of resolving), 1 act-wrong (ranker ranked the target below another candidate);
  - **Human ceiling not done**: `agent/resolver/data/ceiling_v1.csv` (40 blind cases) is waiting for Carlos to fill the `pick` column (a candidate number or `none`); then rerun `uv run python scripts/resolver.py report` (offline) to add the ceiling to the report;
  - Tests: agent suite 293 passed.

- 2026-10-05: **`extract` model comparison on the 150 test messages** (owner-approved, about 300 Bedrock calls; `agent/scripts/compare_extract_models.py`, production `extract.v2` prompt and `max_tokens` 1024, only the model swapped; no Jev calls, `models.yaml` unchanged):
  - `openai.gpt-oss-20b` (current): 41 of 150 failed (27%); on the 99 non-nil rows where it worked, 61% of extractions are consistent with the known target (`matches_mentions`, a strict check: merchant substring, amount within 1%, date inside range);
  - `mistral.ministral-3-14b-instruct`: **0 of 150 failed**, p50 1.8 s / p95 2.9 s, about 209 output tokens, 64% consistent on all 135 non-nil rows (65% on the 99 rows where gpt-oss worked);
  - `qwen.qwen3-next-80b-a3b-instruct`: **0 of 150 failed**, p50 3.3 s / p95 4.3 s, about 202 output tokens, 61% consistent (63% on the same 99 rows);
  - `xai.grok-4.3`: listed by the Mantle endpoint, but chat-completions rejects it (`isn't supported on this route`); a one-off Responses-API probe timed out at 30 s on a trivial prompt. Not testable through the current client, so not compared;
  - Reading: the new models fix reliability (27% → 0%) at equal extraction quality on this metric. Not measured: end-to-end effect on B2/P (would need a labeled rerun of the Jev test runs), Spanish/Portuguese gloss quality, cost. Switching is `LLM_EXTRACT_MODEL=<id>`; the dev set, thresholds and test evaluation were all produced with gpt-oss-20b.

- 2026-10-05: **Resolver run 2: `extract` switched to `mistral.ministral-3-14b-instruct` and the test evaluation redone** (owner-approved: 150 Bedrock + 900 Jev calls; same frozen sheet SHA-256, same artifact and thresholds; files in `agent/resolver/ministral/{data,runs,reports}`, run 1 kept untouched in `agent/resolver/{data,runs,reports}`):
  - Extraction errors 41/150 → 1/150. Coverage rose for the non-Jev systems (B0 28% → 44%, B1 43% → 58%) because fewer messages lost their mentions; B0 and B1 each made 1 wrong action (0 in run 1);
  - B2 and P: wrong-action 0.7% each (1 case); coverage 76.0% vs 76.7%; hard-slice resolved-within-one-step **P 98.7% vs B2 94.2%**, paired P−B2 95% interval +1.3 to +10.7 points (run 1: 96.0% vs 95.6%, interval −1.3 to +10.7); top-3 recall when asking P 98.3% vs B2 89.3%;
  - **Adoption decision unchanged: adopt P**, now with the paired interval excluding zero on the hard slice. Caveats: the two runs share the same 150 messages, so they are not independent evidence; thresholds were tuned on gpt-oss extractions; both results are reported;
  - `scripts/resolver.py report` now prints the extract model next to the prompt version. Docs updated (`agent/README.md`, `context/code-standards.md`, Architecture Decisions 2026-10-05).

- 2026-10-05: **Human ceiling done** (Carlos, blind, 40 random test cases: 16 hard / 21 easy / 3 not_in_list; `agent/resolver/data/ceiling_v1.csv`, also linked from `resolver/ministral/data`): 27/40 = 67.5%. Rule used: type `none` when a message is ambiguous. Misses: 11 `none` answers where the target was in the list (abstentions), 1 wrong candidate, 1 candidate picked on a not-in-list case; of the 27 answers that named a candidate, 25 were right (92.6%). Both reports (`resolver/reports/` and `resolver/ministral/reports/`) now carry the ceiling and this reading; it is not comparable to `resolved_one_step`. Resolver definition of done: complete.
  - 51 (live, owner-approved step by step; branch `feature/51-eval-live-dev`, worktree `worktree-eval-live-dev`): local serving set and DynamoDB Local, persona smoke, goal sets (seed 2026), three dev runs and the freeze. Persona `gpt-6-luna` through OpenCode's Responses API (see Evaluation plan decision 4). The dev run of record is `eval/runs/20261005-dev3`: safe automated resolution 15/15, correct outcome 29/30, unsafe 0/30, no harness errors; the `qwen3.6-plus` run and dev2 are kept as history. Owner decisions applied before the freeze: unsupported goals tell the persona to decline an offered human; `account_info` goals use card and account products only; `bad_nonexistent` goals are about a purchase the customer made. Findings for the agent-core owner (date drift in confirmation text, loan balance declined on the first turn, 20 template-fallback turns) are in `calibration_notes.md`. Held-out set frozen, hash in the Spec Changelog. `cd eval && uv run pytest` → 74 passed. Unit 52 (held-out run, judge validation, report) is next and needs the owner's approval for the run.
- 2026-10-05: **Console stats + demo act 4 · Handoff**: `/agent` queue chips show counts and the oldest open age; `CaseStats` under the case header (turns, mean reply, template fallbacks, handoff → claimed). `/demo` act 4 = phone + one as-is dispute line + the case-only console for the phone's session (`Console caseOnly`). Tests `demo-handoff.test.tsx`, act-4 case in `demo.test.tsx`, e2e `act 4` (also checks `/agent`); 200 unit and 9 desktop e2e pass. `ui-context.md` → Demo stage documents both.

## In Progress

- None.

## Next Up

Unit ranges, in build order (see `feature-specs/README.md` for the full list and dependencies):

| Units | Subsystem | Status | First dependency |
| --- | --- | --- | --- |
| 01–11 | Data pipeline | **done**, running daily and green | none |
| 12–25 | Agent core | **done**; 25 ran and recorded the definition-of-done run | none (16 uses a synthetic fixture; 23 uses the local drop) |
| 26–39 | Transaction resolver | 26–39 **done** (P adopted; human ceiling done) | 12, 16 |
| 40–52 | Evaluation | 40–51 **done** (51: dev run and frozen held-out set); 52 is `[live]` and waits for the owner's approval | 43+ need agent core 12–24 |
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

- ~~**Data-use approval:** confirm with the organizers (Slack `#technical-help`) that dataset records may be sent to Amazon Bedrock and to TypeSafe (Jev). This extends the pipeline spec's open item.~~ **Resolved 2026-10-05:** the organizers confirmed; unit 25's definition-of-done run used the real serving set. The evaluation spec's extension to the persona provider stays open (see evaluation risks).
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

### Session Note: UI final-review fixes (2026-10-05)

Fixed in `web/`: C1 HandoffPacket now matches `packet.py` (decision `value` string or number, `p`, policy `detail`); I1 `COOKIE_SECURE`; I2 ECS guard on forged cookies; I3 Summary amount/currency/reason_code are nullish; M1 takeover/return condition on `sessions.control`; M2 resolve refuses an already resolved case; M4 history GET is 401 without any session (404 kept for a non-owner); M5 staff 401s in Console, ConversationTab and the demo stage go to `/login?staff=1&next=...`; M61 `<html lang>` follows the customer's language (en for staff). Tests: `tests/unit/review-fixes.test.ts` plus additions to ddb, messages-route and console tests.

## Architecture Decisions

### 2026-10-05: `extract` model (resolver real run)

`extract` moved from `openai.gpt-oss-20b` to `mistral.ministral-3-14b-instruct` (Bedrock Mantle, same chat-completions client, `LLM_EXTRACT_MODEL` still overrides). **Why:** gpt-oss-20b failed on 41 of 150 real test messages (27%: truncated output or restarted JSON) and Ministral on 0 to 1 of 150, with equal extraction quality on a target-consistency check. **Effect:** the resolver test set was evaluated twice (run 1 gpt-oss, run 2 Ministral; both disclosed, same frozen sheet and thresholds); both adopt P. The dev set, the promoted artifact and the tuned thresholds were not rebuilt, so they still reflect gpt-oss extractions. `xai.grok-4.3` is listed by Mantle but not served on the chat-completions route.

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

### 2026-10-05: LLM model defaults (agent core)

`llm/models.yaml` ships `extract` = `openai.gpt-oss-20b` and `compose` = `openai.gpt-oss-120b` (effort `low`) over the
Bedrock Mantle chat-completions endpoint, not the `openai.gpt-5-6-luna` / `openai.gpt-5-6-terra` roles the plan and
`code-standards.md` named: the commercial GPT-5.6 models need special account access. `LLM_EXTRACT_MODEL` /
`LLM_COMPOSE_MODEL` still override per role, and `test_model_defaults_and_env_override` pins the defaults. The
gpt-oss models occasionally emit malformed JSON (decoder restarts / split values); `llm/client.py` rejects it and
the reply falls back to the fixed template (unit 25 findings, tests in `tests/test_llm.py`).

### 2026-10-05: Bedrock inference runs in a second account

The hackathon account has limited Bedrock model access, so the agent's LLM calls run in account `040684487035`.
When `BEDROCK_ROLE_ARN` is set, `llm/client.py` `_bedrock_session()` assumes that role (with `BEDROCK_EXTERNAL_ID`)
and mints the Mantle token from the assumed credentials; when it is unset, it uses this account's credentials as
before. The `agent` root sets both env vars (`main.tf` locals) and grants `lb-demo-agent-exec` `sts:AssumeRole` on
`arn:aws:iam::040684487035:role/argos-bedrock-role`. That role (managed outside this repo) must trust
`arn:aws:iam::762197749808:role/lb-demo-agent-exec` with the external id and allow `bedrock-mantle:CallWithBearerToken`
plus `bedrock-mantle:CreateInference` on its own projects. Inference quotas and cost now land on that account.

### 2026-10-05: Web session cookies and the E2E guard (final-review fixes)

- `COOKIE_SECURE` drives the `Secure` flag on session cookies (default "1" in production, "0" disables). The current deployment is plain HTTP on the ECS public IP, so it must be set to 0 there until an ALB with TLS exists.
- The forged E2E cookie path (`E2E_MOCK` + `DEMO_MODE`) is also refused whenever `ECS_CONTAINER_METADATA_URI_V4` is set (Fargate always sets it).

### Agent-core plan (2026-09-29)

**Spec adjustments found while planning** (verified against the installed libraries on 2026-09-29: bedrock-agentcore 1.24.0, anthropic 1.9.0, langgraph 1.2.12, langgraph-checkpoint-aws 1.2.3, pyjwt 2.15.1):

1. **Refusals (§6):** `anthropic.BetaRefusalFallbackMiddleware` only handles `client.beta.messages` requests, and this plan uses `client.messages.create`. So refusals are handled in code: `stop_reason == "refusal"` → `LLMRefusal` → template reply (or handoff). No fallback model.
2. **Bearer token in AgentCore (§3.2, §12):** AgentCore forwards `Authorization` to `context.request_headers` when the runtime has a `CUSTOM_JWT` authorizer and `requestHeaderAllowlist: ["Authorization"]`. The entrypoint reads it from there, falls back to `payload["session_token"]`, and always re-verifies. (Superseded by unit 56: header only, no payload fallback.)
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

- 2026-10-05, unit 75: **contrast tokens.** axe `color-contrast` (serious) failed on `c-pass` text (#1A8F5A on white, 4.1:1) and `c-alert` on `c-alert-tint` (#C8337A on #FCE8F1, 4.26:1). New values `c-pass` #167A4D (5.35:1 on white) and `c-alert` #B52C6C (5.07:1 on the tint); `context/ui-context.md` §7 updated. The pending customer bubble shows a muted "enviando…" label instead of `opacity-80` (4.38:1).
- 2026-10-05, unit 75: **deployment note.** The E2E cookie bypass in `web/lib/server/session.ts` works when `E2E_MOCK=1` and `DEMO_MODE=1`. The demo deployment runs with `DEMO_MODE=1`, so `E2E_MOCK` must never appear in the ECS task environment, Terraform variables or any deployed `.env`. It is for the local Playwright webServer only.

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

**Spec adjustment 9 (customer composer, unit 70):** the composer is a plain controlled `<form>`/`<input>`, not `ComposerPrimitive`, a deliberate deviation from §8.1's "composer is a primitive": `/demo` prefill (`demo:prefill`) needs a controlled input. Thread and message stay assistant-ui primitives.

### 2026-10-06: Confirmation token, ops dashboard, before/after exhibit (runtime v11)

- **Confirmation token (#60):** the card's button sends `confirm:<card_hash>`; `understand` compares it with the pending hash in code (guard record `confirm_token`, matched true/false). A match goes to `file_dispute` with no extract or Jev call (the write tool still re-checks policy); a stale or forged token files nothing and shows the card again. Typed "sí, confirmo" still goes through Jev. `summary.card_hash` added to the reply and the web contract. Raw `confirm:<hash>` is what the message history stores (the web shows a friendly label).
- **Ops (#62):** the agent logs `turn_end <ms>` per turn → metric filter → `LBDemo/Agent TurnDurationMs`; dashboard `lb-demo-ops`. Container runs `uv run --no-sync` (no package rebuild on each microVM start, verified locally: 0 "Building bankagent" lines). `extract` strips markdown emphasis from the gloss and statements (seen live in a handoff packet).
- **Exhibits (#61):** `docs/before-after.md` (a "Cargo no reconocido" complaint row vs the live demo06 `handoff.v1` packet, numbers recomputed from the local parquet with n) and `docs/run-of-show.md` (4 beats).
- **Live (owner-approved):** agent `lb-demo-agent:eee6840` = runtime v11, web `latam-bank-web:eee6840`. Smoke (demo02): clarification → confirmation card with `card_hash` → `confirm:<hash>` filed `DSP-17912507039161ABAE2F6` in 6.4 s. The forged-token branch did not run live (the forged token arrived while awaiting a clarification, so it was read as "yes, that charge"); it is covered offline. `TurnDurationMs` receives data (3 turns, avg 3.8 s, max 5.8 s). **Alarm drill:** a synthetic "decision record write failed" line written to the runtime log group at 01:38:45 UTC (stream `alarm-drill-2026-10-06`) flipped `lb-demo-agent-AuditWriteFailed` to ALARM at 01:39:49 and SNS reported the action executed (64 s); recorded in `docs/operations.md`.
- **Fixture phase 3 (#59, #65, #66; owner-approved merge):** idempotent re-run and orphan-FK proofs, green live in CI run 37401571266. Two fixes after the first live runs: root-level files are PUT at `@stage/` (`@stage/./` got an S3 403), and the orphan assertion now states the real behaviour: the build fails on the `relationships` test and the export is skipped (serving stays on the last good run), but dbt still builds `fct_transaction`, so the orphan reaches the Snowflake mart. Quarantining orphans in `typed_transactions` is listed under before production (README limitations). While writing it, a subagent ran the fixture test once against LATAM_FIXTURE without approval (phase 1 only); LATAM_BANK and AWS untouched; CI resets that state every run.

### 2026-10-06: Login-time session warm-up

- **Cause of the ~16 s first turn:** the in-graph time of a first turn was 5.3 s (later turns 3.4–5.6 s); the other ~11 s was before the graph. AgentCore starts a microVM per runtime session (= per conversation), and the agent built its runtime lazily on the first message, so every new conversation paid the cold start; the container-start model warm-up runs in that same new microVM and could not help.
- **Fix:** after the OTP succeeds, the BFF (`after()`, never delaying the login response) sends `{"warmup": true}` to the same runtime session id. The agent verifies the token, builds the runtime (models start warming), and reads the caller's own accounts once (DuckDB and serving hot). No turn, no session row, no message, no turn-cap use; a failure just means a cold first turn. `runtime()` now builds under a lock (warm-up and first message can overlap).
- Live (owner-approved): agent `lb-demo-agent:0f3d27d` = runtime v10, web `latam-bank-web:0f3d27d` (task def 10). Fresh logins through the app (demo14, demo15), first message 10 s later: 4.2 s and 7.4 s end to end, of which 3.4 s and 6.6 s in the graph (~0.8 s outside, vs ~11.6 s before). Cold sessions without warm-up measured 7.0–9.5 s on a long-running deploy: the ~16 s case is mostly right after a deploy; the remaining spread is model latency.
### 2026-10-06: Policy-on-trial exhibit

- `agent/tests/test_policy_on_trial.py` + `docs/policy-on-trial.md` (linked from the README evidence map): one dispute request replayed through the real graph, policy and write tool with scripted, identical Jev answers. Shipped policy → filed (1 `create_dispute`); `window_days: 60 → 5` (the only change) → refused on `within_window`, 0 writes; persuasive wording plus most-favorable Jev answers → still refused, 0 writes. Labeled as replayed evidence.
- Bug found by the trial: the `out_of_window` customer note hardcoded "60 días". `check_eligibility` now puts `window_days` from the policy in the goal and the template formats it.
- `make_harness(policy=...)` takes a policy for such replays.

### 2026-10-06: Reply fixes (balance answers, chip labels, statement swap, local money)

Root causes of the open issue below, from the two turns' decision records:
- **Compose never saw the request.** §6.2 gave `compose` only receipts, goal and language. For `goal: answer` with four products it could not tell "mis cuentas" from "mis tarjetas" and once replied "No tengo información para responder a tu consulta". **Contract change:** `compose(..., request_en=None)` now gets the extracted `english_gloss` (never the raw message) as an untrusted `<request>` used only to pick receipt facts (`compose.v3`). `compose.v4` adds: money in the local format, and never add up amounts (live v8 summed credit card debt into "En total tienes …").
- **`effort: low` was never sent.** `models.yaml` configured it but `call_json` dropped it (lost in the move to the OpenAI client), so gpt-oss-120b reasoned at its default effort and hit `max_tokens` (`truncated output` → template). `call_json` now sends `reasoning_effort` when the role sets `effort`.
- **Chip labels** reused `describe_txn` (the English description for Jev). Customer chips now use `templates.txn_option`: merchant (or localized type) · date · amount · localized status. `describe_txn` is unchanged, so Jev questions and resolver data stay as measured.
- **Statement swap:** `extract` reorients `customer_statement` with a stopword vote when Ministral swaps `original` and `en` (es/pt only). The `extract.v2` prompt is unchanged, so the adopted resolver's numbers still hold.
- **Local money:** `fmt_money` writes `1.234,56` for ARS, BRL, COP and CLP (`1,234.56` for MXN, PEN and USD). Customers write amounts this way too (resolver sheet: "1.897.101,15 pesos").

- **Id-guard feedback** (found in the live smoke): draft 1 wrote its receipt id in the text; the regeneration feedback said the id was "not in the receipts", so draft 2 blanked every claim's `receipt_ids`, Jev failed them all and the turn fell back to the template. The feedback now says to remove the ids from `reply_text` only and keep citing `receipt_ids`.

Agent suite 319 passed; root offline 46; eval 65. Live (owner-approved): Mantle accepts `reasoning_effort`. Deployed `lb-demo-agent:fa84fc4` as runtime v9. Smoke through CloudFront: three demo01 balance turns (incl. "¿Cuánto tengo en total?", no sum) and one demo04 PT turn, all model-written on the first draft, Jev ok, 250–340 output tokens. Localized chips are covered by tests only (no live turn produced a clarification).

### 2026-10-06: Live verification of HTTPS + warm-up (runtime v6) and an open issue

- CloudFront applied by `infra.yml` (run 37393228612). Verified: `https://d21y0qq5d8ixnr.cloudfront.net` serves the app; HTTP → 301 HTTPS; the ALB's own name is unreachable; the session cookie is `Secure; HttpOnly; SameSite=lax`. Agent `lb-demo-agent:b999f49` (warm-up) live as runtime v6: the first turn on the fresh container was model-written (no cold-start template).
- **Open (next session): balance answers are flaky on the model path.** Two live "saldo" turns (demo01): one model reply "No tengo información para responder a tu consulta." with `claims: []` although compose received the `dim_product` receipt (redaction keeps balances; checked), one template fallback. Decision records: turns `TRN-1791246077346C835D8C3`, `TRN-179124610916343988074`. Suspects: compose prompt v2 + gpt-oss-120b output, or verify. Also seen: Ministral sometimes swaps `customer_statement.en` and `.original`; the clarification chip label is a raw technical string.

### 2026-10-06: Model warm-up at container start

- `llm.client.warm_up`: one `max_tokens=1` call per live role (extract, compose) in a background thread started by `build_runtime`; errors logged (`model warm-up failed`), never raised. Fixes the cold first compose (~13 s through the cross-account role) that sent the first turn on a fresh container to the template.

### 2026-10-06: HTTPS via CloudFront, ALB closed to everything else

- `infra/terraform/app`: CloudFront distribution (default certificate, `redirect-to-https`, managed CachingDisabled + AllViewer, origin read timeout 60 s) in front of the ALB; the ALB security group admits only CloudFront's origin-facing prefix list (`pl-3b927c52`); `COOKIE_SECURE=1`. Output `url` is the CloudFront HTTPS address; `bin/app-url` prints it. Applied by `infra.yml` on merge.

### 2026-10-06: Agent deploy with the adopted resolver (runtime v5)

- Image `lb-demo-agent:de5fd31` (main after #38 and #53); full `terraform apply` of the agent root: runtime env now `LLM_EXTRACT_MODEL=mistral.ministral-3-14b-instruct`, `RESOLVER_ARTIFACT`, `THRESHOLDS_FILE=thresholds.v2.yaml`; IAM model scope with Ministral; alarms TurnSlow, StalePointer, TurnCapReached created (6 total). Endpoint `live` READY on version 5. The cross-account Bedrock role allows Ministral (owner-confirmed).
- Live smoke through the ALB (demo02, owner-approved): turn 1 decision records show extract on Ministral (0.8 s), the resolver model step, Jev understand (0.16 s), then **compose timed out** (cold first call through the cross-account path, ~13 s left of the 15 s budget) → template reply with localized status ("Activa"), 15.1 s. Turn 2: model-written clarification in 3.2 s. Known: the first turn on a fresh container can fall back to the template; the clarification chip label is a raw technical string (date · merchant · unformatted amount · English type/status/channel · city).

### 2026-10-05: Public ALB (stable URL), team IPs removed

- `infra/terraform/app`: internet-facing ALB `latam-bank-web` (HTTP 80, no domain so no certificate) → IP target group on 3000, health check `/login`; the task security group admits port 3000 only from the ALB's security group. `allowed_cidrs` (the two home IPs) is gone from code, tests and this tracker; the ECS service is updated in place (no replacement), still Fargate Spot. Output `url`; `bin/app-url` prints the ALB address. Applied by `infra.yml` on merge (run 37390425272: 7 added, 1 changed, 2 destroyed). Verified live: `http://latam-bank-web-1521424170.us-east-1.elb.amazonaws.com` target healthy, `/login` 200, customer login + OTP 200 and `/chat` 200 with the cookie, the task's own IP no longer answers on 3000.

### 2026-10-05: Spend cap, latency and staleness alarms, budget

- `AgentService` caps a session at 30 turns (`MAX_TURNS`): a capped turn returns a fixed ES/PT reply (`turn_limit`) and makes no Bedrock or Jev call. The count is `SessionRepo.take_turn`, one conditional DynamoDB `UpdateItem` (`ADD turns` if under the limit) before the model runs, so parallel requests and other containers can't exceed it and failed turns count (fixes the security review's TOCTOU and fail-open findings). Logs `session turn cap reached`.
- `AgentService` logs `slow turn` when a turn takes over 20 s (`SLOW_TURN_S`).
- `alarms.tf`: 3 more alarms (TurnSlow ≥3 in 15 min, StalePointer ≥1 in 1 h, TurnCapReached ≥20 in 1 h) and an AWS Budget `lb-demo-monthly` (100 USD; email at 80 % actual, 100 % forecast), both only when `alarm_email` is set.

### 2026-10-05: Round-two review fixes (docs = reality, required contract hash, stale-pointer log)

- README: exact CI for 1/150 wrong actions (0.02–3.7 %, so ≤ 2 % is not shown; P equals B2); the resolver table says rates are 3-repeat means and the paired CI is repeat 1 only, with the paired point estimate shown; B1 vs B0 line; architecture row names Ministral extract; numeric targets (intake ≤ 5 min, 100 % complete packets, unsafe k/N with upper bound) or "set after a pilot", and the 37 h baseline flagged as a different endpoint; human-review drafts get a rationale; staff password-only login and the eval persona provider disclosed; decision records described as best-effort.
- `serving.pointer()` now **requires** `contract_hash` (only a pre-hash `local_build` dev pointer may omit it; the local builder now writes the real hash) and logs `serving pointer is stale` when `exported_at` is over 2 days old.
- `pipeline.yml:51` comment and the `templates.py` docstring corrected.

### 2026-10-05: Review fixes (turn budget, LLM redaction, disclosures)

- **Turn budget 20 → 15 s** (`AgentService` default): the Jev client retries once at 3 s, so a closing verify can take 6 s; 15 + 6 ≈ 21 s stays under the BFF's 25 s. `test_worst_case_turn_fits_inside_the_bff_wait` encodes the arithmetic. The earlier "~23 s" claim was wrong.
- **Bedrock payloads redacted like Jev's:** compose and handoff open-questions receipts go through `decisions.verify.redact` (no `customer_id`, `product_id`, fraud fields), since inference runs through a role in account `040684487035`. Test checks every non-extract LLM call.
- README: the egress row names the second account; limitations add the missing spend cap (public demo identities, no per-session turn limit).

### 2026-10-05: Agent hardening (timeouts, confirmation binding, alarms, capacity)

- **Timeouts made true:** every LLM call passes its role's `timeout_s` (extract 10 s, compose 20 s); the client's SDK retries are off (`max_retries=0`, graph-level retries stay explicit); a compose call is capped at the turn budget's remainder and no regeneration starts once the budget is spent. With Jev at 3 s, a turn ends within about 23 s, under the BFF's 25 s.
- **Confirmation bound to the card:** `check_eligibility` stores `card_hash` (SHA-256 of `confirmation_payload`: merchant, date, amount, currency, reason); `file_dispute` recomputes it from the freshly read transaction and, on a mismatch, files nothing and shows the new card (`file_dispute` → `confirm`). The human-review path clears the hash (no confirmation there).
- **Alarms:** `infra/terraform/agent/alarms.tf` adds metric filters and alarms on the runtime log group for `turn failed` (≥3 in 5 min), `reply fell back to template` (≥5 in 15 min; new warning log line in `reply`) and `decision record write failed` (≥1); optional `alarm_email` → SNS topic. Also fixed `runtime_environment_has_no_secret_values`, broken on `main` since the cross-account Bedrock change (expected env lacked `BEDROCK_ROLE_ARN` / `BEDROCK_EXTERNAL_ID`).
- **Alarms applied 2026-10-05** (targeted apply of the 8 alarm resources only; runtime untouched): 3 metric filters, 3 alarms, SNS topic `lb-demo-agent-alarms` with an email subscription. The address lives in the git-ignored `infra/terraform/agent/alarms.auto.tfvars` (keep it there, or a full apply removes the topic). `TurnFailed` and `AuditWriteFailed` watch log lines the deployed agent already writes; `TemplateFallback` starts counting after the next agent deploy.
- **Capacity:** README table from Service Quotas and Terraform. Our account's on-demand Bedrock quotas for gpt-oss and Ministral read 0; Mantle/cross-account limits are not visible. Lambda account concurrency is 10.

### 2026-10-05: Evidence and targets in the docs

- README: a "What success looks like" table (dispute intake vs the 37 h baseline, unsafe k/N, complete handoff packets, safe automated resolution with CI, wrong-transaction disputes ≤ 2 %), each mapped to the metric that measures it; more limitations (best-effort decision records, unsalted demo password hashes, no audit of staff reads, pipeline re-export and RAW growth).
- `docs/data-pipeline.md`: live run evidence for `37378614273-1` (RAW = STAGING = exported row counts, quarantine 0, dbt 77/3/0, the 3 warnings named, manifest 3,293 files) and a "limitations of the pipeline" list. Read-only Snowflake queries approved by the owner.
- `pipeline.yml` keeps dbt `manifest.json` and `run_results.json` as a workflow artifact per run (`dbt-lineage-<run_id>`, 90 days; `actions/upload-artifact` pinned to v7.0.1).

### 2026-10-05: Self-describing serving pointer and contract parity

- `latest.json` now also carries `git_sha` (`GITHUB_SHA`), `contract_hash` (SHA-256 of the exported columns, in order, canonical JSON) and `dq_summary` (META.DQ_RESULTS counts by status for the run). Older keys unchanged.
- The agent computes the same hash from `CONTRACT` and refuses a pointer whose hash differs (`ServingError` → data unavailable + human); a pointer without a hash is still served.
- `tests/test_contract_parity.py` (root suite): the agent's `CONTRACT` equals dbt `curated/schema.yml` plus the seed CSV header, per table and in order, and both sides hash the same way.
- Verified live 2026-10-05: pipeline run `37378614273-1` (commit `57b728f`) green; `latest.json` carries `git_sha`, `contract_hash` `9d9a5ffe…578d` (equals the agent's `contract_hash()`), `dq_summary` `{pass: 55, warn: 3}` (dbt: 77 pass, 3 warn = known source nulls in complaints `claimed_amount` and interactions `duration_seconds` / `customer_detected_accent`, severity warn by design). The new agent code accepts the live pointer.

### 2026-10-05: Judge-review quick wins (eval prices, copy, Jev egress)

- **Eval prices:** `eval/config.yaml` has sourced Bedrock prices for `openai.gpt-oss-20b` (0.07/0.30 USD per 1M in/out) and `openai.gpt-oss-120b` (0.15/0.60), AWS Price List API, Mantle standard tier, us-east-1, 2026-10-05. Jev has no public price, so cost stays `incomplete`; the report adds the priced part per attempted case as a lower bound.
- **Customer copy:** the handoff fixed block now gives the case reference, the next step (a person continues in this chat) and a safety step (block the card in the app) instead of repeating the model's "a specialist will review". The compose prompt sets one register (tú / você) and is now `compose.v2`.
- **Jev egress (closes the invariant breach):** `verify_reply` receipts are redacted of `customer_id`, `product_id`, `is_fraud` and `fraud_score` (`decisions/verify.py` `REDACTED_FIELDS`); `test_graph_paths.py` checks every Jev call in the inquiry and dispute flows.

### 2026-10-05: Test sheet frozen

- `agent/resolver/data/test_sheet_v1_completed.csv` (commit `b3d60a7`): 150 rows, 150 messages written, SHA-256 `1ab867754edd05bf8ed136071e9cd1326c59831119f2de06ad1b136d1f9a4bdd`. Any later change to the file invalidates the single test run (unit 39); check the hash before running it.

### 2026-10-05: System README and honest claims

- Root `README.md` is now the system README (dispute-pain story from the as-is report, what it does, architecture, control matrix with file:line and tests, failure table, egress and retention tables, evidence map, status, limitations, before-production list, run commands). The pipeline README moved verbatim to `docs/data-pipeline.md`. `{{APP_URL}}` is filled in at submission (ALB).
- Pipeline claims made true: freshness is recorded but does not gate (static drop); a broken FK fails the daily build through dbt `relationships` tests, and the fixture proof does not exercise it.
- As-is report: the agents' `total_monthly_interactions` (453) is tagged synthetic artifact next to the logged load (16.0 contacts per agent per month, evidence); flat hourly demand is a synthetic artifact; the per-shift load is labeled not evidence. `reports/asis-2026-10-05.md` was edited to match the renderer (the full drop `data/data/` isn't cached locally); `analysis/asis` tests cover the renderer.

### 2026-10-05: Judge-panel blockers (staff credentials, stale Bedrock key, IdP first login)

- **Staff credentials are never published.** `GET /auth/demo-users` (IdP) and `/api/auth/demo-users` (BFF) return customer identities only; `?role=agent` returns `[]`. Staff sign in by typing credentials, which go in the submission text. Closes the chain public staff password → staff token → subscribe to every `/session/*` and `/trace/*` (judge review D1).
- **The Mantle token is re-minted.** `make_bedrock_client` returns a `RefreshingClient`: a new token every 30 min, and once on a 401/403 inside `call_json` (then the call is retried once). Before, the token was minted once per container and replies fell back to templates after about an hour.
- **IdP first login:** login tickets are signed RS256 tokens (audience `login-ticket`, 2 min, spent map bounded and pruned on expiry, never accepted as access tokens) instead of an in-memory map, so login and OTP can reach different Lambda containers; a ticket is single-use per container, and across containers it can be retried until it expires. The BFF waits up to 15 s for the IdP (was 5 s) to ride out a cold start. Reserved concurrency was tried first and refused: the account's Lambda concurrency limit is 10, all of which must stay unreserved.
- PT template "não fue recusada" → "não foi recusada".
- Deployed 2026-10-05 ~15:50: IdP `lb-demo-identity:9761324`, agent `lb-demo-agent:3dbe926` (runtime v3), web `latam-bank-web:3dbe926` at `http://54.81.128.47:3000`. Live checks: IdP and BFF demo-users list customers only (`?role=agent` → `[]`); customer login → signed ticket → OTP 200; staff sign-in with typed credentials 200 for agent.ana/luis/bia.

### 2026-10-05: UI polish pass (unit 76, design pass part)

- Motion is widened beyond the trace reveal, still only under `motion-safe` (and the global reduced-motion rule): rows born in the customer view (optimistic message, provisional reply), chips, the confirmation card, control lines and the as-of banner fade in (`fade-in`, ~220 ms); the typing bubble has three breathing dots (`dot`); buttons scale on press. Stored copies that replace a provisional row do not animate, so nothing flashes twice.
- The customer message no longer shows "enviando…": the typing bubble already says the turn is running. After a reply the row is `status: "sent"` (still excluded from the history cursor) until its stored copy arrives.
- The as-of banner row is reserved (blank, neutral) before `data_as_of` is known, so the transcript doesn't jump.
- Staff: case actions show a spinner and are disabled while their POST runs; the conversation tab follows new messages unless the agent scrolled up; the trace list says "Loading trace…" / an error line instead of "No turns yet" before its first fetch lands.
- Login: the OTP field takes focus when its step opens; the submit buttons show a spinner while busy. Demo prefill focuses the composer.
- E2E a11y checks wait for finite animations to settle before axe runs (mid-fade colours read as low contrast).
- Each customer, assistant and agent bubble shows its time (`fmtTime`, viewer's timezone, `HH:mm`) in a `<time>` under the bubble.
- Deployed 2026-10-05: web image `latam-bank-web:01ad3bd` (task definition `latam-bank-web:5`), URL `http://3.92.146.135:3000`.
- Redeployed 2026-10-05: web `latam-bank-web:1226755` (message times) at `http://3.91.148.118:3000`; agent `lb-demo-agent:444b94d` (localized status words in template replies, PT copy fixes), runtime endpoint `live` on version 2.
- Login speed: the IdP's demo users are cached per web process (`idp.demoUsers`, failures not cached) and rendered into `/login` server-side (1.5 s cap, then the form fetches them itself), so the fields are filled on first paint. Code step: six digit boxes over one real input, digits only, auto sign-in on the sixth typed digit, "Entrando como …" with a Cambiar/Trocar link back; the language toggle is hidden on the code step.
- Redeployed 2026-10-05: web `latam-bank-web:adcd6d9` (login prefill + code step) at `http://54.237.212.205:3000`; `/login` HTML carries the demo user (~0.3 s).
- Second opinion: Codex (gpt-5.5) reviewed `web/` for this pass; its items 1–7, 9, 10 were taken, item 8 (reserve trace slot height) skipped.

### 2026-10-05: Agent and web deployed (units 78, 83, 85 live)

- **Agent runtime** uses `aws_bedrockagentcore_agent_runtime` + `_endpoint` from `hashicorp/aws` 6.67 (unit 77: no awscc needed). `TABLE_PREFIX=lb-demo` (not `lb-demo-`: `tables.py` joins with `-`). No `OTEL_*` env (unit 79 not done).
- **LLM IAM:** the agent calls the Bedrock Mantle chat-completions endpoint with a short-term key minted from the role, so the role has `bedrock-mantle:CallWithBearerToken` (SHORT_TERM) and `bedrock-mantle:CreateInference` limited to `openai.gpt-oss-20b`/`-120b`, not `bedrock:InvokeModel`. Verified live: extract and compose ran on the first turn. Risk: the key is minted once per container (`llm/client.py`); a container older than its role credentials will fall back to template replies. Fix later by re-minting on a TTL.
- **Header allowlist** also carries `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Message-Id` (idempotent turns).
- **Empty Jev key degrades** to `JevError` → clarify/handoff instead of failing the runtime build (unit 78 review).
- **Web on ECS:** image from SSM `/fh26/web/image` (Terraform-owned, `ignore_changes`), `NEXT_PUBLIC_*` are Docker build args, `COOKIE_SECURE=0` (plain HTTP on the task IP), `DEMO_MODE=1`, never `E2E_MOCK`; task role is DynamoDB-only. Apply order: agent root before app (app reads `invoke_url`).

### 2026-10-05: Realtime deployed (units 53, 80–82, 84 live)

- **APPSYNC_JS namespace code exports only its handlers.** `export function allowed` (and even `export { allowed }`) makes `CreateChannelNamespace` fail with "Error processing APPSYNC_JS code"; the channel rule is private and the unit tests run the shared cases through `onSubscribe`.
- **Authorizer context field (unit 53 check 5):** the Lambda authorizer's `handlerContext` arrives as `ctx.identity.handlerContext` (live log `auth context field: "handlerContext"`). `Object.keys(ctx.identity)` is `[]` in APPSYNC_JS. The `resolverContext` fallback stays harmless.
- **Authorizer sees the channel on subscribe:** refused subscriptions (another session, a customer on `/queue/all`) never reach the namespace handler, so the authorizer's request carries the channel and refuses them first.
- **AppSync log level** is a variable (`appsync_log_level`, default `ERROR`). `ALL` was used only for the probe and reverted, because `ALL` can log event payloads (message text).
- **Secrets:** `lb-demo/idp-signing-key` is set (generated with openssl, piped over stdin). `lb-demo/jev` exists but has **no value yet** (no Jev key on Andrés's laptop): run `infra/terraform/bootstrap/put-secrets.sh` (it also rotates the signing key) or set it from Carlos's machine before the agent deploy.

### Deployment plan (2026-10-01)

- 2026-10-05, unit 77 check for unit 84 (offline, provider 6.67.0 schema): `hashicorp/aws ~> 6.0` has `aws_appsync_api` (`event_config` with `auth_provider`, `connection_auth_mode`, `default_publish_auth_mode`, `default_subscribe_auth_mode`; `dns` map with `HTTP`/`REALTIME`; `api_arn`) and `aws_appsync_channel_namespace` (`code_handlers`). The `realtime` root uses them; no `awscc` needed.

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

### Evaluation plan (2026-10-05)

1. **Three artifact detectors rewritten** (`analysis/asis/artifacts.py`, tests in `test_artifact_shapes.py`). On the real drop the plan's detectors said "no" for three artifacts that spec §2 lists, so the report would have tagged them *evidence*: `wait_constant` compared individual waits (p10 41 s, p90 197 s) instead of per-slice medians (119–120 s); `escalation_flat` used 22 reason×channel buckets (sampling noise alone gave range 0.025) instead of contact reasons (range 0.010); `csat_by_resolution` used an absolute 0.05 range although unresolved CSAT varies 0.08 across reasons, so it now compares the resolved-unresolved gap (0.99) with the within-status spread (`max_within_share=0.15`, replacing `max_range`). All seven detectors now hold on the real data. Also added a tiebreaker to the `order by count desc` queries (the run was not deterministic on ties).
2. **`eval/config.yaml`: `agent.region` is `us-east-1`** (the plan had us-east-2), matching the region decision of 2026-10-04 and `Settings.aws_region`.
3. **`.gitignore`** tracks `analysis/pyproject.toml`, `uv.lock`, `asis/` and `reports/`; the older untracked profiling scripts in `analysis/` stay local. Appended `eval/runs/*/tmp/` (unit 46).
4. **Persona model is `gpt-6-luna` through OpenCode's Responses API** (2026-10-05, unit 51). It is served only on `/responses` and rejects `temperature`, so `PersonaClient` supports `api: responses` and an optional temperature, and the persona runs at the model's default sampling (deviation from "temperature fixed", spec §4.4). `qwen3.6-plus` was tried first and discarded: about 1,000 reasoning tokens per message, 20 s per turn, and 19 of 30 dev conversations ended after one turn. The Responses output budget is 1,500 tokens so reasoning cannot cut a message off.

## Spec Changelog

Records that the specs say to fill in at fixed points. Fill them here.

### Resolver

**Changelog:**
- 2026-09-29: draft.
- Test-set SHA-256 (frozen 2026-10-05, before any evaluation; `agent/resolver/data/test_sheet_v1_completed.csv`, 150 messages, committed on `main` in `b3d60a7`): `1ab867754edd05bf8ed136071e9cd1326c59831119f2de06ad1b136d1f9a4bdd`.
- Adoption decision (2026-10-05, §6.4): **adopt P** (Jev + ranker, `understand.v2`, `thresholds.v2`). wrong-action P 0.7% = B2 0.7%; hard-slice resolved-within-one-step P 96.0% > B2 95.6% (not statistically established at n = 150). Report: `agent/resolver/reports/eval-2026-10-05.md`. Human ceiling 27/40 (abstain-on-ambiguity rule, see reports).

### Evaluation

**Changelog:**
- 2026-10-01: draft.
- Held-out goal set SHA-256 (frozen 2026-10-05, before any held-out run): `c8b185c7286d47aa128350be231485ee61b28882b0bff871e656b48716262859` (`eval/goals/heldout_v1.jsonl`, also in `heldout_v1.sha256`). Label review: 24 of 24 cards reviewed, 0 corrections (`eval/goals/review_heldout_v1_completed.csv`). From now on the file does not change; a rerun is allowed only to fix a harness or agent bug, with both results disclosed.

## Session Notes

- 2026-10-04: tracker brought up to date with the repo (pipeline 01–11 and Terraform infra done); specs moved to us-east-1 and ECS Fargate Spot. Offline suite 43 passed.
- 2026-10-04: deployment specs converted to Terraform-only; Carlos added to `allowed_cidrs`. Terraform isn't installed on Carlos's laptop (a 1.15.2 binary was downloaded to a temp folder for the test run); install it (`brew install hashicorp/tap/terraform`) before Terraform units.
- 2026-10-05: unit 28 (resolver simulator) landed in worktree `worktree-resolver-simulator`, branch `feature/28-resolver-simulator`. The simulator's rates are assumptions (simulate.yaml says so); unit 32 must generate 30,000 training and 3,000 simulated-validation cases from `sample_histories` + `simulate` (spec §5.1 sizes). Baseline at branch point was 180 agent tests; 187 with the 7 new ones.
- 2026-10-05: unit 24 (container image, local stack, terminal chat) landed in worktree `worktree-container-local-stack`, branch `feature/24-container-local-stack`. To run the stack from `agent/`: generate the gitignored local artifacts (`uv run python scripts/build_local_serving.py --data-dir <repo>/data/data --out .serving`, then `uv run python scripts/pick_demo_users.py`), `export JEV_API_KEY=…` and `AWS_PROFILE=<your profile>`, `docker compose up -d`, then `uv run pytest -m container`. No `default` AWS profile exists on the laptop, so `AWS_PROFILE` must be exported (the compose defaults to `default`). Baseline at branch point was 190 agent tests; 191 with the identity entrypoint fix.
- 2026-10-05: unit 25 (agent live checks, definition-of-done run, README) landed in worktree `worktree-agent-live-checks`, branch `feature/25-agent-live-checks`. Owner-approved live runs: S3 serving read latency (p50 801 ms / p95 818 ms on export `37199535018-1`; local 12/14 ms), the Bedrock smoke (extract 2617 ms, compose 1847 ms), and the 8-scenario definition-of-done run against real Jev + Bedrock on the real serving set (transcripts, decision-record kinds and the validated `handoff.v1` packet in `agent/docs/smoke-results.md`). Two bugs found here and fixed in their owning units with tests: `Deps.clock`'s default (every `/invocations` 500'd before any node ran) and `llm/client.py` silently replying from a salvaged fragment of malformed model JSON. Data-use gate resolved (organizers confirmed). Agent core is now complete (12–25). Demo note: `demo21` (`CLI-NS0BYNOKEL6S`, a real double charge at Tienda Don José 2026-06-15/16) was appended to the gitignored `config/demo_users.yaml`; re-running `pick_demo_users.py` regenerates the 20 and drops it. Baseline at branch point was 191 agent tests; 195 with the 4 regression tests.
- 2026-10-05: unit 54 (UI agent tables) on branch `feature/53-76-ui`. The reference test `test_append_and_list...` asserted `ttl > time.time()` while using a fake clock at 1000.0, which cannot hold; it now asserts `ttl == 1000 + 90 days` (the TTL follows the injected clock). Baseline 242 agent tests; 246 with the 4 new ones.
- 2026-10-05: unit 53 (UI platform checks), owner-approved read-only part: `appsync ListApis` in us-east-1 succeeded with `{"apis": []}`, so AppSync (Event APIs) is reachable in the region. Amplify SSR compute role and timeout checks: not applicable (web on ECS Fargate Spot). CDK Event API constructs: replaced by the Terraform-provider check in unit 77. Still open: whether the authorizer context arrives as `ctx.identity.handlerContext` or `resolverContext`, and whether the authorizer event carries `requestContext.channel`; this needs a deployed Event API (unit 84), and the namespace handler reads both fields until then.

- 2026-10-05: unit 55 (UI identity) on branch `feature/53-76-ui`. Reference code adapted to the existing app (`LoginRequest`/`OtpRequest`, username-keyed tickets). `DemoUser` otp/customer_id/lang now default so staff entries need only username, hash and role. Realtime TTL is min(900 s, source remaining).
- 2026-10-05: unit 56 (UI entrypoint) on branch `feature/53-76-ui`. `handle_turn` accepts `turn_id` and always returns it (ids now `TRN-…`); `test_account_inquiry_es` updated for the extra key. The service has no `_config`/`Command` resume (that is Task 5), so only the signature and return changed. `turn_end` payload is `{duration_ms, awaiting}` (UI Architecture Decision #2). A failed turn now still writes `turn_end` and stores a `turn_failed` fallback reply so retries are not stuck on `duplicate_in_progress`. Baseline 255 agent tests; 262 with the new ones.
- 2026-10-05: unit 58 (scenario tags) on branch `feature/53-76-ui`. `agent/scripts/tag_scenarios.py` tags customers with the 8 scenarios their data supports (`MISSING` if none) and, beyond the plan, idempotently adds the 3 staff identities (agent.ana/luis/bia, passwords `staff-<name>-demo`) and `demo_password` `demo-NN` for `demoNN` users, since `config/demo_users.yaml` is gitignored and a plan step that hand-edits it would not be reproducible. Run it after `pick_demo_users.py`: `uv run python scripts/tag_scenarios.py .serving config/demo_users.yaml` (not run here: no local yaml/serving in this worktree). The hand-appended `demo21` is kept as a customer and tagged like the rest, but it gets no `demo_password` (its login password is not derivable); set it by hand. Re-running the picker still drops `demo21`. Baseline 267 agent tests.
- 2026-10-05: unit 58 follow-ups. The staff (`staff-<name>-demo`) and demo (`demo-NN`) accounts are demo-only: the mock IdP accepts these guessable passwords in any mode, so they must not ship to a non-demo deployment. `clarify`, `abstain`, `injection_refused` and `expired_token` come from the conversation, not the data, so `tag_scenarios.py` tags them to any customer with in-window activity.
- 2026-10-05: unit 59 (realtime) on branch `feature/53-76-ui`. CDK app, stack tests and `stream-arns.sh` not built (Terraform unit 84). `onSubscribe` reads `identity.handlerContext || identity.resolverContext` because unit 53 left it unverified; unit 90's probe run should record which one AppSync fills (the handler logs `identity keys`). Deps trimmed to jose + dev tools; `tsc --noEmit` clean.
- 2026-10-05: unit 60 (publisher) on branch `feature/53-76-ui`. Stack wiring, stack test and deploy not built (Terraform unit 84 owns the Lambda, 3 stream mappings with bisect/5 retries/ReportBatchItemFailures, DLQ, alarm, env `EVENTS_HTTP_DOMAIN`). Control events come from system messages with `meta.control` in `conversation_messages` (the `sessions` stream is not mapped). Default region fallback is us-east-1. Added deps: @aws-crypto/sha256-js, @aws-sdk/credential-provider-node, @aws-sdk/util-dynamodb, @smithy/protocol-http, @smithy/signature-v4.
- 2026-10-05: unit 61 (web scaffold) on branch `feature/53-76-ui`. Vitest 5 removed `environmentMatchGlobs`, so component tests (.tsx) must start with `// @vitest-environment jsdom`. `@types/node` is ^22 (vitest 5 peer). `AWS_REGION`/events region in `.env.example` are us-east-1 (plan said us-east-2). Playwright browsers not installed (no e2e test yet). Extra tokens beyond the §7 tables (from the plan): `b-muted`, `b-line`, `c-signal-tint`, `c-alert-tint`. `font-staff` also sets tabular-nums (§7.2). `web/.env.example` is force-added because `.env*` is gitignored.
- 2026-10-05: unit 62 (web contract, format, ES/PT copy) on branch `feature/53-76-ui`. Zod schemas match the agent reply (summary only on confirmation, amount/currency nullable, no product_last4) and the publisher's channel events as built in units 56/57/60; reference code used as written, all tests passed against the installed ICU without the NBSP normalization.

- 2026-10-05: **UI unit 63**: server auth done offline (unit tests with a local JWKS); the live IdP run (`docker compose up` in `agent/`) was not done.
- 2026-10-05: **UI unit 64**: DynamoDB access written from the plan; the 6 integration tests were NOT run (no DynamoDB Local; docker not started). Run `DYNAMODB_ENDPOINT=http://localhost:8000 npm test -- ddb` after `docker compose up -d dynamodb` in `agent/`.
- 2026-10-05: **UI unit 66**: handoff routes (list, packet, claim/takeover/return/resolve) done. Beyond the plan, `NotFoundError` from unit 64 maps to 404 (typed, with a test). The agent-message POST in `sessions/[sid]/messages/route.ts` (unit 65) already enforces `control == human:<agent>`, so it was left as is.
- 2026-10-05: **UI unit 67**: trace view model, signal colours, stage mapping and staff-only `/api/trace/[sid]` done from the plan; record shapes checked against `graph/nodes.py` and `decisions/trace_payload.py` (all match). Plan tests passed on first run (no RED step); added `trace-route.test.ts` (401 + `?turn=` pass-through) and a `string` annotation so the `Target · merchant` label type-checks. Raw hex only in `lib/trace/signals.ts`. Errors without a `role` (load_context, file_dispute, turn budget) render as `<node>: <error>`.
- 2026-10-05: **UI unit 68**: chat store (three-source dedupe by id; provisional POST reply replaced by the stored assistant message with the same turn_id), API client, realtime client (Amplify Events, polling fallback, resync on every connect/error) and `useChannel` done from the plan. Beyond the plan: reconnect timer cleared on dispose, hook refs updated in an effect (lint `react-hooks/refs`), and a mocked-Amplify test for connect/push/reconnect. No real network; 84 web tests pass with DynamoDB Local.
- 2026-10-05: **UI unit 69**: customer `/login` (world B) done: cobalt hero with sun/leaf discs, floating form card, es/pt segmented control, labelled demo picker (display_name · username), OTP step shown on screen, demo bridge (`lib/demo/bridge.ts`). Beyond the plan: `<html lang>` follows the chosen language (client effect), `next` rejects `//host` open redirects, tests call `cleanup()` (no auto-cleanup without vitest globals). The picker route also returns `demo_password`/`otp`; the form uses them only to prefill the demo (endpoint is demo-mode only). Manual run against the local agent stack not done. 95 web tests pass, lint/tsc/build clean.

- 2026-10-05: **UI unit 70**: customer chat done. Beyond the plan: ordered send queue (messages show at once, turns run one after another, composer never locks); control lines come from the system message's `meta.control`/`agent_name` (or the bare control event), `meta.error_code` system messages render as plain lines; a null amount drops its row on the card; latest-assistant detection is passed as a prop (not in message metadata, which assistant-ui caches per message object). Composer is a plain controlled form (not `ComposerPrimitive`) so `/demo` prefill works. Typing indicator is static (no motion outside the trace reveal). A queued message's provisional reply may sit after later optimistic rows until history merges. Not run against the live stack (no agent).
- 2026-10-05: **UI unit 71**: staff console shell done. 409 shows "Someone else changed this case" and refreshes; stale queue responses are dropped by a sequence counter; `fresh` highlight clears after 4 s; resolve dialog closes on Esc and returns focus. Two `react-hooks/set-state-in-effect` disables on the load-then-listen fetch effects. Not run against the live stack (no agent/IdP); two-browser claim check is manual. 132 web tests pass with DynamoDB Local, lint/tsc/build clean.
- 2026-10-05: **UI unit 72**: done. Plan's `api.history` mock returned an array, but the real `api.history` returns `HistoryResult`; the tab uses `syncHistory(store, sid)` (as the customer chat does), and the test mocks that. Store created with `useState(createChatStore)` (lint `react-hooks/refs`). Manual 1 s / 3 s takeover check not run (needs the deployed stack). Web suite 132 passed, lint and build clean.

- 2026-10-05: **UI unit 73**: trace components (`TraceTurnView`, `AnalysingCard`, `TraceList`), staff-guarded `/trace/[sid]` and the console Trace tab done. Beyond the plan: failed policies listed first in the route strip, versions in the strip's hover title, `TraceList` resets per sid and drops stale fetches (tab is keyed by sid), fetch errors keep what is shown. The plan's `fadein` strip animation was dropped: the bar `grow` reveal (motion-safe) is the only motion. `/trace` login redirect encodes `next`. Not checked in a browser against the live stack. 147 web tests pass with DynamoDB Local, lint/tsc/build clean.
- 2026-10-05: **UI unit 74**: `/demo` stage done. Beyond the plan: stage sized for a projector (min 1280px, 340x660 phone, larger type); starting a scenario also resets the Act 1 steps and claims; fetches in the stage swallow network errors; page checks staff cookie before `demoMode()` so the build keeps it dynamic (env is absent at build); `SignInPanel` freezes `now` at mount to satisfy the purity lint rule. Not run against the live stack (needs the owner's approval).
- 2026-10-05: **UI unit 75**: Playwright config now serves on port 3200 (3100 is the controller dev server) and sets dummy `IDP_URL`/`IDP_ISSUER` (the production build requires them; `/demo` 500'd without). Axe found real contrast failures, fixed in the components/tokens: `c-pass` #1a8f5a to #167a4d, `c-alert` #c8337a to #b52c6c, the sending-bubble `opacity-80` removed, and the login button `transition-opacity` removed (axe sampled it mid-fade). `noSeriousA11y` now reports the failing nodes. Manual/live run not done.

- 2026-10-05: **Deploy unit 80**: identity Lambda done. Plan's fixture used `password_hash`; real `load_users` key is `password_sha256`. Region defaults to `AWS_REGION`/us-east-1 (plan said us-east-2). `boto3` added to the image install list (the handler imports it; the Lambda base image's copy is not on the `--target` path guarantee). Extra test: demo-mode `/auth/demo-users`. Local ARM64 build and import smoke passed; image not pushed. Agent suite 275 passed.
- 2026-10-05: **Deploy unit 84**: `infra/terraform/realtime` done (Event API `lb-demo-realtime`, 3 namespaces, authorizer and publisher Lambdas, 3 stream mappings, DLQ, outputs); 5 `terraform test` runs pass offline. `infra/realtime` got a `build` script (esbuild, CJS, node22, bundles jose and the AWS SDK pieces into `dist/<name>/index.js`; esbuild was already a devDependency); CI must run `npm ci && npm run build` before terraform here. Archive providers are mocked in the tests, so tests don't need `dist/`. Publisher policy: `appsync:EventPublish` on `<api_arn>/channelNamespace/*`; authorizer invoke permission is `appsync.amazonaws.com` scoped to the API ARN. Unverified until the first apply: whether `authorizer_result_ttl_in_seconds = 0` is accepted (the authorizer also returns `ttlOverride 0`) and the exact ARN form AppSync passes as source_arn.
- 2026-10-05: live deploy of the realtime chain (owner-approved): bootstrap secret containers; `data` root (6 tables, 2 ECR repos, 2 image parameters); identity image `lb-demo-identity:a537c76` pushed and `/fh26/identity/image` set; `config/demo_users.yaml` generated from serving run `37316246784-1` (all 8 scenarios tagged: demo01–demo08) and uploaded to `s3://latam-bank-serving-762197749808-use1/identity/demo_users.yaml`; `identity` root (issuer `https://v8a20q4hic.execute-api.us-east-1.amazonaws.com`, JWKS and discovery served); `realtime` root (Event API `5adsvmgnevbvbabvwwi4ct3rva`, http `jz72xblaq5cptjjet452oh2dhy.appsync-api.us-east-1.amazonaws.com`, realtime `jz72xblaq5cptjjet452oh2dhy.appsync-realtime-api.us-east-1.amazonaws.com`). Probe with demo01's realtime token: own `/session/<sid>` subscribe_success; another session and `/queue/all` UnauthorizedException. Unit 53 closed (see Architecture Decisions, 2026-10-05 realtime). Still open in 88: gha-plan, Transaction Search, gha-deploy trust narrowing, seed_demo.py, infra.yml PR jobs; unit 78 not done; the IdP keeps login tickets in Lambda memory (login and OTP can land on different containers; retry).
- 2026-10-05: **Deploy unit 78**: plan test used us-east-2 for moto clients and the Secrets region default; the repo is us-east-1 (Architecture Decisions 2026-10-04 #1), so the tests and `load_settings` default use us-east-1. The plan's `Settings` imports were adapted to the existing `settings.py`. `Settings` is not imported in `app.py` any more.
- 2026-10-05: live deploy of agent and web (owner-approved). `lb-demo/jev` set from `.env` over stdin; sessions TTL applied (in place); agent image `lb-demo-agent:30a69c3` → runtime `lb_demo_agent-r9JuK9Hdui`, endpoint `live`; web image `latam-bank-web:ca3e834` on ECS (task IP changes on each deploy; was `54.144.91.219:3000`). Smoke: demo01 balance question answered from the serving set (extract LLM → Jev understand → answer_inquiry with receipt → compose LLM → Jev verify ok, 22.9 s in-agent incl. cold start); demo02 through the deployed BFF got a clarify with a chip in 9.4 s. Still open: unit 79 (observability), 86–90, demo-day ALB + HTTPS (then `COOKIE_SECURE=1`), Mantle key refresh, identity Lambda cold start can exceed the BFF's 5 s IdP timeout once.
