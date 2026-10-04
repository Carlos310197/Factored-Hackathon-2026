# LATAM Bank Customer-Service System

> How to read this file: everything below a `· <spec> §<n>` heading, or inside a block introduced by a *From …* line, is copied word for word from the design specs in `docs/design/`. A `§` reference inside copied text points to the original spec's numbering. `docs/design/README.md` shows where each section lives now.

## Overview

This is the Factored Hackathon 2026 submission for a synthetic LATAM Bank. The system includes:

- a customer-service agent that answers account and payment inquiries and takes transaction-dispute intake in Spanish and Portuguese;
- a learned component that resolves which transaction a customer means;
- a curated data pipeline that feeds the agent;
- an evaluation against the historical contact center;
- a customer chat, a human-agent console and a decision-trace demo stage;
- a one-account AWS deployment with operations.

Submissions close **2026-10-05**. Owners: Carlos (agent, resolver, UI, evaluation, deployment), with Andrés on the data pipeline and the resolver's blind test set.

Specs are referred to by short names: `pipeline`, `agent-core`, `resolver`, `ui`, `deployment` and `evaluation`. Inside the copied text, "spec 2" means `evaluation` (plus `resolver`), and "spec 3" means `ui` plus `deployment`.

## Goals

1. Curate the five source tables the workflow needs, with contracts, quality checks, lineage and a freshness policy, and publish a serving copy the agent reads (`pipeline`).
2. Resolve account and payment inquiries and take dispute intake in ES/PT, showing a normal resolution, a clarify/abstain path and a structured human handoff (`agent-core`).
3. Ship at least one learned component, evaluated against baselines with valid labels, leakage prevention, calibrated thresholds and splits (`resolver`).
4. Measure the new system on a held-out workload and compare it with the as-is contact center only on shared metrics (`evaluation`).
5. Let judges see each decision and why it was taken, and let human agents take over live (`ui`).
6. Show a credible route to operation: reproducible IaC, CI/CD, tracing, alarms, access controls, retention and an honest list of remaining work (`deployment`).

## Core User Flow

1. A customer signs in to `/login` with a labeled demo identity and an on-screen OTP, choosing Español or Português.
2. The customer writes in `/chat`. Each turn runs Understand → Decide → Act → Verify → Escalate in the agent core.
3. The turn ends in one of three ways: a resolution (an answer, or a dispute filed after confirmation and verified by read-back), a clarification or abstention, or a handoff with a `handoff.v1` packet.
4. A human agent claims the handoff in `/agent`, reads the packet and the decision trace, takes over the chat live, then returns it to the assistant or resolves it.
5. On `/demo`, the presenter runs the three acts (sign in, live conversation, scenarios) with the trace revealed after each turn.

## Features

### Data pipeline

*From pipeline §1:*

Build the repeatable data preparation the hackathon brief scores under "sound data and ML practice": contracts, quality checks, lineage, and an update/freshness policy. The pipeline curates the five source tables the chosen workflow needs (account/payment inquiries + transaction-dispute intake) and publishes a serving copy the live agent reads without depending on Snowflake being awake.

### Agent core

*From agent-core §1:*

The AI side of the hackathon brief is split into three specs:

1. **Agent core (this spec):** the conversational agent, its tools, authentication and permissions, and the human handoff.
2. **Evaluation and learned component (next):** held-out evaluation, the baseline comparison, Jev threshold tuning, and the measurements the brief asks for (automated resolution, containment, escalation quality, unsafe outcomes, latency, cost).
3. **UI and deployment/operations (last).**

This spec defines the interfaces the other two consume (§9).

**Workflow:** account and payment inquiries, plus transaction-dispute intake, in Spanish and Portuguese. The system must show:

- a normal resolution path;
- an ambiguous or unsupported request (clarify or abstain);
- a case that requires a human (structured handoff).

It follows the kickoff deck's loop, Understand → Decide → Act → Verify → Escalate. Its principle is that AI should not be autonomous just because it can be.

### Transaction resolver (learned component)

*From resolver §1:*

The brief requires at least one learned component, evaluated against an appropriate baseline, with valid labels, leakage prevention and justified representations, metrics, thresholds and splits. This spec defines that component: a **transaction resolver**. It is a classic ML ranker that scores which of a customer's transactions they are describing. Jev reads those scores as evidence when it answers `target_transaction`.

### Evaluation

*From evaluation §1:*

This is the "spec 2" the agent-core spec refers to and the "separate spec" for system-wide evaluation that the resolver spec defers to. It covers three things:

1. **As-is diagnosis.** What the historical data says about the current contact center, which is the "problem supported by data" the brief asks for and the opening of the deck.
2. **Held-out evaluation of the new system.** Simulated customers with hidden goals, run against the real agent, producing the measurements the brief lists: safe automated resolution, containment, escalation quality, unsafe outcomes, latency, cost, and slices.
3. **Legacy vs new comparison.** Only on metrics both systems have. Everything else is reported as new-system-only.

### UI

*From ui §1:*

The agent-core spec deferred "the customer UI, the human-agent queue UI" and the related infrastructure to a third spec. This is it, minus the deployment of the agent and identity service themselves.

The UI has two audiences:

- **Customers of the synthetic LATAM Bank.** They talk to the assistant in Spanish or Portuguese about accounts, payments and disputed charges.
- **Hackathon judges, watching a live demo.** They must see the three required paths (normal resolution, clarify/abstain, human handoff) and *why* each decision was taken: code decides the route, Jev makes bounded judgments, Claude writes the language.

A third audience, **human agents**, receive handoffs, read the packet, and can take over the conversation live.

### Deployment and operations

*From deployment §1:*

This is the deployment half of the agent-core spec's "spec 3". The UI spec covered the surfaces and left out "deploying the AgentCore runtime and the identity service". This spec deploys every component of the system and covers the operations story.

It answers brief item 6, **"a credible route to operation"**: demonstrate tracing, bounded retries, safe fallback and a reproducible setup, and explain capacity limits, monitoring, access controls, data retention and the remaining deployment work. Tracing, retries and fallback behaviour are already specced in the agent core; this spec makes them run, observable and reproducible in AWS.

## Scope

### In Scope

#### Scope · pipeline §3

In: `customers`, `products`, `transactions`, `complaints`, `call_center_interactions` from `data/`.
Out: `digital_events`, `campaign_sends`, `satisfaction_surveys`, `call_transcripts`, `branches`, `service_agents`, `marketing_campaigns`, `daily_exchange_rates`, and the whole `data_backup_20260831/` prefix. Transcripts are documented as unusable (templated text, no intents) using the profiling output; they are not loaded.

*From resolver §1:*

**In scope:**
- the resolver's features, model, training data (simulated), dev and test sets;
- the evaluation of four systems on the same held-out cases;
- the resolver's integration into the agent core.

*From ui §1:*

**In scope:**
- four surfaces: customer chat, agent console, trace page, demo stage;
- the real-time channel;
- the BFF route handlers;
- the change requests to the agent core that the UI needs.

*From deployment §1:*

**In scope:**
- infrastructure as code for every AWS resource the other specs need;
- CI checks and continuous deployment from GitHub;
- the identity service's hosting;
- IAM, secrets and retention;
- tracing, metrics, alarms and an ops dashboard;
- the capacity statement and the remaining-work list.

### Out Of Scope

#### Out of scope for this spec · pipeline §11

Agent, tool layer, evaluation harness, learned component, UI, deployment of the agent, and the app's own store. Each gets its own spec. This spec fixes the serving contract (5.3, 5.4) those components consume.

#### Out of scope for this spec · agent-core §13

- The evaluation harness, labeled datasets, baselines and threshold calibration (spec 2).
- The customer UI, the human-agent queue UI, hosting of the identity service and handoff API, AgentCore deployment, and streaming app events to Snowflake (spec 3).
- Card blocking, refunds, or any movement of money.

*From resolver §1:*

**Out of scope:** the system-wide evaluation (safe automated resolution, containment, escalation quality, unsafe outcomes, cost per case). That gets a separate spec, which reuses this spec's test-set conventions (§5).

*From ui §1:*

**Out of scope:**
- deploying the AgentCore runtime and the identity service (they must be reachable over HTTPS; see §13);
- the ops and eval metrics dashboard;
- Snowflake event streaming;
- dark mode.

*From deployment §1:*

**Out of scope:**
- application behaviour (already specced elsewhere);
- the Snowflake pipeline itself (only its S3 role lives here);
- alarm notifications;
- cost guardrails;
- post-deploy smoke tests with automatic rollback;
- Snowflake app-event streaming.

The last four are listed as remaining work (§9).

*From evaluation §1:*

**Out of scope:** the learned-component evaluation (resolver spec §6), threshold calibration of the resolver (resolver spec §6.3), the UI, deployment.

### Remaining deployment work · deployment §9

This goes in a README section, in this order:

1. **Identity:** replace the mock IdP with a real one (Cognito or the bank's IdP) with MFA.
2. **Environments:** before production, separate staging and production environments (ideally separate AWS accounts) with promotion between them. The prototype runs a single `demo` environment in one account.
3. **Safer deploys:** a post-deploy functional smoke test with automatic rollback, and canary traffic on the AgentCore endpoint.
4. **On-call:** alarm notifications routed to on-call (SNS to paging) and a runbook per alarm.
5. **Cost guardrails:** AWS Budgets, a per-turn cost metric and a cost alarm.
6. **Hardening:** customer-managed KMS keys, automatic secret rotation, WAF on the web ALB and the HTTP API, a custom domain.
7. **Retention:** a policy for `disputes` and `handoffs` (1 year, then archive), and a deletion process for data-subject requests.
8. **Private networking:** AgentCore VPC mode with VPC endpoints for S3, DynamoDB and Bedrock; egress allowed only to TypeSafe.
9. **Capacity:** load testing and quota increases.
10. **Analytics:** stream app events (sessions, disputes, decision records) to Snowflake, so ops metrics and the baseline share one warehouse.
11. **Data use:** approval for sending dataset records to Bedrock and TypeSafe (open item carried from earlier specs).

## Dataset Facts

These facts come from profiling the organizer data. Every design decision depends on them.

### Verified facts the design rests on · pipeline §2

From profiling the organizer bucket (`s3://factored-datathon-2026-…/data/`) on 2026-09-26:

- Layout: one CSV per day per fact table (`<table>_YYYYMMDD.csv` under `year=/month=/day=`), 1,097 partitions from 2023-06-17 to 2026-06-17. Dimension tables are single CSVs. The partition always equals `process_date`. CSV headers carry a UTF-8 BOM.
- Types parse 100% from text. Referential integrity is 100% for `customer_id` and `product_id`. No duplicate keys and no exact or near duplicates in any of the seven tables checked. No schema change between the first and last file of any table.
- Real quirks: nulls only in nullable columns (duration 14%, claimed amount 68%, accent 30%); the event timestamp falls on the day after `process_date` for 25% of transactions and 33% of interactions, consistent with a timezone offset; sentiment values are Spanish while the dictionary lists English.
- `data_backup_20260831/` is a different synthetic generation (0 shared IDs for the same day, 4k of 150k customer IDs in common). It is never loaded.
- Cross-table links that do not work: `interactions.mentioned_products` (0.65% match products), `complaints.origin_interaction_id` (100% empty). Grounding goes through `customer_id`.

Consequence: the documented traps (2% duplicates, schema evolution, late arrivals) are not present in the current drop. The pipeline builds the defenses anyway and proves them with a labeled fixture drop, which the brief explicitly allows ("demonstrate update correctness with a clearly labeled test fixture").

### Facts this design rests on · agent-core §2

From the curated data and a profile of the local drop (2026-09-29):

- **Customers:** all Spanish-speaking (México 74,907, Colombia 45,251, Argentina 29,842). There are **no Portuguese-speaking customers.** Brazil appears only as a transaction country. So Portuguese support is conversational: the session language is the customer's choice, Portuguese evaluation cases are team-written, and this is reported as a data limitation.
- **Transactions:** statuses `Approved / Declined / Pending / Reversed`; response codes `00, 05, 14, 51, 54`, matching `seed_decline_reason`. Declines are about 5% of recent rows.
- **Dispute demand:** the complaint subcategories *"Cargo no reconocido"* (unrecognized charge) and *"Cobro indebido"* (improper charge) together make up about 37% of recent complaints. This is data backing for the workflow choice.
- **Complaints don't link to transactions**, so "already disputed" can only be checked against our own dispute store.
- **The data ends on 2026-06-17.** All time windows are measured from the serving pointer's `max_process_date` (the "as-of" date), never from the real date today.
- **Synthetic-data quirks are shown as delivered**, for example México transactions in USD.
- **Jev constraints** (skill references, checked 2026-09-21):
  - Jev is stateless; each request carries all its evidence, up to about 32k tokens of state for the longest question (64k total).
  - English is its best-supported language.
  - It answers only with `choice` / `noul` / `score`. `selected` is not approval, calibration is not resistance to prompt injection, and the example thresholds are not calibrated.
  - The direct TypeSafe transport is only mock-tested upstream, and the endpoint is alpha.

### Facts this design rests on · resolver §2

Profiled from the local drop on 2026-09-29.

**No organizer label supports a learned model.** Each candidate was checked:

| Candidate label | Finding |
|---|---|
| Transcript intent | 26,552 transcripts in 2026 but only 42 distinct `customer_text` values, all balance inquiries. `detected_intents` is `consulta_general` (95%) or empty. |
| `is_fraud` | 0.09% positive (407 / 448,641, Mar–Jun 2026). The rate is flat (0.06–0.24%) across status, type, channel, response code, domestic vs abroad, and amount. Every row with `fraud_score` > 30 is fraud, which catches 78% of fraud. A model would only reproduce `fraud_score`. |
| `was_escalated` | 9.8–10.5% in every reason, sentiment, channel and wait-time bucket (686k interactions) |
| `sla_breached` | 19–22.5% in every priority, category and channel (67k complaints). `compensation_granted` is 0% everywhere. |

The generator appears to assign these outcomes at fixed rates, independent of every other field. This goes in the report as evidence for the component choice.

**Resolving the target transaction is easy for most customers and hard in a tail.** In the 60-day window ending 2026-06-17 (104,082 customers):
- transactions per customer: median 2, p90 5, max 16; no customer exceeds the 40-candidate limit;
- `merchant_name` appears only on purchases (95% of them), with 24 distinct merchants. Withdrawals, transfers, payments, deposits and adjustments (about 70% of rows) have none;
- 2% of customer–merchant pairs repeat within the window.

Consequence: the component's value is **calibrated abstention on the hard tail**, not headline accuracy. The report shows the easy and hard slices separately (§5.2).

## Success Criteria

The definition of done for each spec. Feature specs have smaller, unit-level checks.

### Definition of done · pipeline §9

- `pipeline.yml` green on `main`: load, `dbt build`, export.
- `tests/test_fixture_drop.py` green in CI.
- `s3://<our-bucket>/serving/latest.json` present and pointing at a run folder containing the five exported tables.
- `META.DQ_RESULTS` and `META.RUN_MANIFEST` populated for the latest run.
- README section documenting: source contracts, freshness policy, lineage (manifest), quarantine policy, the fixture drop, and limitations (backup prefix ignored, transcripts unusable, timezone offset, counts below the documented totals, static organizer keys).

### Definition of done · agent-core §11

- `docker compose up` (agent, identity service, DynamoDB Local) plus a terminal chat client demonstrate:
  - an ES account inquiry;
  - a PT decline explanation;
  - an ES dispute filed after confirmation and verified;
  - ambiguous → clarify;
  - unsupported → abstain;
  - unauthorized charge → handoff with a valid `handoff.v1` packet;
  - injection attempt refused;
  - expired token rejected.
- Unit and graph tests pass in CI.
- Live smoke results recorded for Jev, Bedrock and S3 read latency.
- The ARM64 image passes the AgentCore contract test. The actual deployment is spec 3.

### Definition of done · resolver §8

- `train.py` reproduces the promoted artifact from its seed and serving `run_id`; the run is in MLflow.
- `resolver/artifacts/v1/` and `MODEL_CARD.md` are committed. The model card covers data, features, splits, dev metrics, calibration and limitations.
- `dev_v1.jsonl` and `test_v1.jsonl` are committed, the test hash is recorded before evaluation, and the test set was evaluated once.
- `resolver/reports/eval-<date>.md` is complete (§6.6).
- The adoption decision is recorded; `thresholds/v2.yaml` and `understand.v2` are active only if P won.
- Unit and scenario tests pass in CI.

### Definition of done · ui §13

- On ECS Fargate Spot (us-east-1), in front of the deployed agent:
  - `/demo` runs Act 1 (sign in with claims shown), Act 2 (free-typed turns, each followed by its trace block), and Act 3 (all 8 scenario chips);
  - the unauthorized-charge scenario lands in `/agent`, is claimed and taken over, the agent and customer exchange messages live, and the case is resolved.
- A customer cannot read or subscribe to another session (tests plus one manual attempt recorded).
- The unit, handler, publisher, channel-auth and end-to-end suites pass in CI. The axe scan shows no serious or critical issues.
- Agent-core change requests §4.1–4.9 are merged, with the agent-core tests extended for the gate, idempotency and the new contract fields.

### Definition of done · deployment §11

- `infra/terraform/` deploys every root into a clean account by following `bootstrap/apply.sh`, `put-secrets.sh` and the README *(updated 2026-10-04: everything is Terraform)*.
- A push to `main` runs `deploy.yml` green through `verify`. A PR shows a `terraform plan` per root and passes the Terraform tests, `trivy` and the stateful guard.
- The UI spec's definition of done (§13) passes against the deployed stack.
- `lb-demo-ops` shows live data from the demo run, and every alarm is OK afterwards.
- The README covers:
  - setup and bootstrap;
  - access controls;
  - retention;
  - capacity (quota vs measured);
  - monitoring;
  - the rollback runbook;
  - remaining deployment work.
- Pipeline spec §7 says "AgentCore execution role" instead of "Agent (Fargate) task role", and `JEV_API_KEY` is the only name for the Jev key, local `.env` included.

*From evaluation §10:*

- `reports/asis-<date>.md` and `asis_metrics.json` committed; reconciled, or marked "not reconciled".
- 120 held-out cards committed, their hash recorded below before the first run.
- 360 conversations run; `reports/eval-<date>.md` complete per §6.
- Judge validated on 40 human labels, κ reported.
- Offline tests pass in CI.
