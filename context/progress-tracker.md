# Progress Tracker

Update this file whenever the current phase, the active unit or the implementation state changes. Record what is actually implemented.

## Current Phase

- **Data pipeline built (units 01–11)** and **Terraform infrastructure deployed** (state, OIDC, serving bucket, Snowflake objects, ECS web hosting shell). Agent core, resolver, evaluation, UI and the remaining Terraform roots (`data`, `identity`, `agent`, `realtime`, `ops`) are not started: there is no `agent/`, `eval/` or `web/` code yet.
- Region: **us-east-1** for all our AWS resources and Snowflake. The organizer bucket (theirs) stays in us-east-2.
- Offline suite: `uv run pytest -m "not snowflake"` → 43 passed, 6 deselected (2026-10-04).
- Submission deadline: **2026-10-05**.

## Current Goal

- Start the agent core at `feature-specs/12-agent-scaffold.md`. The as-is diagnosis (`40`) can run in parallel. The UI (53+) and deployment (77+) follow the agent core.

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

## In Progress

- None.

## Next Up

Unit ranges, in build order (see `feature-specs/README.md` for the full list and dependencies):

| Units | Subsystem | Status | First dependency |
| --- | --- | --- | --- |
| 01–11 | Data pipeline | **done**, running daily and green | none |
| 12–25 | Agent core | next | none (16 uses a synthetic fixture; 23 uses the local drop) |
| 26–39 | Transaction resolver | not started | 12, 16 |
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
