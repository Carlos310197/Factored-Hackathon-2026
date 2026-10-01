# Progress Tracker

Update this file whenever the current phase, the active unit or the implementation state changes. Record what is actually implemented.

## Current Phase

- Design and planning complete; implementation not started. Six design specs (`docs/design/`) and six plans (`docs/reference/plans/`), reorganized into `context/` and `feature-specs/` on 2026-10-01.
- Existing code: only the profiling scripts in `analysis/` (`domain_evidence.py`, `etl_facts.py`, `profile_demand.py`).
- Submission deadline: **2026-10-05**.

## Current Goal

- Start the build at `feature-specs/01-pipeline-scaffold.md`. The agent core (from `12`) and the as-is diagnosis (`40`) don't depend on the pipeline and can run in parallel.

## Completed

- 2026-09-26 → 2026-10-01: design specs and implementation plans for all six subsystems.
- 2026-10-01: docs reorganized into `context/` + `feature-specs/`; specs archived in `docs/design/`, plans in `docs/reference/plans/`.

## In Progress

- None.

## Next Up

Unit ranges, in build order (see `feature-specs/README.md` for the full list and dependencies):

| Units | Subsystem | First dependency |
| --- | --- | --- |
| 01–11 | Data pipeline | none |
| 12–25 | Agent core | none (16 uses a synthetic fixture; 23 uses the local drop) |
| 26–39 | Transaction resolver | 12, 16 |
| 40–52 | Evaluation (40–42, the as-is diagnosis, have no dependencies) | 43+ need agent core 12–24 |
| 53–76 | UI | agent core 12–22 |
| 77–90 | Deployment | 77 has none; the rest follow the agent core and UI |

## Open Questions

### From the data pipeline spec

#### Open items · pipeline §10

- Confirm in Slack `#technical-help` that dataset records may be loaded into Snowflake (third party) and sent to an external LLM. Synthetic data, but the brief says to follow the published data-use terms.
- Carlos to confirm the workflow and the Snowflake choice.
- Create the Snowflake trial (AWS us-east-2), our S3 bucket, and the public GitHub repo `factored-hackathon-2026-<team>`. The project folder is not a git repository yet.
- Who owns the Snowflake account and the AWS account for the bucket and the agent.

### From the agent-core spec

#### Open items and risks · agent-core §12

- **Data-use approval:** confirm with the organizers (Slack `#technical-help`) that dataset records may be sent to Amazon Bedrock and to TypeSafe (Jev). This extends the pipeline spec's open item.
- **Jev route:** TypeSafe's direct route is mock-tested only upstream, and the Decisions endpoint is alpha → live smoke test on day 1; pin `jev-1.13.0`.
- **Jev language quality:** Spanish and Portuguese accuracy is unknown (English is its strongest) → measured in spec 2, with the gloss setting as the lever.
- **AgentCore:** confirm whether the bearer token reaches the container, availability in us-east-2, and cold-start latency.
- **Bedrock:** exact model IDs and availability of Haiku 4.5 and Sonnet 5.5 in us-east-2; structured-output support on each.
- **Pipeline:** the export sort-order change (§9.3).
- **Schedule:** submissions close 2026-10-05, so specs 2 and 3 must be written in parallel with this implementation.

### From the UI spec

#### Open items and risks · ui §14

- **Amplify SSR:** the compute role and request timeout are unverified; the 202 + push fallback is designed in (§10). Checked in plan task 1.
- **AppSync Events:** availability in us-east-2, and the `onSubscribe` handler's access to authorizer claims. Checked in plan task 1. If the handler can't see the claims, the Lambda authorizer enforces the channel path instead.
- **Identity service reachability:** AgentCore's authorizer and our AppSync Lambda authorizer both need its JWKS over HTTPS. Hosting it is a dependency of the (not yet written) deployment work.
- **Agent-core schedule:** §4 adds tables, a gate and contract fields to a plan that's already being implemented. They must land before the UI's integration tasks.
- **Scenario data:** each scenario needs a demo identity whose real data triggers it (for example a transaction with `fraud_score` > 30, or a duplicate-looking pair). The selection script might not find all of them in the 60-day window; any gap is reported, never fabricated.
- **Jev alpha endpoint:** a live demo depends on it. There's no silent fallback (agent-core §4.4); a failed turn shows as a failure in the trace.
- **Submission deadline** 2026-10-05.

### From the deployment spec

#### Open items and risks · deployment §12

Each is checked in plan task 1, with the fallback chosen in advance.

| Item | Fallback |
|---|---|
| CloudFormation support for `AWS::BedrockAgentCore::Runtime` with JWT authorizer properties | CDK `AwsCustomResource` calling `CreateAgentRuntime` and `UpdateAgentRuntime` |
| Whether a JWT-authorized runtime also accepts SigV4 calls | Bearer-only invocation from the BFF (§4.1) |
| AppSync Events namespace handlers in CDK | L1 `AWS::AppSync::ChannelNamespace` with inline handler code |
| AppSync Events and Amplify compute roles in us-east-2 | Already flagged in UI plan task 1 |
| Amplify SSR timeout | 202-plus-push (UI §10) |
| Amplify needs a GitHub token to connect the repo | A fine-grained token with read access to this repo only, stored in `lb-demo/amplify-github-token`, revoked after the hackathon |
| Schedule: four days to the deadline, with application code still unwritten | The `Data` and `Identity` stacks and the deploy workflow go first, so the agent and web deploy as soon as they exist |

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
1. **The BFF calls AgentCore with the Bearer token only** (UI plan Task 13 uses `fetch` with `Authorization`; no SigV4). This settles spec §4.1's open item: the Amplify compute role has **no** `InvokeAgentRuntime` permission.
2. **There's no cookie-signing key.** The UI plan stores the IdP-signed JWT in the cookie directly. Spec §3 and §4.3's "cookie-signing key" is dropped.
3. **The serving bucket and Snowflake role already exist** (pipeline plan Task 2, created by hand). `LbDemo-Data` references the bucket by name and adds a TLS-only bucket policy.
   - The lifecycle backstop is dropped: CloudFormation can't set lifecycle rules on a bucket it doesn't own, and the export already keeps only 3 runs.
   - Bootstrap step 6 (Snowflake) becomes a check that the integration still lists the stage.
4. **The identity Lambda is a container image** built from `agent/Dockerfile.identity`, served with Mangum. The labeled demo identities (`config/demo_users.yaml`) are gitignored because they name real dataset customer ids. So the Lambda reads them from `s3://<serving bucket>/identity/demo_users.yaml`, uploaded by `agent/scripts/seed_demo.py`.
5. **Names:**
   - the table prefix is `lb-demo`, so tables are named `lb-demo-<name>`;
   - the AgentCore runtime name is `lb_demo_agent`, because runtime names allow only letters, digits and `_`;
   - the stacks are `LbDemo-<Part>`.
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
12. **The GitHub deploy role does slightly more than assume the CDK roles** (spec §4.2). It also has `amplify:StartJob`/`GetJob` on this app's `main` branch, and `bedrock-agentcore:GetAgentRuntime`/`GetAgentRuntimeEndpoint`, because the `web` and `verify` jobs call those APIs directly.
13. **Workflow names:** the data pipeline plan already owns `.github/workflows/ci.yml`, so the app's workflows are `app-tests.yml` (reusable), `app-ci.yml` (pull requests) and `deploy.yml`.

**Supersedes in the UI plan** (Task 8 adds a note to that file):
- Task 7 Step 6: the TypeScript `RealtimeStack` and `bin/app.ts`;
- Task 7 Steps 8–9 and Task 8 Steps 5 and 7: the TypeScript stack, its synth, deploy and probe deploy commands;
- Task 24 Steps 2–3: the hand-made BFF IAM policy and the console-created Amplify app.

The handler code and its Vitest tests from UI Tasks 7–8 stay. The probe script stays, and is run against this plan's stack in Task 14.

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

- None yet.
