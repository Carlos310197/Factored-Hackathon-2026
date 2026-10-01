# Code Standards

Read **General** and **Testing and Live Calls**, then only the subsystem section for the code you're touching. Each subsystem section is copied word for word from that plan's "Global Constraints", and they're binding. Paths inside them that start with `docs/superpowers/` now live elsewhere; see `ai-workflow-rules.md` → Path Mapping.

## General

- Keep modules small and single-purpose: one unit per responsibility, named after the responsibility, not the technology.
- Fix root causes; don't layer workarounds on top.
- Respect the system boundaries and invariants in `architecture-context.md`.
- Validate unknown external input at the boundary: Zod in TypeScript; typed parsing and validation in Python. Invalid responses are errors, never approval.
- Every versioned artifact (question sets, thresholds, prompts, policy, models, goal sets) carries its version, and every record that used it stores that version.
- Labeled synthetic material (policy, demo identities, fixtures, seeds) says so in the file.
- Don't add behavior the specs don't define. Ambiguities go to `progress-tracker.md` → Open Questions.

## Testing and Live Calls

- Default test commands are offline and must stay that way: `uv run pytest` in each Python project; `npm test` in `web/` and `infra/realtime/`.
- Tests that need real services carry markers (`live`, `container`) or flags (`--live`) and are excluded by default.
- Anything that calls Jev, Bedrock, the persona model, S3 or other real AWS resources runs **only after the owner explicitly approves that run**.
- A unit is done only when its tests pass and the review-focus cases listed in its feature spec are pinned by tests.
- Every task ends with one commit that stages only that unit's files, never `.env*`, and ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

### Testing requirements from the specs

#### Testing · agent-core §10

- **Unit tests (offline, pytest):**
  - the policy table (every rule, pass and fail);
  - the routing function (Jev answers and thresholds → edge);
  - JWT verification (expired, tampered, wrong audience, missing scope);
  - tool ownership (`not_found` equivalence) on a small labeled synthetic parquet fixture;
  - `handoff.v1` schema validation;
  - ES/PT templates;
  - the output check against leaked ids.
- **Graph scenario tests with stubbed Claude and Jev, against DynamoDB Local.** Each asserts on final state, store contents and decision records. Scenarios: the three required paths in both languages, plus:
  - multi-intent;
  - confirm → pause → resume;
  - `modify` during confirmation;
  - duplicate dispute;
  - injection attempt;
  - Jev down;
  - session expired mid-conversation;
  - amount over the limit.
- **Live smoke tests** (marked; run manually, each only with the owner's approval):
  - one Jev request with synthetic state;
  - one Bedrock call per role;
  - DuckDB reading from the real serving bucket, with latency recorded.
- **Container contract test:** the ARM64 image answers `/ping` and `/invocations` locally as AgentCore expects.

Quality metrics (automated resolution, containment, escalation quality, unsafe outcomes, latency and cost by language) belong to spec 2.

#### Testing · resolver §7

**Unit tests (pytest, offline):**
- **`features.py`:**
  - an accent-insensitive merchant matches;
  - the local vs USD amount path;
  - inside vs outside the date range;
  - a hint mismatch gives −1;
  - an absent mention gives 0.
- **`simulate.py`:**
  - the same seed produces identical output;
  - style rates in 10k draws fall within ±2 points of `simulate.yaml`;
  - `not_in_list` cases exclude the target.
- **`splits.py`:**
  - no customer and no anchor date overlaps between splits;
  - the hard-slice rule on crafted histories.
- **`model.py`:**
  - probabilities sum to 1 within a case;
  - temperature is applied;
  - a loaded artifact reproduces its recorded scores on 20 fixed rows;
  - a missing or corrupt artifact raises `ResolverUnavailable`.

**Graph scenarios (stubbed Jev and Claude, agent-core harness):**
- `understand.v2` state contains the match scores;
- a `kind: model` decision record is written;
- a `ResolverUnavailable` turn continues on the `understand.v1` path with a `kind: error` record.

#### Testing · ui §12

- **Unit (Vitest):**
  - merging and de-duplicating the three message sources;
  - the trace view model (bar selection order and the cap of 4, colour map, fold line, verdicts, error rows, reply check);
  - the queue sort;
  - Zod contract parsing for §4.7;
  - money and date formatting per locale;
  - the demo stage-light mapping.
- **Channel authorization:** the `onSubscribe` handler, tested offline with AppSync `EvaluateCode`:
  - customer on its own `/session` ✓;
  - customer on another `/session` ✗;
  - customer on `/queue` ✗;
  - customer on `/trace` ✗;
  - agent on each ✓;
  - missing or expired token ✗.
- **BFF (Vitest, mocked AgentCore and DynamoDB Local):**
  - the ownership check before history reads;
  - the takeover gate skips the runtime;
  - claim race;
  - idempotent retry;
  - role checks on every staff route.
- **Publisher (pytest or Vitest):**
  - each Stream record maps to the right channel and event;
  - a poison record goes to the DLQ without blocking the batch.
- **End-to-end (Playwright, mocked BFF backends):**
  - the four customer states (clarify, confirm → filed, handoff → takeover, expired);
  - the console lifecycle (claim → take over → message both ways → return → resolve);
  - demo acts 1–3.
  - An axe scan on every page.
- **Live smoke run** (manual, only with the owner's approval): one full ES handoff and takeover against the deployed stack, recording turn latency, push latency and the SSR timeout behaviour.
- **Design pass:** `impeccable detect --json` over `web/`, once, after the UI is finished; findings fixed in one batch.

#### Testing · deployment §10

- **Infra unit tests** (`infra/tests/`, pytest with `aws_cdk.assertions`, offline, run in CI):
  - every table has point-in-time recovery, `RETAIN`, and its TTL attribute where specced; Streams are on exactly the three tables;
  - the runtime has a `CustomJWTAuthorizer` whose discovery URL is the `Identity` stack's output;
  - IAM: no `Action: "*"`, and no `Resource: "*"` outside the allow-list with reasons;
  - the publisher's event source mapping has bisect on error, `ReportBatchItemFailures`, at most 5 retries and the SQS on-failure destination;
  - the serving bucket blocks public access and denies non-TLS requests;
  - every log group has 30-day retention;
  - the Amplify app has auto-build off, and its branch environment variables are wired from stack outputs;
  - every §6.3 alarm exists with its threshold, `DemoUnhealthy` covers all of them, and the dashboard has five rows;
  - no SNS topic exists.
- **cdk-nag** (AwsSolutions pack) in `infra-check`, failing on any error without a written suppression reason.
- **Stateful-replacement guard:** a script over `cdk diff` output, tested against two fixture diffs (one safe, one replacing a table).
- **Live checks after the first deploy** (manual, recorded in the README):
  - `verify` passes;
  - one ES dispute and one PT decline explanation end to end through `/demo`;
  - the unauthorized-charge scenario reaches `/agent` and is taken over;
  - a turn's trace is visible in CloudWatch, reached from the trace page's link;
  - a forced Jev failure (a throwaway runtime version with an invalid secret name) turns `Jev failing` and `DemoUnhealthy` red on the dashboard, then back to OK after the revert;
  - cold-start and warm turn latency recorded;
  - the §8 table filled in.

#### Testing (pytest, offline) · evaluation §8

- **Goal generator:** same seed gives identical cards; labels equal `policy.evaluate()` on the target; identities only from bucket 9 (held-out) or 8 (dev); the mix matches §4.1 exactly.
- **Persona rule checks:** each rule on crafted messages.
- **Outcome classifier:** crafted store diffs, decision records and replies for every class, including each unsafe type and the `unsafe` override.
- **Metrics:** denominators; "not defined" with zero successes; the bootstrap keeps repetitions of a goal together; small-sample labels at n < 30.
- **Legacy comparison:** reads a fixture `asis_metrics.json`; fails on a missing key.
- **As-is runner:** a small labeled synthetic CSV fixture under `analysis/asis/tests/fixtures/` gives known metric values; reconciliation fails on a 0.2% mismatch and passes on an exact match.

## Data Pipeline (`pipeline/`, `dbt/`, `fixtures/`)

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

## Agent Core (`agent/`)

- Python `>=3.12`; the project lives in `agent/` with its own `pyproject.toml` and `uv.lock`. Commands run from `agent/` unless stated.
- `customer_id` comes **only** from a verified JWT (`SessionContext`). No tool takes a `customer_id` argument, and a transaction that isn't owned gives the same `not_found` as one that doesn't exist.
- **Claude has no tools.** Both calls (`extract`, `compose`) are input-to-JSON with `output_config.format`. No LLM chooses a graph edge.
- **Jev:** TypeSafe `POST https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`, key `JEV_API_KEY`; 3-second timeout; one retry on timeouts and 5xx only; invalid responses are errors, never approval; no model substitution.
- **Claude defaults:** `extract` = `anthropic.claude-haiku-4-5` (thinking off, no effort); `compose` = `anthropic.claude-sonnet-5-5`, effort `low`; overridable via `LLM_EXTRACT_MODEL` / `LLM_COMPOSE_MODEL`.
- **Dispute policy** `dispute-policy.v1` (labeled synthetic):
  - only `Approved`; types `Purchase, Withdrawal, Payment, Transfer`;
  - 60-day window before `max_process_date`;
  - automated only if `amount_usd` ≤ 500 and reason ≠ `unauthorized`;
  - human review if `is_fraud`, `fraud_score > 30`, `amount_usd > 500`, reason `unauthorized`, or an escalation signal.
- **Thresholds `thresholds.v1`:**
  - intent: p ≥ 0.80 and margin ≥ 0.15;
  - target transaction: p ≥ 0.85 and margin ≥ 0.20;
  - handoff: `reports_unauthorized_use` / `legal_or_regulator_threat` ≥ 0.50, `asks_for_human` ≥ 0.60;
  - `distress` ≥ 0.60 → offer a human; `injection_attempt` ≥ 0.50;
  - `confirm` ≥ 0.90; each claim ≥ 0.80;
  - at most 2 clarifications and 2 confirmation re-asks; 2 consecutive Jev failures → handoff; 2 injections → handoff.
- **Tokens:** RS256 JWT, 15-minute TTL; claims `iss, aud, client_id, sub=customer_id, sid, scope, lang, iat, exp`.
- **DynamoDB tables** (`<prefix>-<name>`):
  - `checkpoints`: PK/SK, TTL 30 days;
  - `disputes`: PK `transaction_id`, GSI `by_customer`;
  - `handoffs`: PK `handoff_id`, GSI `by_status`;
  - `decision_records`: `session_id` + `sk`, TTL 90 days.
- **Every decision record stores its versions:** question set, thresholds, prompt, model, policy.
- **Graph limits:** `recursion_limit` 25; 20-second turn budget.
- **Serving contract:** `<serving>/latest.json` + `<serving>/<run_id>/<table>/*.parquet`, lowercase columns exactly as pipeline spec §5.3.
- **Tests:** `uv run pytest` runs offline tests only (markers `live` and `container` are excluded by default). Live tests and scripts that call Jev, Bedrock or S3 run **only after the owner explicitly approves each run**.
- **Commits:** each task ends with a commit. Stage only the task's files; never `.env`.

## Transaction Resolver (`agent/src/bankagent/resolver/`)

- Python `>=3.12`, in the agent's uv project `agent/`. Commands run from `agent/` unless stated.
- The runtime dependencies added are `numpy>=2.0` and `rapidfuzz>=3.9`. The offline dependency group is `resolver`: `scikit-learn>=1.5`, `lightgbm>=4.5`, `mlflow>=3.1`, `matplotlib>=3.9`. `[tool.uv] default-groups = ["dev", "resolver"]`, and the image uses `--no-default-groups`.
- **Features (13, in this order):**
  - `merchant_mentioned`, `merchant_sim`, `merchant_missing_on_cand`;
  - `amount_mentioned`, `amount_log_err`, `amount_rank`;
  - `date_mentioned`, `days_outside`;
  - `type_match`, `channel_match`, `city_match`;
  - `recency_pct`, `is_purchase`.
  An artifact whose feature list differs is refused.
- **Splits:**
  - customers: the first byte of `sha256(customer_id)` mod 10 → 0–7 train, 8 dev, 9 test;
  - anchors: train 2023-09-01…2025-09-30, dev 2025-10-01…2026-01-31, test 2026-02-01…2026-06-17;
  - window: 60 days before the anchor, inclusive;
  - histories with fewer than 2 candidates are skipped.
- **Hard slice:** a case is hard if another candidate has the same `transaction_type` and neither has a merchant; or another candidate has the same (folded) merchant; or another candidate's amount is within 10% of the target's. A missing target is `nil`.
- **Test set:** 150 cases (75 hard, 60 easy, 15 nil), alternating ES/PT within each slice. Dev set: 300 cases, alternating ES/PT.
- **Grids:**
  - logistic regression: C ∈ {0.01, 0.1, 1, 10, 100};
  - LightGBM: `num_leaves` ∈ {7, 15, 31} × `learning_rate` ∈ {0.05, 0.1} × `n_estimators` ∈ {200, 500};
  - selection on simulated validation by hard-slice top-1, then on dev with ties within 0.02 going to logistic regression.
- **Thresholds:** highest dev coverage with a dev wrong-action rate ≤ 0.02.
  - B1: τ and φ over [0.3, 0.99] in steps of 0.01;
  - B2 and P: t over [0.5, 0.99] and m over [0, 0.5] in steps of 0.01.
- **Adoption rule (fixed before the test run):** P replaces B2 if and only if mean wrong-action(P) ≤ mean wrong-action(B2) **and** mean hard-slice resolved-within-one-step(P) > B2's.
- **Committed dataset files keep transaction fields only**: never `customer_id` or `product_id`.
- **Live calls:** Bedrock (`dev-set`, `ingest-test`) and Jev (`jev`) run **only** with `--live`, and only after the owner approves each run. `uv run pytest` stays offline.
- **Commits:** each task ends with a commit. Stage only the task's files; never `.env`.

## UI (`web/`, `infra/realtime/`, agent change requests)

These rules apply to every task, and each task's requirements include them.

- **Next.js 16 differs from older versions.** Before writing Next code, read the relevant guide in `web/node_modules/next/dist/docs/`.
  - Route handlers get `params` as a `Promise`.
  - `cookies()` is async.
  - Middleware is `proxy.ts` exporting `proxy`.
- **TypeScript is strict.** No `any`. Unknown external input is parsed with Zod at the boundary (request bodies, IdP, AgentCore, DynamoDB items, channel events).
- **Colours are only CSS custom properties** mapped through Tailwind v4 `@theme` (spec §7). Components never use raw hex or default Tailwind palette classes (`zinc-*`, `blue-*`). The exception is `lib/trace/signals.ts`, which owns the signal hex values.
- **Server Components by default.** Add `"use client"` only for interactivity, hooks or realtime state.
- **Route handlers stay thin:** parse the input, authorize, call a `lib/server/*` function, and return `{data}` or `{error: {code, message}}` with the right status.
- **Identity:** `customer_id` comes only from a verified token (`sub`).
  - Customer cookie `cust_session`: audience `bankagent`.
  - Staff cookie `staff_session`: audience `bankagent-staff` and `role: "agent"`.
  - Both cookies: `httpOnly; Secure; SameSite=Lax; Path=/`. The only token browser JS ever sees is the realtime token.
- **Languages:** customer UI copy lives in the `es`/`pt` dictionaries; staff, trace and demo copy is English. Customer quotes are always shown in the original.
  - Money: formatted by currency code (COP with no decimals).
  - Dates: formatted in the locale.
- **Trace:** at most 4 open bars per turn. The signal colours are fixed (spec §7.3), a bar is grey below its threshold, and the verdict is always text plus icon.
- **Motion:** only the trace reveal (spec §7.4), and none under `prefers-reduced-motion`.
- **Channels:** `/session/<sid>`, `/queue`, `/trace/<sid>`. The namespaces are `session`, `queue` and `trace`. Publishing is IAM-only (the publisher Lambda).
- **Tests:**
  - `web`: `npm test` (Vitest, offline) and `npm run e2e` (Playwright, which mocks `/api/*`).
  - `infra/realtime`: `npm test`.
  - `agent`: `uv run pytest` (offline).
  - Anything that touches real AWS, Jev or Bedrock runs **only after the owner explicitly approves that run**.
- **Commits:** each task ends with a commit that stages only that task's files and never `.env*`. End each message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Deployment (`infra/`, workflows, agent observability)

- **Account and region:** one AWS account, region `us-east-2`, environment `demo`. No other environment or account.
- **Names:**
  - stacks: `LbDemo-Data`, `LbDemo-Identity`, `LbDemo-Agent`, `LbDemo-Realtime`, `LbDemo-Web`, `LbDemo-Ops`, and `LbDemo-GitHub` (bootstrap only);
  - resource names start with `lb-demo-`; tables are `lb-demo-<name>`;
  - runtime `lb_demo_agent` with endpoint `live`;
  - dashboard `lb-demo-ops`; composite alarm `lb-demo-DemoUnhealthy`.
- **Secrets (Secrets Manager):** `lb-demo/jev`, `lb-demo/idp-signing-key` and `lb-demo/amplify-github-token`.
  - They're created only by `infra/bootstrap.sh`. CDK references them by name and never creates, rotates or deletes them.
  - Never in the repo, GitHub secrets or logs.
  - GitHub holds only two **repository variables**: `AWS_DEPLOY_ROLE_ARN` and `AWS_DIFF_ROLE_ARN`.
- **The Jev key variable is named `JEV_API_KEY` everywhere**, local `.env` included. In AWS the agent gets `JEV_SECRET_ID=lb-demo/jev` and reads the key at startup.
- **Stateful resources** (the six tables) have `RemovalPolicy.RETAIN`, and `LbDemo-Data` has termination protection on.
- **IAM:** one role per principal. No `Action: "*"`. `Resource: "*"` only for the actions in `infra/tests/test_iam.py::STAR_OK`, each with a reason.
- **Retention:**

  | Data | Kept for |
  |---|---|
  | `checkpoints` | 30 days (TTL) |
  | `decision_records`, `conversation_messages`, `sessions` | 90 days (TTL) |
  | `disputes`, `handoffs` | no TTL |
  | every log group | 30 days |

- **Alarms:** no SNS topic and no alarm actions. Missing data counts as `notBreaching`.
- **Metrics:** namespace `LatamBank`. Observability code is best-effort: it never raises into a customer's turn.
- **Logs:** never include message text (`LOG_MESSAGE_TEXT=false`).
- **Commands:**
  - `infra/`: run from `infra/` (`uv run pytest`, `npx aws-cdk@2 synth`);
  - `agent/`: run from `agent/` (`uv run pytest`);
  - `infra/realtime/`: `npm test`.
  - Before any `infra/` synth or test, run `npm ci` in `infra/realtime/`: `NodejsFunction` bundles with its local esbuild.
- **Approval:** anything that creates or changes AWS resources, or calls Jev or Bedrock, runs **only after the owner explicitly approves that step**.
- **Commits:** each task ends with a commit that stages only that task's files and never `.env*`. End each message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Evaluation (`analysis/`, `eval/`)

- Python `>=3.12`. `analysis/` and `eval/` are separate uv projects; commands run from that folder unless stated. `eval/` depends on `bankagent = { path = "../agent", editable = true }`.
- As-is window: `process_date` in [2025-06-17, 2026-06-17], inclusive. Full history only for trend charts. `data_backup_20260831/` is never read. PII columns (names, documents, emails, phones, addresses) are never selected.
- In-scope legacy slice: `reason_category = 'Transaccional'`; disputes = complaints with `subcategory` in (`Cargo no reconocido`, `Cobro indebido`).
- Every metric in `asis_metrics.json` is `{"value": float|int|None, "n": int}` under a flat dotted key.
- Reconciliation tolerance: 0.1% relative difference; a mismatch fails the as-is run.
- Held-out set: 120 goals, 60 ES / 60 PT, the exact mix in spec §4.1; dev set: 30 goals. Held-out identities from customer bucket 9 (`sha256(customer_id)[0] % 10`), dev from bucket 8.
- Runs: 3 repetitions per held-out goal, 8 workers, `max_turns` = 8. Each repetition uses its own DynamoDB table prefix.
- Persona: a non-Claude model served through OpenCode (OpenAI-compatible chat completions). Judge: `anthropic.claude-sonnet-5-5`; it never decides a class or an unsafe outcome.
- Every legacy-vs-new row carries the label `offline simulation vs historical record; different workloads`.
- Slices with n < 30 are labeled "small sample, not conclusive"; any gap over 10 points between slices of one dimension is listed for investigation.
- Bootstrap: 1,000 resamples of goals, keeping each goal's repetitions together; 95% intervals.
- Cost: prices per 1M tokens with a required `source`; a model without a sourced price makes cost `incomplete`. Zero successful resolutions → cost per success is `"not defined"`. Legacy cost needs `legacy.cost_per_agent_hour_usd` and `legacy.source`, otherwise `"not computed"`.
- **Live calls** (persona, Bedrock, Jev) run only with `--live`, and only after the owner approves each run. `uv run pytest` stays offline.
- **Commits:** each task ends with a commit, run from the repo root. Stage only the task's files; never `.env`.
