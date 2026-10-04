# Architecture Context

> Text under a `· <spec> §<n>` heading, or after a *From …* line, is copied word for word from `docs/design/`, except where marked *(updated 2026-10-04)*: those edits bring the text in line with the deployed infrastructure (region us-east-1, web on ECS Fargate Spot, Terraform-managed serving bucket). Where a planning decision changed a spec, the change is listed in `progress-tracker.md` → Architecture Decisions, and it takes precedence over the copied text.

## Stack

| Layer | Technology | Role |
| --- | --- | --- |
| Warehouse | Snowflake (AWS us-east-1, account `RLQHFPF-AXC97788`) + dbt-snowflake | RAW → STAGING → CURATED with enforced contracts, quarantine and DQ results |
| Pipeline code | Python 3.12 (uv), `snowflake-connector-python`, GitHub Actions | Loader, export to the serving bucket, scheduled runs |
| Serving set | S3 parquet + `latest.json`, read with DuckDB | The agent's read-only view of the curated data |
| Agent | Python 3.12 (uv), LangGraph + `DynamoDBSaver`, `bedrock-agentcore` | The workflow graph, tools, policy and handoff, hosted on AgentCore Runtime |
| Decisions | Jev (`jev-1.13.0`, TypeSafe direct) | Bounded judgments: intent, target transaction, escalation flags, reply verification |
| Language | Claude on Amazon Bedrock (Haiku 4.5 `extract`, Sonnet 5.5 `compose`) | Extraction and reply writing; no tools |
| Learned component | numpy + rapidfuzz at runtime; scikit-learn, LightGBM, MLflow offline | Transaction resolver (ranker) |
| Agent state | DynamoDB | Checkpoints, disputes, handoffs, decision records, sessions, conversation messages |
| Identity | Mock OIDC IdP (FastAPI; on AWS: Lambda + HTTP API) | Labeled test identities, RS256 JWTs, JWKS |
| Web | Next.js 16 (App Router, React 19, TS strict), Tailwind v4, assistant-ui, Zustand, Zod | Customer chat, agent console, trace, demo stage; route handlers as a thin BFF |
| Real time | AppSync Events + DynamoDB Streams + publisher Lambda | Push to `/session/<sid>`, `/queue`, `/trace/<sid>` |
| Infrastructure | Terraform only (`infra/terraform/`: `bootstrap`, `platform`, `data`, `identity`, `agent`, `realtime`, `app`, `ops`), applied by GitHub Actions; `terraform test` with mocked providers, `trivy config` for security checks | One AWS account (`762197749808`), region us-east-1, environment `demo` |
| Web hosting | ECS Fargate Spot (`infra/terraform/app`), image in ECR | Runs the Next.js app and its BFF route handlers |
| Evaluation | DuckDB (as-is), a persona served through OpenCode, Claude judge | As-is diagnosis and held-out simulated evaluation |

## Decisions Already Taken

*From pipeline §1:*

Decisions already taken (2026-09-26): workflow = account/payment inquiries + dispute intake; warehouse = Snowflake with dbt-snowflake (chosen over dbt-duckdb on AWS; the caveats raised were the 30-day trial, cold-start latency for live reads, and a third-party data-use question); the agent reads an S3 parquet export, never Snowflake directly.

*From agent-core §1:*

**Decisions already taken (2026-09-29):**

| Topic | Decision |
|---|---|
| Control model | Option A: **code decides the route, Jev makes the bounded judgments, Claude handles language.** No LLM ever chooses a graph edge or calls a tool. |
| Workflow engine | LangGraph `StateGraph` with the `DynamoDBSaver` checkpointer (`langgraph-checkpoint-aws`) |
| Hosting | Amazon Bedrock AgentCore Runtime (ARM64 container, `/invocations` + `/ping`) |
| Language model | Claude on Amazon Bedrock, configurable per role; defaults: Haiku 4.5 for `extract`, Sonnet 5.5 (effort `low`) for `compose` |
| Decision model | Jev (TypeSafe direct, `jev-1.13.0`), key in `JEV_API_KEY` |
| Identity | Mock OIDC identity service we own (labeled test identities) |
| Agent state | DynamoDB |
| Dispute policy | Team-authored, labeled synthetic policy enforced in code (§5) |
| Multi-intent | Claude flags a second request; the graph queues it and offers it after the current one |

*From resolver §1:*

**Decisions already taken (2026-09-29):**

| Topic | Decision |
|---|---|
| Learned component | Transaction resolver (ranker) over the customer's 60-day candidates |
| Who decides | **Jev decides `target_transaction`**; ranker scores are added to its state as evidence. Code applies the thresholds. |
| Training data | Simulated structured mentions over real histories. No text and no LLM in training. |
| Dev set | 300 Claude-written ES/PT messages passed through the real `extract` |
| Test set | 150 messages written blind by Andrés (75 ES / 75 PT) |
| Model | L2 logistic regression (main) vs LightGBM `lambdarank` (comparison) |
| Tracking | MLflow, local file store; the promoted run is copied into committed metadata |

*From ui §1* (the last row, "Process", was superseded on 2026-10-01: this repo now uses `context/` and `feature-specs/`; see `progress-tracker.md`):

**Decisions taken (2026-09-30):**

| Topic | Decision |
|---|---|
| Surfaces | Customer chat, human-agent queue with full takeover, decision trace. No metrics dashboard. |
| Layout | The trace component lives in the agent's case view (Packet · Conversation · Trace tabs) **and** on a `/demo` stage beside the customer's phone |
| Demo | Three acts: 1 Sign in (auth shown once) → 2 Live conversation (presenter types; the trace appears after each turn's analysis) → 3 Scenarios (scripted chips) |
| Stack | One Next.js 16 (App Router) app; route handlers act as a thin BFF |
| Hosting | *(updated 2026-10-04)* ECS Fargate Spot (us-east-1): the Next.js app as one container image in ECR, no Amplify, no Cognito |
| Chat library | assistant-ui primitives with `useExternalStoreRuntime`, styled by us |
| Takeover transport | AWS AppSync Events, with push driven by DynamoDB Streams |
| Brand | Plain "LATAM Bank", light branding, "demo · synthetic data" labels |
| Visual worlds | Customer: **B, tropical modernist**. Staff, trace and demo canvas: **C, instrument panel** (§7) |
| Trace encoding | Each Jev signal owns a fixed colour; a bar is grey below its threshold and takes its colour above; at most 4 open bars per turn; the verdict text and icon carry act/clarify/handoff |
| Languages | Customer UI in ES/PT. Staff console, trace and demo chrome in English, with customer quotes kept in the original plus an English line |
| Process | No `context/` or feature-spec files; everything lives in this spec and its plan |

*From deployment §1:*

**Decisions taken (2026-10-01):**

| Topic | Decision |
|---|---|
| Accounts and environments | **One AWS account** (the owner's, admin access), **one environment `demo`**, region us-east-1 *(updated 2026-10-04)*. Staging and production are remaining work (§9). |
| Automation level | IaC plus continuous deployment: GitHub Actions deploys on every push to `main` |
| IaC tool | *(updated 2026-10-04)* Terraform (`hashicorp/aws` 6.x, `snowflakedb/snowflake`), with the `awscc` provider only where `hashicorp/aws` lacks a resource |
| Stack structure | *(updated 2026-10-04)* One Terraform root per lifecycle (§3), each with its own state, applied in order by one workflow |
| Identity service hosting | The Python `identity/` unit as one Lambda behind an API Gateway HTTP API |
| Web build | *(updated 2026-10-04)* The deploy workflow builds the `web/` image, pushes it to ECR tagged with the git SHA, and rolls it out to the ECS service with `terraform apply` in `infra/terraform/app` |
| Operations built | CloudWatch alarms and one ops dashboard. **No email or SNS notifications**: alarm state shows on the dashboard only. |

*From evaluation §1:*

**Decisions taken (2026-10-01):**

| Topic | Decision |
|---|---|
| Legacy system | The as-is contact center that produced the historical data. There is no replayed legacy bot. |
| Comparison | Only metrics defined for both systems. Other metrics are new-system-only. Every comparison row is labeled "offline simulation vs historical record". |
| System-level same-workload baseline | Not run. The resolver's B0-vs-P result is the same-workload baseline; the missing system-level one is stated as a limitation. |
| As-is analysis engine | Standalone DuckDB over the raw local drop (`analysis/asis/`), reconciled against the curated marts when they exist |
| Held-out workload | 120 simulated-customer goals (60 ES / 60 PT), each run 3 times |
| Persona model | A model served through OpenCode, not Claude, so the simulated customer is a different model family from the agent |
| Judge | Claude Sonnet, only for soft criteria, validated against 40 human labels |

## System Boundaries

| Path | Responsibility |
| --- | --- |
| `pipeline/`, `dbt/`, `fixtures/`, `infra/snowflake/`, `tests/` (root) | Data pipeline: loader, dbt models and tests, fixture drop, Snowflake DDL |
| `agent/` (package `bankagent`) | Agent core, identity service, transaction resolver (`bankagent.resolver`) and their tests |
| `analysis/` (package `asis`) | As-is diagnosis over the raw local drop; the profiling scripts live here too (gitignored for now; the as-is package is added to git when built) |
| `eval/` (package `evalkit`) | Held-out evaluation harness, depends on `../agent` by path |
| `reports/` | Generated as-is and evaluation reports plus figures |
| `web/` | The Next.js app |
| `infra/terraform/` | All infrastructure, one root per lifecycle (Deployment Topology → Terraform roots). Deployed today: `bootstrap/`, `platform/`, `app/`. Planned: `data/`, `identity/`, `agent/`, `realtime/`, `ops/` |
| `infra/snowflake/` | Snowflake DDL the pipeline runs (RAW and META tables) |
| `infra/realtime/` | TypeScript handler code for the realtime Lambdas and the namespace handler, with Vitest tests; bundled to `dist/` by esbuild (no CDK) |
| `infra/scripts/` | Python helpers for CI: Terraform source checks, the stateful guard, `verify.py`, `deploy.sh` |
| `bin/` | `bin/dbt` (dbt wrapper), `bin/app-url` (prints the web task's current public URL) |
| `.github/workflows/` | `ci.yml` + `pipeline.yml` (data pipeline); `infra.yml` (Terraform `platform` and `app`: check on PR, apply on `main`); `app-tests.yml`, `app-ci.yml`, `deploy.yml` (app, planned) |
| `docs/design/` | The original design specs (frozen rationale) |
| `docs/reference/plans/` | The original implementation plans (reference code, read by line range only) |

### Code locations · ui §15

- `web/`: the Next.js app (routes, BFF handlers, components, stores, dictionaries, tests).
- `infra/realtime/`: TypeScript code for the namespace handlers, the Lambda authorizer and the publisher Lambda. *(updated 2026-10-04)* The AppSync Events API, Stream mappings and DLQ are in the Terraform `realtime` root.
- The agent-core changes live in the agent-core code paths its plan defines.

## Data Pipeline

### Architecture · pipeline §4

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

Snowflake account *(updated 2026-10-04)*: `RLQHFPF-AXC97788` on AWS `us-east-1` (the same region as our AWS resources; only the daily load from the organizer bucket in us-east-2 crosses regions), Standard edition, one `X-Small` warehouse `WH_PIPELINE` with `AUTO_SUSPEND = 60`. Databases: `LATAM_BANK` (schemas `RAW`, `STAGING`, `CURATED`, `META`) and `LATAM_FIXTURE` (same schemas, used only by the fixture test).

#### Ingestion modes (documented migration path, not built) · pipeline §4.1

The organizer data is delivered as daily files, so the loader is batch. If the bank swapped files for continuous delivery or CDC, only the trigger, the RAW row shape, and the serving path change; models, tests, and contracts carry over. Continuous files: Snowpipe auto-ingest (requires bucket-owner event notifications, so for a bucket we do not own a Snowflake Task polling `COPY INTO` on a short schedule) with Streams + Tasks or Dynamic Tables driving transforms; GitHub becomes CI/CD only. CDC or real-time events: DMS/Debezium into Kinesis/Kafka, Snowpipe Streaming into RAW as a change log (operation, key, sequence number, timestamp), Dynamic Tables with a 1-minute target lag, and the agent reading a hot store fed by the same stream while Snowflake keeps the analytics copy. Genuine streaming in this project is limited to our own app events (sessions, dispute cases, actions, traces) into Snowflake via Snowpipe Streaming so the ops metrics refresh from the same warehouse as the baseline.

## Agent Core

### Architecture · agent-core §3

Diagram: `docs/diagrams/agent-core.svg` (animated: one dispute filed after confirmation, then an unauthorized-charge report handed off to a human).

```
Customer UI (spec 3) ──login/OTP──▶ identity/  mock OIDC IdP: discovery + JWKS; RS256 JWT, 15 min
        │ Bearer JWT                            claims: sub=customer_id, sid, scopes, lang
        ▼
AgentCore Runtime  inbound JWT authorizer → our container
        ▼
app.py  re-verify JWT → SessionContext → graph.invoke(thread_id = session id)
        ▼
graph/  LangGraph StateGraph + DynamoDBSaver
        load_context → understand → route ─┬─ answer_inquiry ───────────────────────┐
                                           ├─ resolve_transaction → check_eligibility│
                                           │    → confirm ⏸ → file_dispute → verify ─┤
                                           ├─ clarify ⏸ ─────────────────────────────┤
                                           └─ handoff ───────────────────────────────┤
                                                                   reply ◀───────────┘
        uses: llm/ · decisions/ · policy/ · tools/ · handoff/
        ▼
DynamoDB (checkpoints, disputes, handoffs, decision_records) · S3 serving parquet (DuckDB)
Claude on Bedrock · Jev on TypeSafe · OpenTelemetry → AgentCore Observability / CloudWatch
```

⏸ marks a LangGraph `interrupt()`: the graph pauses and the customer's next message resumes it with `Command(resume=…)`.

#### Components · agent-core §3.1

| Unit | Responsibility | Depends on |
|---|---|---|
| `identity/` | Mock OIDC IdP: login → OTP → RS256 JWT; publishes `/.well-known/openid-configuration` and `/jwks.json`. About 20 demo users mapped to real `customer_id`s, in a versioned config file, labeled test identities. | signing key |
| `app.py` | AgentCore entrypoint: re-verifies the JWT (signature, expiry, audience, scope), builds `SessionContext`, invokes the graph, returns the response contract (§9.2). | `identity` JWKS, `graph` |
| `graph/` | LangGraph state, nodes and conditional edges. Nodes call units; edges read typed decisions plus policy results. | all units below |
| `llm/` | `extract()` and `compose()` on Claude with structured outputs. No tools. Model config per role in `llm/models.yaml`. | Bedrock |
| `decisions/` | Jev client, versioned question sets (`decisions/questions/v1/*.yaml`) and thresholds (`decisions/thresholds/v1.yaml`), response validation, the routing function. | TypeSafe |
| `policy/` | `dispute_policy.yaml` (labeled synthetic) plus escalation rules; pure functions returning per-rule pass/fail. | none |
| `tools/` | Customer-scoped reads over the serving parquet (DuckDB) and dispute/handoff writes. Every tool takes `SessionContext`; none accepts a `customer_id`. | S3, DynamoDB |
| `handoff/` | Builds and validates the `handoff.v1` packet. | receipts, decisions |
| `store/` | DynamoDB access for disputes, handoffs and decision records. | DynamoDB |

#### One turn · agent-core §3.2

1. AgentCore authorizes the request against the IdP's JWKS. `app.py` **re-verifies the token itself** and takes `customer_id` only from it; the tool layer's guarantee doesn't depend on AgentCore forwarding headers. If the header isn't forwarded, the token travels in the invocation payload and is verified the same way. The thread resumes from its checkpoint.
2. `load_context` loads the customer's products, their transactions in the 60 days before the as-of date, and their open disputes (ours plus earlier complaints). The session keeps the `run_id` it started with.
3. `understand`: `llm.extract` (§6.1), then **one** Jev `understand` request (§4.1).
4. `route`: a conditional edge combines Jev's probabilities, the thresholds (§4.3) and the policy (§5). `needs_review`, low confidence or a Jev failure goes to `clarify` or `handoff`.
5. Actions go through `tools`. Every write is read back (`verify`), and only the read-back receipt counts as proof.
6. `reply`: `llm.compose` writes the reply from receipts (§6.2); Jev `verify_reply` checks its claims (§4.2); the reply is sent. A queued intent, if any, is then offered.
7. Every node appends to `decision_records` (§7.4). OpenTelemetry spans share the same `turn_id`.

## Transaction Resolver

### Architecture · resolver §3

```
customer message ──▶ extract (Claude, agent core §6.1)
                        mentions: merchant, amount, currency, date_from/to, type_hint, channel_hint, city
                                  │
60-day candidates ──▶ resolver.score()  (features.py → model.json)
                        {transaction_id: prob}, best_raw_fit, per-feature contributions
                                  │
                   Jev understand.v2: target_transaction reads the message + candidates annotated "· match 0.93"
                                  │
                   code thresholds (decisions/thresholds/v2.yaml) → act | ask customer (top 3) | not_in_list
```

#### Components (`bankagent/resolver/`) · resolver §3.1

| Unit | Responsibility | Used by |
|---|---|---|
| `features.py` | Pure function `(mentions, candidate, context) → feature vector` (§4.1). The single source of features for both training and serving. | train, serve |
| `model.py` | Loads the artifact; `score(candidates, mentions, as_of) → {probs, best_raw_fit, contributions}`. Logistic-regression inference is a dot product and a softmax, with no scikit-learn at runtime. | agent |
| `simulate.py` | Generates training and simulated-validation cases (§5.1). Rates live in `resolver/simulate.yaml`. | offline |
| `splits.py` | Customer-hash and anchor-date split rules, plus the hard-slice rule (§5.2) | offline, tests |
| `train.py` | Hyperparameter search, model selection, calibration, MLflow logging, promotion | offline |
| `make_dev_set.py` | Builds the dev set: simulator picks → Claude writes the message → real `extract` | offline |
| `make_test_sheet.py` | Builds the CSV Andrés writes the test set from | offline |
| `evaluate.py` | Runs B0/B1/B2/P on a set and writes the report (§6) | offline |

`train.py`, `simulate.py`, `make_*` and `evaluate.py` are never imported by the agent.

**Artifact:** `resolver/artifacts/v1/model.json` contains:
- feature list, scaler, coefficients, intercept, temperature;
- metadata: serving `run_id`, seed, `simulate.yaml` hash, git SHA, MLflow run id, dev metrics.

If LightGBM wins (§4.3), its native text model file goes alongside `model.json`, and `lightgbm` becomes a runtime dependency. JSON and text only; no pickle. `resolver/MODEL_CARD.md` is committed next to it.

## Real-Time UI

### Architecture · ui §3

```
Browser ── /login /chat (world B) · /agent /trace/[sid] /demo (world C)
   │ HTTPS, httpOnly cookies (cust_session | staff_session)      ▲ WebSocket (AppSync Events)
   ▼                                                             │ /session/<sid> · /queue · /trace/<sid>
Next.js 16 on ECS Fargate Spot (us-east-1)                       │
   BFF route handlers (§6)                                       │
     ├─ identity service: login, OTP, staff login, realtime token│
     ├─ AgentCore /invocations: Bearer JWT, runtime session id   │
     └─ DynamoDB reads/writes (ECS task role)                    │
   ▼                                                             │
DynamoDB: sessions* · conversation_messages* · handoffs · decision_records
   │ Streams (conversation_messages, handoffs, decision_records) │
   ▼                                                             │
realtime-publisher Lambda ── IAM-signed publish ─────────────────┘
(* = new tables, §4)
```

**Rules:**

1. **Producers only write to DynamoDB.** `app.py` and the BFF never publish. The publisher Lambda turns every committed write into a channel event, so there's no gap between write and publish.
2. **Clients load, then listen.** On mount or reconnect a client fetches history after its last cursor from the BFF, then applies pushed events, de-duplicated by id. A missed push is repaired on the next fetch.
3. **Browsers never hold AWS credentials.** They hold the 15-minute JWT in an httpOnly cookie, plus a **subscribe-only realtime token** from the identity service:
   - for a customer it's bound to their `sid`;
   - for an agent it grants `/queue`, `/session/*` and `/trace/*`.
4. **AppSync auth:**
   - Subscribe uses a Lambda authorizer that verifies the realtime token against the identity service's JWKS (cached).
   - The namespace `onSubscribe` handler compares the channel path with the token's claims: a customer may subscribe only to `/session/<own sid>`; `/queue` and `/trace/*` need role `agent`.
   - Publish needs IAM, which only the publisher Lambda has. A browser can never publish.
5. **During takeover the runtime isn't called.** When `sessions.control = human:<agent_id>`, `POST /api/chat` stores the customer's message and returns `awaiting: human`. `app.py` also refuses such sessions, as defence in depth.

#### Channel events · ui §3.1

| Channel | Event | Emitted from | Consumers |
|---|---|---|---|
| `/session/<sid>` | `message` `{id, role: customer\|assistant\|agent\|system, text, parts?, ts}` | `conversation_messages` Stream | customer chat, console Conversation tab |
| `/session/<sid>` | `control` `{control, agent_name?}` | `conversation_messages` system rows written by takeover/return | customer chat |
| `/queue` | `handoff` `{handoff_id, status, priority, reason_codes, language, amount?, claimed_by?, created_at}` | `handoffs` Stream | console queue, demo handoff ticker |
| `/trace/<sid>` | `record` `{turn_id, seq, node, kind}` (slim; no payload) | `decision_records` Stream | demo "Analysing…" stage lights, console Trace tab (live) |
| `/trace/<sid>` | `turn_complete` `{turn_id}` | the `kind: turn_end` record (§4.6) | trace blocks: fetch the full turn from the BFF |

Trace events stay slim on purpose: the full records are fetched through the BFF (§6), which applies the view-model rules (§8.3).

## Deployment Topology

### Terraform roots · deployment §3 *(updated 2026-10-04: everything is Terraform)*

The spec's six CDK stacks become Terraform roots under `infra/terraform/`, one state file each in `s3://fh26-tfstate-762197749808-use1` (`<root>/terraform.tfstate`). Environment `demo`, us-east-1. A root reads the roots above it only through `data "terraform_remote_state"`, and `deploy.yml` applies them in this order. Names of the new resources keep the `lb-demo-` prefix; the roots that already exist keep `latam-bank-`/`fh26`.

| # | Root | Owns | Applied by | Changes |
|---|---|---|---|---|
| 0 | `bootstrap/` (exists) | State bucket, GitHub OIDC provider, `gha-deploy` and (unit 88) `gha-plan`, `TF_DEPLOY`, organizer keys in SSM, the secret containers `lb-demo/jev` and `lb-demo/idp-signing-key` (values set out of band), Transaction Search | a laptop (`apply.sh`) | Only when the trust chain changes |
| 0 | `platform/` (exists) | Serving bucket, Snowflake objects, `SI_SERVING` + `snowflake-serving`, stages, `pipeline-runner` + `PIPELINE_SVC` | `infra.yml` on `main` | Occasionally |
| 1 | `data/` | The six DynamoDB tables: `checkpoints`, `disputes`, `handoffs`, `decision_records` (agent-core §7.2), `sessions`, `conversation_messages` (UI §4). On-demand billing, point-in-time recovery on, TTLs as specced, Streams on `conversation_messages`, `handoffs` and `decision_records`. Shapes come from `tables.json`, exported from `TABLE_SPECS`. ECR repos `lb-demo-agent` and `lb-demo-identity`; SSM image parameters `/fh26/agent/image` and `/fh26/identity/image`. Reads the serving bucket by name; doesn't manage it. | `deploy.yml` | Rarely. `prevent_destroy` and deletion protection on every table. |
| 2 | `identity/` | The `identity/` Lambda (container image, Python 3.12, ARM64) behind an API Gateway HTTP API. The issuer is the API's default `https://<api-id>.execute-api.us-east-1.amazonaws.com` URL. Stage throttling: rate 10/s, burst 20. Reads the RS256 signing key from Secrets Manager. | `deploy.yml` | Occasionally |
| 3 | `agent/` | AgentCore runtime `lb_demo_agent` (image from `/fh26/agent/image`, ARM64, tagged with the git SHA) with a custom JWT authorizer (discovery URL from `identity`, the allowed audience) and the `Authorization` header allowlist, PUBLIC network mode (egress to Bedrock, TypeSafe and S3), endpoint `live`. The execution role (§4.2). Environment: table prefix, serving URI, issuer, model config, `GIT_SHA`, the secret's name for `JEV_API_KEY` (read at startup). The Terraform resource type is settled in unit 77. | `deploy.yml` | Every agent change |
| 4 | `realtime/` | AppSync Events API with namespaces `session`, `queue` and `trace`, and the `onSubscribe` handler (UI §3). The Lambda authorizer (verifies realtime tokens against cached JWKS). The `realtime-publisher` Lambda on the three Streams: bisect on error, `ReportBatchItemFailures`, 5 retries, SQS on-failure destination (the DLQ). Lambda code is bundled from `infra/realtime/` with esbuild. | `deploy.yml` | Occasionally |
| 5 | `app/` (exists) | The web: ECR repo `latam-bank-web`, ECS cluster `latam-bank` with `FARGATE_SPOT` as the default capacity provider, service `latam-bank-web` (one task, 0.5 vCPU / 1 GB, X86_64, port 3000, circuit breaker with rollback), SSM `/fh26/web/image`, the task role (§4.2), and container environment from the roots above (issuer URL, runtime invoke URL, AppSync endpoints, table names). | `deploy.yml` (moved from `infra.yml` in unit 89) | Every web change |
| 6 | `ops/` | CloudWatch alarms and the `lb-demo-ops` dashboard (§6). No SNS topic. | `deploy.yml` | Occasionally |

Splitting by lifecycle keeps stateful resources in a root that almost never changes. A broken agent or web deploy cannot replace a table, because its root doesn't own any.

### Deployed Infrastructure (Terraform)

What is live today, from `docs/design/2026-10-01-infra-iac-design.md` and `infra/terraform/`. Everything is applied by GitHub Actions (`infra.yml`) except `bootstrap/`, and nothing is created by hand in a console.

| Fact | Value |
|---|---|
| AWS account | `762197749808`, admin through the SSO profile `hackathon-sso` |
| Region | **us-east-1** for all our resources. The organizer bucket stays in us-east-2 (theirs). |
| Snowflake account | `RLQHFPF-AXC97788`, AWS us-east-1 |
| Repository | `Carlos310197/Factored-Hackathon-2026` (private; public before submission) |
| Terraform state | `s3://fh26-tfstate-762197749808-use1`, keys `bootstrap/`, `platform/`, `app/terraform.tfstate`, `use_lockfile = true` |
| Name prefixes | `latam-bank-`/`fh26` for the resources that exist (bucket, cluster, service, roles, parameters); `lb-demo-` for the resources the new roots add (tables, runtime `lb_demo_agent`, Lambdas, API, alarms) |

| Root | Applied by | Owns |
|---|---|---|
| `bootstrap/` | a laptop, once | state bucket; GitHub OIDC provider; role `gha-deploy` (trust: `main` and `pull_request`; `AdministratorAccess` for now); Snowflake user `TF_DEPLOY` (AWS workload identity on `gha-deploy`); SSM `/fh26/organizer/aws_key_id` and `/aws_secret` |
| `platform/` | `infra.yml` | serving bucket `latam-bank-serving-762197749808-use1` (private, SSE-S3, TLS-only); warehouse `WH_PIPELINE`, role `PIPELINE_ROLE`, databases `LATAM_BANK` and `LATAM_FIXTURE` with their schemas and grants; storage integration `SI_SERVING` and the AWS role `snowflake-serving`; file format `RAW.CSV_HEADER`; stages `RAW.ORGANIZER_STAGE`, `RAW.SERVING_STAGE`, `LATAM_FIXTURE.RAW.FIXTURE_STAGE`; role `pipeline-runner` and Snowflake user `PIPELINE_SVC` |
| `app/` | `infra.yml` | ECR repo `latam-bank-web` (immutable tags, last 10 kept); ECS cluster `latam-bank` (`FARGATE_SPOT` default, `FARGATE` available); service `latam-bank-web` in the default VPC's public subnets with a public IP; security group open on port 3000 to the team's IPs only; execution and task roles; log group |

**Web hosting now (ponytail):** no load balancer, so the task's public IP changes on every deploy or Spot interruption; `bin/app-url` prints the current URL. The image is a Node placeholder until `web/` ships one. **Demo day:** add an ALB with HTTPS and switch the service to `FARGATE` (on-demand). The task role gets its permissions (DynamoDB tables, nothing else) when those resources exist.

## Storage Model and Contracts

### Serving contract (pipeline → agent)

#### CURATED (`LATAM_BANK.CURATED`, dbt models with `contract: enforced`) · pipeline §5.3

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

#### Serving export (our bucket, `s3://<our-bucket>/serving/`) · pipeline §5.4

- Storage integration `SI_SERVING` (Snowflake assumes an IAM role in our account scoped to `serving/*`). No static keys.
- Per run: `COPY INTO @serving_stage/<run_id>/<model>/ FROM CURATED.<model> FILE_FORMAT = (TYPE = PARQUET) HEADER = TRUE OVERWRITE = TRUE` for `dim_customer`, `dim_product`, `fct_transaction`, `fct_complaint`, `seed_decline_reason`. Multiple files per table are fine; the agent reads a glob.
- Pointer: `COPY INTO @serving_stage/latest.json FROM (SELECT OBJECT_CONSTRUCT('run_id', …, 'exported_at', …, 'max_process_date', …, 'tables', …)) FILE_FORMAT = (TYPE = JSON COMPRESSION = NONE) SINGLE = TRUE OVERWRITE = TRUE`. The agent reads `latest.json` then the run folder; the flip is the only visible state change. Old run folders are kept for the last 3 runs and deleted by the export step afterwards.
- Serving contract for the agent (interface other components depend on): column names and types exactly as in 5.3; `max_process_date` in the pointer is surfaced to customers as "data as of".

### Agent state

#### DynamoDB tables · agent-core §7.2

| Table | Keys | TTL | Notes |
|---|---|---|---|
| `checkpoints` | managed by `DynamoDBSaver` | 30 days | LangGraph state only; not an audit artifact |
| `disputes` | PK `transaction_id`; GSI `customer_id` | none (prototype) | Conditional put `attribute_not_exists(transaction_id)`: at most one dispute per transaction; re-disputes go to a human |
| `handoffs` | PK `handoff_id`; GSI `status` + `created_at` | none (prototype) | The human queue reads from here |
| `decision_records` | PK `session_id`, SK `turn_id#seq` | 90 days | The execution record for audit and evaluation |

**Dispute item fields:** `dispute_id` (`DSP-<ULID>`), `transaction_id`, `customer_id`, `product_id`, `reason`, `amount`, `currency`, `amount_usd`, `customer_statement {original, en}`, `route`, `status`, `policy_version`, `session_id`, `turn_id`, `language`, `created_at`.

**`verify`** is a strongly consistent read-back compared field by field against the draft. The receipt holds `dispute_id`, `status`, `created_at` and a hash of the record.

#### Handoff packet (`handoff.v1`) · agent-core §7.3

```json
{
  "handoff_id": "HND-…", "created_at": "…", "session_id": "…",
  "customer_id": "…", "language": "es|pt", "data_as_of": "2026-06-17",
  "priority": "critical|high|medium",
  "reason_codes": ["reports_unauthorized_use", "amount_over_limit"],
  "customer_request": {"original": "…", "en": "…"},
  "verified_facts": [{"fact": "…", "receipt_id": "…"}],
  "actions_taken": [{"action": "dispute_drafted", "result": "pending_review", "receipt_id": "…"}],
  "decisions": [{"question": "reports_unauthorized_use", "value": 0.91,
                 "question_set": "understand.v1", "thresholds": "v1"}],
  "policy_checks": [{"rule": "within_60_days", "passed": true}],
  "open_questions": ["…"],
  "transcript_ref": "session:<id>"
}
```

- **Priority** is set by code: unauthorized use or fraud → `critical`; legal threat → `high`; otherwise `medium`.
- **`verified_facts`** come only from receipts.
- **`open_questions`:** at most 3, written by Claude.
- **The transcript** is referenced, not copied in.
- **The customer** gets a reference number and no promised deadline or outcome.

#### Decision records · agent-core §7.4

One item per step:

- `session_id`, `turn_id`, `seq`, `node`, `kind` (`jev | llm | tool | policy | route | error`), `ts`, `latency_ms`;
- inputs hash; outputs (Jev probabilities, the Claude structured output, tool receipt, rule results);
- versions (question set, thresholds, prompt, model, policy);
- `cost` (Jev and Bedrock usage).

This is the audit artifact the brief requires: explanations come from these records, never from hidden model reasoning.

### Invocation contract (agent ↔ BFF)

*From ui §4, item 7. This revises the invocation contract in agent-core §9.2 below:*

7. **Invocation contract (§9.2), revised:**
   - **Request:** `{message, client_message_id}`, with the token in the `Authorization` header only. This drops the token-in-payload fallback.
   - **Response:** `{reply_text, language, awaiting: none|clarification|confirmation|human, options[], refs[], data_as_of, turn_id, summary?}`.
   - `summary` is present only when `awaiting = confirmation`: `{merchant, date, amount, currency, reason_code, product_last4}`. It's built from **the same draft object** that `create_dispute` files, so the card can never differ from the filed record.

## Interfaces Between Subsystems

### Interfaces for other components · agent-core §9

#### To spec 2 (evaluation and learned component) · agent-core §9.1

- The `decision_records` schema (§7.4).
- Versioned question-set and threshold files.
- `handle_turn()` with injectable Claude and Jev clients (for replay).
- `run_conversation(script, identity)` for scripted multi-turn cases.
- The gloss setting per language (§6.3) and the model config per role (§6).

#### To spec 3 (UI and deployment) · agent-core §9.2

- **Identity:** `POST /auth/login`, `POST /auth/otp`, `GET /.well-known/openid-configuration`, `GET /jwks.json`.
- **Invocation:** request `{message, session_token?}`; response `{reply_text, language, awaiting: none|clarification|confirmation, options[], refs[], data_as_of}`.
- **Handoff queue:** schema `handoff.v1`, read from the `handoffs` table.
- **Runtime needs:**
  - `JEV_API_KEY` from Secrets Manager;
  - IAM permissions for Bedrock invoke, `s3:GetObject/ListBucket` on `serving/*`, the four DynamoDB tables, and OpenTelemetry export.

#### To the data pipeline · agent-core §9.3

Sort the serving export by `customer_id` (§7.1). No other change to the serving contract.

### Interfaces · evaluation §9

**Consumes:**
- agent-core: `handle_turn()` with injectable Claude and Jev clients, `policy.evaluate()`, the store repositories, the `decision_records` schema (§7.4), the identity service with short-TTL tokens;
- resolver spec: the customer split rule (§5.2);
- pipeline: `fct_interaction`, `fct_complaint` for reconciliation only.

**Produces:**
- `analysis/asis/out/asis_metrics.json` and `reports/asis-<date>.md`;
- `eval/runs/<run_id>/` and `reports/eval-<date>.md`;
- the calibration evidence for agent-core §4.3 thresholds and the §6.3 gloss setting, from the 30 dev goals.

## Access Controls and Secrets

### Access controls · deployment §4

#### Trust paths · deployment §4.1

No browser ever holds AWS credentials. Each hop authenticates.

| From → To | How |
|---|---|
| Browser → BFF | httpOnly, Secure, SameSite=Lax cookie holding the 15-minute JWT |
| BFF → identity | HTTPS; login and OTP routes are public and throttled at the HTTP API stage |
| BFF → AgentCore | *(updated 2026-10-04, deployment plan #1)* The customer's Bearer JWT only, from the ECS task; the AgentCore authorizer checks it and `app.py` re-verifies. The task role has no `InvokeAgentRuntime` permission. |
| Browser → AppSync | Subscribe-only realtime token → Lambda authorizer → `onSubscribe` channel check (UI §3 rule 4) |
| Publisher → AppSync | IAM, `appsync:EventPublish` on this API only |
| Snowflake → S3 | Integration `SI_SERVING` assumes the AWS role `snowflake-serving` with an external-ID trust condition; read/write/list on the serving bucket only (Terraform `platform`) |
| GitHub → AWS | OIDC. *(updated 2026-10-04)* Deployed today: one role `gha-deploy` trusting `repo:Carlos310197/Factored-Hackathon-2026` on `ref:refs/heads/main` and `pull_request`, plus `pipeline-runner` with the same trust. Splitting a read-only PR role is remaining work. |

#### Roles · deployment §4.2

One role per principal, least privilege, no `*` resource except where the service requires it (X-Ray, CloudWatch `PutMetricData`), each with a written reason.

| Role | Allowed |
|---|---|
| Agent execution | `bedrock:InvokeModel*` on the two configured model or inference-profile ARNs. `s3:GetObject` and `s3:ListBucket` on `serving/*`. DynamoDB item operations on its six tables and their indexes, with no `Scan`, and no `DeleteItem` on `disputes` or `handoffs`. `secretsmanager:GetSecretValue` on `lb-demo/jev`. ECR pull. Logs, X-Ray, and metrics in namespace `LatamBank`. |
| Identity Lambda | `GetSecretValue` on `lb-demo/idp-signing-key`; logs |
| Publisher Lambda | Read on the three streams; `appsync:EventPublish`; `sqs:SendMessage` to the DLQ |
| AppSync authorizer | Logs only (JWKS is fetched over HTTPS) |
| Web task (`latam-bank-web-task`) | *(updated 2026-10-04)* Read and write on `sessions`, `conversation_messages` and `handoffs`; read on `decision_records`. No `InvokeAgentRuntime` (§4.1). The execution role `latam-bank-web-execution` pulls the image, writes logs and reads the web's secrets. |
| GitHub deploy (`gha-deploy`) | *(updated 2026-10-04)* Applies every root except `bootstrap`. `AdministratorAccess` today; narrowing it to the roots' resource types is remaining work (deployment plan #12). |
| GitHub plan (`gha-plan`, unit 88) | `ReadOnlyAccess`, state-bucket read and lock-file write, for PR plans |

#### Secrets · deployment §4.3

- **Secrets Manager:**
  - `lb-demo/jev`, the TypeSafe key;
  - `lb-demo/idp-signing-key`, the RSA private key (the `kid` is published in the JWKS).
  - *(updated 2026-10-04)* There's no Amplify GitHub token: the web is built in CI and pushed to ECR.
- **Secret creation** *(updated 2026-10-04)*: the containers are in Terraform `bootstrap/` with `prevent_destroy` and **no secret version**, and `put-secrets.sh` sets the values, so they never reach Terraform state and no CI deploy can rotate or delete them. The other roots reference them by name.
- **Web secrets** *(updated 2026-10-04)*: none today (deployment plan #2 drops the cookie-signing key). Any later web secret goes into the ECS task definition's `secrets` from Secrets Manager, never into `environment`.
- **Organizer S3 keys:** SSM SecureString `/fh26/organizer/*` and the `RAW.ORGANIZER_STAGE` definition; they reach Terraform state through the stage resource (private, encrypted state bucket: the accepted exposure).
- **Never stored** in the repo, GitHub secrets or logs. GitHub holds only the two role ARNs, which are not secret.
- **Rotation:** manual for the prototype. The README documents signing-key rotation (add the new key to the JWKS, switch signing, remove the old key after 15 minutes).

#### Data protection · deployment §4.4

- DynamoDB and S3 are encrypted at rest with AWS-owned keys. Customer-managed KMS keys are remaining work.
- The curated marts hold no names, contact details or full card numbers (pipeline §5.3), so the stores hold pseudonymous ids, transaction facts and transcript text.
- **Logs never include message text by default.** `LOG_MESSAGE_TEXT` defaults to `false` and stays off in `demo`. Decision records store input hashes plus model outputs (agent-core §7.4).

#### Retention · deployment §4.5

| Data | Kept for |
|---|---|
| `checkpoints` | 30 days (TTL) |
| `decision_records`, `conversation_messages` | 90 days (TTL) |
| `sessions` | 90 days (TTL, matching messages) |
| `disputes`, `handoffs` | No TTL in the prototype; a 1-year policy is remaining work |
| CloudWatch log groups | 30 days, set on every group Terraform creates |
| Serving runs | The last 3 (pipeline §5.4). *(updated 2026-10-04)* No lifecycle backstop (deployment plan #3). |
| DynamoDB point-in-time recovery | 35 days (service default) |

### Access and secrets · pipeline §7

- Organizer bucket: their static read-only keys, stored only inside the Snowflake stage definition (`CREATE STAGE organizer_stage URL = 's3://…/data/' CREDENTIALS = (…)`). They never appear in the repo, in GitHub secrets, or in CI logs.
- *(updated 2026-10-04: as built, GitHub Actions assumes the AWS role `pipeline-runner` via OIDC, and the Snowflake `SERVICE` user `PIPELINE_SVC` trusts that role with `WORKLOAD_IDENTITY (TYPE = AWS)`; Terraform uses `gha-deploy` → `TF_DEPLOY` the same way. The original text follows.)* GitHub Actions → Snowflake: a Snowflake `SERVICE` user with `WORKLOAD_IDENTITY (TYPE = OIDC, ISSUER = 'https://token.actions.githubusercontent.com', SUBJECT = 'repo:<org>/<repo>:ref:refs/heads/main')`, role `PIPELINE_ROLE` with usage on the warehouse and ownership of `LATAM_BANK` and `LATAM_FIXTURE`. The workflow requests the GitHub OIDC token (`permissions: id-token: write`). Verified: the Snowflake side, and the Python connector (`authenticator = WORKLOAD_IDENTITY`, `workload_identity_provider = OIDC`, `token = <GitHub JWT>`), which covers the `load` and `export` steps. To verify in the first implementation task: whether dbt-snowflake can pass that same token. If it cannot, the `dbt build` step uses key-pair auth for the same service user, with the private key in a GitHub secret and rotated after the hackathon; that would be the one secret of ours.
- Snowflake → our bucket: storage integration `SI_SERVING` (IAM role trust to Snowflake's account, `s3:PutObject/DeleteObject/GetObject/ListBucket` on `serving/*`).
- Agent (Fargate) → our bucket: task role with `s3:GetObject/ListBucket` on `serving/*`.
- Net: one inherited static credential, held in Snowflake; none of ours, or exactly one (the dbt key pair) if the fallback is needed.

### Prompt-injection defense, in layers · agent-core §6.4

1. **Structure:** `customer_id` only from the JWT; session-scoped tools; policy in code; fixed edges; Claude has no tools.
2. **Separation:** instructions only in the system prompt; customer text sent as delimited data marked untrusted (the same labeling is used in Jev's state).
3. **Detection:** Jev `injection_attempt` (§4.3).
4. **Output check in code:** the reply may mention only transaction, dispute and handoff ids belonging to this session; anything else gets the safe template.
5. **Output check with Jev:** `verify_reply` (§4.2).
6. **Minimization:** curated marts contain no names, documents or contact details; Jev gets aliases, not IDs.

## Platform Facts

### Facts this design rests on · ui §2

- **AgentCore Runtime passes `Authorization` through to the container** (agents-build › request-headers).
  - It strips every other header except those prefixed `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`.
  - This settles agent-core §12's open question: `app.py` can read and verify the bearer JWT itself.
- **AgentCore sessions** are keyed by the runtime session id (`X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`, at least 33 characters). Reusing it keeps a conversation on its warm session.
- **Don't front the runtime with API Gateway plus a Lambda** (about 29 s ceiling; agents-build › integrate). Our BFF calls the runtime endpoint directly.
- **AppSync Events** is managed WebSocket pub/sub (amazon-dynamodb reference architecture):
  - it replaces the API Gateway WebSocket, connections table and fan-out Lambda pattern;
  - **channel-level authorization is not enforced by default**, so a namespace `onSubscribe` handler is required;
  - publishing is best-effort; DynamoDB stays the source of truth.
- **DynamoDB** (amazon-dynamodb facts):
  - single-item conditional writes are atomic, so a claim needs no transaction;
  - reads have no conditions, so authorization comes from checking ownership before querying by the session partition;
  - every Stream consumer needs bisect-on-error, per-item failure reporting, bounded retries and a DLQ, or a poison record stalls the shard for 24 h.
- *(updated 2026-10-04)* **ECS Fargate Spot** runs the Next.js server (`next start` in a container). Route handlers get AWS access through the task role and secrets through the task definition. There's no platform request timeout while the task is reached directly; behind the demo-day ALB the idle timeout (60 s default) is above the 20 s turn budget.
- **Not yet verified; checked in plan task 1:**
  - AppSync Events in us-east-1.
  - *(updated 2026-10-04)* The Amplify compute-role and SSR-timeout checks no longer apply.
- **Data facts carried from agent-core §2:**
  - customers are all Spanish-speaking, so Portuguese is conversational only;
  - data ends 2026-06-17, so the UI always shows "data as of";
  - some synthetic quirks are shown as delivered (for example México in USD).
- **The trace's source** is `decision_records` (agent-core §7.4), plus the resolver's `kind: model` record (per-candidate probabilities and the top-3 feature contributions; resolver spec §3.2).

### Facts this design rests on · deployment §2

- **Brief:** the submission "is not expected to operate a live banking service"; a prototype "with evidence of production readiness and an honest account of the work required before deployment" is what's asked. So a single environment is enough, and the remaining work is written down rather than built.
- **Deadline:** submissions close 2026-10-05.
- **AgentCore Runtime** (UI spec §2): it passes `Authorization` through to the container and strips other headers except `X-Amzn-Bedrock-AgentCore-Runtime-Custom-*`. Sessions are keyed by the runtime session id. The container is ARM64 and serves `/invocations` and `/ping`.
- **The AgentCore JWT authorizer and the AppSync authorizer both need the identity service's discovery URL over HTTPS**, so identity must deploy before both.
- *(updated 2026-10-04)* **The web runs on ECS Fargate Spot**: secrets from the task definition, AWS access through the task role. A Spot interruption replaces the task (and, without an ALB, its IP).
- **AgentCore Observability** needs CloudWatch Transaction Search enabled once per account, and the ADOT Python distro in the container.
- **The data pipeline already uses GitHub OIDC** (for Snowflake). AWS gets the same pattern: no stored AWS keys anywhere.
- **Inconsistencies fixed by this spec:**
  - pipeline spec §7 says "Agent (Fargate) task role", but the agent runs on AgentCore;
  - local `.env` uses `TYPESAFE_API_KEY` while the agent core reads `JEV_API_KEY`. `JEV_API_KEY` is the name everywhere.

## Failure Handling

### Failure handling · pipeline §6

- COPY runs with abort-on-error; a failed partition leaves RAW untouched for that file. One retry on transient errors, then the workflow stops. `dbt build` and `export` do not run if `load` failed.
- `dbt build` fails on any error-severity test or contract violation; `export` runs only after a green build, so the serving set is never produced from a broken warehouse state.
- Row-level problems go to quarantine with a reason; the 1% singular test turns a systemic problem into a run failure.
- Schema evolution lands in RAW without failing; staging ignores unknown columns and a warn test makes them visible in `DQ_RESULTS`.
- Restated files are detected by ETag and force-reloaded; staging keeps the newest load per key.
- Export is atomic from the reader's point of view: unload into a run folder, then flip the pointer.

### Failure handling · agent-core §8

| Failure | Behavior |
|---|---|
| Invalid, expired or tampered JWT | Rejected before the graph runs; template shown. An unconfirmed draft is never filed. |
| Missing scope | That action is refused; the conversation continues. |
| Serving data unreadable | One retry → "can't access your information" plus a handoff offer; `/ping` reports unhealthy. |
| Data older than the 7-day freshness limit | Still answers, always showing "data as of"; the session keeps its starting `run_id`. |
| No products or transactions in the window | Deterministic answer. |
| Jev failure | §4.4 |
| Claude timeout or 5xx | One retry (10 s for extract, 20 s for compose) → clarify or template |
| Claude refusal or invalid JSON | Fallback middleware → one retry → template |
| Conditional-write failure on a dispute | "Already disputed": read the existing record and report its status and number |
| DynamoDB throttling | Bounded SDK retries |
| Write outcome unknown | Read back before retrying |
| Handoff write fails | Template pointing to the phone channel; critical log entry; never claim a handoff without a receipt |
| Graph loops | `recursion_limit` 25; at most 2 clarifications per intent → handoff; 20-second turn budget → safe reply, recorded |

### Failure handling · ui §10

| Situation | Behaviour |
|---|---|
| AgentCore timeout or 5xx | Error bubble with *Reintentar* / *Tentar de novo*. The retry reuses `client_message_id`, so the turn never runs twice (§4.3). |
| Request timeout (if a proxy in front of the web, such as the demo-day ALB, cuts a turn short) *(updated 2026-10-04)* | `POST /api/chat` returns `202 {turn_id}`; the reply arrives as a `message` event on `/session/<sid>` |
| Realtime disconnect | Thin "Reconectando…" / "Reconnecting…" banner; on reconnect, refetch after the cursor. Chat works over HTTP without push. |
| Publisher failures | Stream consumer: bisect on error, report per-item failures, retries 5, SQS DLQ; a CloudWatch alarm on DLQ depth > 0 |
| Claim race | Conditional failure → "Already claimed by <name>"; the row updates from `/queue` |
| Takeover during a running turn | The turn finishes and its reply is delivered; control changes from the next customer message |
| Expired token | Customer: sign-in sheet, conversation kept. Staff: redirect to staff login, then back to the same URL. |
| Jev down, refusal, template fallback | The customer sees the backend's safe reply; the trace shows the `error` row. Nothing is hidden. |
| Unsupported language | The backend's note ("solo español y portugués") renders as a normal reply |
| Empty states | Queue: "No open cases". Trace: "No turns yet: send a message to see the first decision". Filter with no results: "Nothing in <filter>". |
| `onSubscribe` refusal | The client drops to HTTP-only mode and logs it. Never retried in a loop. |

### Failure handling · deployment §7

Runtime behaviour is specced in agent-core §8 and UI §10. This table covers deployment and platform failures.

| Failure | Behavior |
|---|---|
| A test or a `terraform apply` fails *(updated 2026-10-04)* | `deploy.yml` stops; later roots aren't applied. Terraform does **not** roll back: resources it already changed in the failing root stay changed and are recorded in state. Fix forward or revert the commit, and the next deploy converges. |
| Web image build or ECS rollout fails *(updated 2026-10-04)* | The deployment circuit breaker rolls the service back to the previous task definition, which keeps serving. The deploy is red. |
| Spot interruption | ECS starts a replacement task; the app is unreachable for about a minute and, without an ALB, gets a new IP (`bin/app-url`). |
| `verify` fails | The deploy is red. Roll back as below. |
| The runtime update fails to stabilize (bad image or environment) | *(updated 2026-10-04)* The `agent` apply fails; `verify` and later roots don't run. Whether `live` keeps serving the previous runtime version depends on the resource chosen in unit 77, which records it; if not, step 2 of the runbook below points it back. |
| Jev secret missing or invalid | `app.py` still starts and `/ping` stays healthy. Every Jev call fails → clarify or handoff (agent-core §4.4). The `Jev failing` alarm turns red. No other model substitutes. |
| Identity service down | No new logins. Existing tokens keep verifying from cached JWKS until they expire (at most 15 minutes). |
| A deploy would replace or delete a stateful resource | *(updated 2026-10-04)* The stateful guard fails the PR (and the deploy, before the `data` apply) when the `data` plan deletes or replaces a table. `prevent_destroy` and table deletion protection stop it if it gets through anyway. |

**Rollback runbook (README):**
1. `git revert` the bad commit and push; the normal deploy restores the previous state.
2. Emergency only, when the agent alone is broken and a deploy is too slow: point the `live` runtime endpoint at the previous runtime version with `UpdateAgentRuntimeEndpoint`, then revert in git so IaC matches again.

### Failure handling · evaluation §7

| Situation | Behavior |
|---|---|
| Provider error during a conversation | The agent's own retry rules apply (agent-core §8). A conversation the harness cannot finish is classed `harness_error`, counted, and not retried silently. |
| Persona breaks character | Discarded, classed `persona_discarded`, counted (§4.4) |
| Jev unavailable on run day | The affected conversations show the agent's real fallback behavior and are scored normally; the report states the outage window and how many conversations it touched. |
| Run interrupted | Resumed from `conversations.jsonl`; finished pairs are skipped |
| `asis_metrics.json` missing a key the comparison needs | The comparison step fails with the missing key named |
| Curated marts unavailable | As-is report marked "not reconciled" (§3.4) |

## Invariants

These rules come straight from the specs and the plans' global constraints. Breaking one is a bug, whatever the unit says.

1. `customer_id` comes **only** from a verified JWT (`SessionContext`, or `sub` in the BFF). No tool takes a `customer_id` argument, and a transaction the customer doesn't own gives the same `not_found` as one that doesn't exist.
2. Code decides the route, Jev makes the bounded judgments, and Claude handles language. **Claude has no tools**, and no LLM ever chooses a graph edge or calls a tool.
3. A Jev error or invalid response is never approval. Nothing substitutes for Jev silently, and the graph never files while in `confirm`.
4. Every write is read back, and only the read-back receipt counts as proof. A reply never claims an action that has no receipt.
5. Every decision record stores its versions: question set, thresholds, prompt, model and policy, plus `GIT_SHA` once deployed.
6. All time windows are measured from the serving pointer's `max_process_date`, never from today's date. A session keeps the `run_id` it started with.
7. PII columns never leave RAW. Committed datasets and Jev requests carry aliases and transaction fields, never `customer_id` or `product_id`.
8. Producers only write to DynamoDB. Only the publisher Lambda publishes to AppSync. Browsers never hold AWS credentials, and the only token browser JS sees is the subscribe-only realtime token.
9. Secrets are never in the repo, GitHub secrets or logs. Logs never include message text.
10. Stateful resources (tables, bucket) are retained. A deploy must never replace or delete them.
11. Anything that calls Jev, Bedrock, the persona model or real AWS runs only after the owner approves that run. Default test suites are offline.
