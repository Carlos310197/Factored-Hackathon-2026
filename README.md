# LATAM Bank: an AI dispute desk that has to earn the right to act

Built for Factored AI & Data Hackathon 2026, this synthetic LATAM bank handles account and payment inquiries and transaction-dispute intake in Spanish and Portuguese. Code enforces identity, permissions and dispute policy; Jev answers bounded questions, a language model extracts details and writes replies, and the trace records each step on a best-effort basis.

> This is a deployed workflow prototype with inspectable controls, not a production system. Identity is a mock IdP, the resolver is trained on simulated cases, and bank integration and operational validation remain (see [Limitations](#limitations-and-before-production)).

## Try it

**Live app: https://d21y0qq5d8ixnr.cloudfront.net** (HTTPS through CloudFront, us-east-1). **Deck:** [`docs/recibra-deck.pdf`](docs/recibra-deck.pdf) (6 slides: the 37-hour problem, what Recibra does, one dispute end to end, measured results, architecture and controls, the road to a pilot).

| Customer sign-in (`/login`) | Staff console (`/agent`) | Demo stage (`/demo`) | Customer chat (`/chat`) |
|---|---|---|---|
| [![Customer sign-in](docs/screenshots/login.png)](docs/screenshots/login.png) | [![Staff console with a handoff packet](docs/screenshots/agent-console.png)](docs/screenshots/agent-console.png) | [![Demo stage](docs/screenshots/demo-stage.png)](docs/screenshots/demo-stage.png) | [![Customer chat with a filed dispute and the My cases sheet](docs/screenshots/customer-chat.png)](docs/screenshots/customer-chat.png) |
| Demo identities listed, password and code filled in; ES/PT switch | The handoff queue and a live `handoff.v1` packet: the request, Jev's probabilities behind the handoff, policy checks and open questions | The phone with a live unauthorized-charge chat, the 8 scenarios, the handoff alert and the decision trace | A dispute filed live, with the My cases sheet showing it as sent |

- **Customer chat:** `/login`. The 20 demo identities (`demo01`–`demo20`) are listed on the page, and their password and code are filled in for you. `demo01`–`demo08` are each tagged with a demo scenario. Portuguese speakers: `demo04`, `demo08`, `demo12`, `demo16`, `demo20` (pick Português on the login page).
- **Staff console:** `/login?staff=1`, then `/agent` for the handoff queue, `/trace/<session>` for the decision trace and `/demo` for the guided stage. Staff credentials are not published; they are in the submission email.
- **Demo stage (`/demo`):** a phone frame, the live trace and 8 one-click scenarios: ES inquiry, PT decline explanation, ES dispute filed, ambiguous → clarification, unsupported → abstain, unauthorized charge → human handoff, prompt injection refused, expired session.

## The problem, in the bank's own numbers

![Dispute handling today: 37 h to first response, 15.5 days to resolve, 70 % still open](reports/figures/asis-dispute-handling.png)

| Finding | Value | Tag |
|---|---|---|
| Dispute complaints (Cargo no reconocido, Cobro indebido) | 8,199 | evidence |
| Median time to first response on a dispute | **37.0 h** (n=5,022) | evidence |
| Median time to resolve a dispute | **15.5 days** (n=1,886) | evidence |
| Disputes still Open or In Process | **69.8 %** (n=8,199) | evidence |

**Where the pain is.** Transaction inquiries are already resolved at first contact 92 % of the time; automating them alone would not move much. The pain is dispute intake: 37 hours before anyone answers and 70 % of cases still open. This system takes a dispute from the first message to a filed, read-back-verified record in one conversation, or to a complete, structured handoff packet when a human must decide. Transaction inquiries are in scope because a dispute needs them: you can't dispute a charge you can't find. [Full findings, success targets and what we don't claim](docs/problem-and-targets.md).

## What it does

| Case type | Example | What happens |
|---|---|---|
| Automated resolution | "¿Cuál es el saldo de mis tarjetas?", "Por que meu pagamento foi recusado?" | Read tools scoped to the session's customer, then a reply checked against the receipts |
| Ambiguous or unsupported | "Tengo un problema con un pago", "quiero un préstamo" | Clarification with options (at most 2 rounds), or an abstain message plus an offer of a human |
| Human required | Unauthorized charge, amount over 500 USD, fraud score over 30, legal threat, repeated injection | A structured `handoff.v1` packet (request, verified facts, actions taken, evidence, open questions) in the staff queue; a person can take over the chat |
| Dispute filed | "Me cobraron dos veces en Netflix" | A summary card built in code, then a confirmation, a policy re-check inside the write tool, a conditional write and a read-back |

## Architecture

[![System architecture](docs/diagrams/system-architecture.drawio.png)](docs/diagrams/system-architecture.drawio.svg)

| Layer | What | Where |
|---|---|---|
| Data | Snowflake and dbt publish versioned serving data | [`docs/data-pipeline.md`](docs/data-pipeline.md), `dbt/`, `pipeline/`, [`docs/diagrams/pipeline.svg`](docs/diagrams/pipeline.svg) |
| Agent | LangGraph runs on AgentCore with Bedrock and Jev | `agent/`, [`docs/diagrams/agent-core.svg`](docs/diagrams/agent-core.svg) |
| State | DynamoDB stores workflow and case records | `infra/terraform/data/` |
| Web | Next.js serves chat, staff, trace and demo views | `web/`, [`docs/diagrams/ui-architecture.svg`](docs/diagrams/ui-architecture.svg) |
| Realtime | AppSync Events authorizes session and staff channels | `infra/realtime/` |
| Identity | A mock OIDC IdP puts identity in tokens | `agent/src/bankagent/identity/` |
| Infra | Terraform and GitHub Actions deploy via OIDC | `infra/terraform/` |

**How a turn works.** The BFF forwards the message with the customer's bearer token. AgentCore checks the JWT, and the agent checks it again. The agent extracts details (LLM → JSON), asks Jev the bounded questions (intent, which of *your* transactions, confirm?, injection?), and code picks the next node from those answers and the YAML policy. Read and write tools run under the token's customer id and scopes. The reply is drafted by the LLM from the receipts, checked by a code guard for foreign ids, and verified by Jev; if it fails twice, a fixed template is used. Each step is written to `decision_records` and pushed to the trace view.

**Controls.** Code and YAML decide, Jev bounds judgments, and prompts only shape wording.
All 11 controls are mapped to code and tests; each of the 13 injected failures is a test.
[Control matrix, failure behaviour and deployed layers](docs/controls.md).

**Capacity.** 10 concurrent customers, 30/30 answered, p95 6.9 s. [Limits and measured load test](docs/operations.md#capacity).

**Data handling.** PII never leaves Snowflake `RAW`; external calls receive aliases and redacted receipts.
Jev and Bedrock payloads are egress-checked in tests. [Data use, recipients and retention](docs/data-handling.md).

**Learned component: the transaction resolver.** The resolver picks the customer's intended transaction or asks; it uses calibrated logistic regression.
On a 150-message blind human-written test set, wrong action was **0.7 % (1/150)**.
It was adopted under a pre-registered rule, but has not been shown better than B2 (Jev without the resolver). [Model, data, baselines, both test runs and limits](docs/resolver.md).

## Evidence map for the judges

| Judged area | Look at |
|---|---|
| Architecture | [System diagram](#architecture) with the 10 numbered flows; [`docs/diagrams/`](docs/diagrams/) for the pipeline, agent core and UI |
| Rationale and docs | This README, [problem and targets](docs/problem-and-targets.md), [limitations](docs/limitations.md), [`reports/asis-2026-10-05.md`](reports/asis-2026-10-05.md), `context/` (specs and decisions), `context/progress-tracker.md` → Architecture Decisions |
| Product | [`docs/before-after.md`](docs/before-after.md): today's complaint row next to a real `handoff.v1` packet from the live agent, field by field; [`docs/run-of-show.md`](docs/run-of-show.md): the 4-beat live demo script with a fallback per beat |
| Data engineering | [`docs/data-pipeline.md`](docs/data-pipeline.md): contracts, quarantine with a 1 % gate, lineage manifest, fixture drop proof (`tests/test_fixture_drop.py`), atomic self-describing serving pointer (`tests/test_export.py`), contract parity with the agent (`tests/test_contract_parity.py`), and the live run evidence (row counts per layer, 77 pass / 3 warn / 0 error) |
| Data analytics | [`reports/asis-2026-10-05.md`](reports/asis-2026-10-05.md) and `analysis/asis/` (synthetic-artifact detectors, every number with n); §9 reconciles its headline counts with `LATAM_BANK.CURATED` (exact match, 0 quarantined rows) |
| AI engineering | [`docs/policy-on-trial.md`](docs/policy-on-trial.md): one request replayed with one YAML rule changed (filed → refused, 0 writes) and argued against with persuasion (still refused); [the control matrix and failure table](docs/controls.md); live trace at `/trace/<session>`; `agent/docs/smoke-results.md` (all 8 scenarios against real Jev and Bedrock, 2026-10-05) |
| Measured quality | [`reports/eval-2026-10-05.md`](reports/eval-2026-10-05.md): held-out run, 360 conversations, every rate with its denominator and CI, error analysis and worked examples quoting decision records; [`reports/threshold-check-2026-10-05.md`](reports/threshold-check-2026-10-05.md): the hand-set Jev thresholds measured on that run |
| ML | [Resolver evidence](docs/resolver.md): model card, customer-disjoint splits, baselines and adoption rule fixed before the test run, frozen human-written ES/PT test set, both test runs reported with CIs |
| API and access | [Data handling](docs/data-handling.md); [`docs/api.md`](docs/api.md): every page and API route with who may call it and where it is enforced, the agent and identity endpoints, and the trust table between services |
| Operations | [`docs/operations.md`](docs/operations.md): dashboard `lb-demo-ops`, the alarm table, a recorded alarm drill, a rollback rehearsal, a 10-user load test, and how to follow one message across the web server, the agent and the decision records |
| Deployment | `infra/terraform/` (7 roots), `.github/workflows/` (OIDC, pinned actions), live app above |

## Status: what is done and what is not

The pipeline runs daily; the agent, web, identity and realtime are live in AWS us-east-1, including My cases and conversation history with end/new conversation controls. [Monitoring details](docs/operations.md).
Held-out eval: correct outcome **354/358**, safe automated resolution **182/185**, missed transfers **0/65**, unsafe outcomes **2/358** (causes disclosed); turn latency **p50 3.7 s / p95 7.8 s**. [Full evaluation](reports/eval-2026-10-05.md).
The LLM judge is not validated (no human labels, no κ), so no headline number uses it; cost is incomplete until Jev has a published price. We report what we measured.

## Limitations and before production

- Mock identity; staff sign-in uses a password only.
- The spend cap is per session; a new login starts a new session.
- Audit records are best-effort; a failed write does not stop the turn.
- One Fargate Spot task; an interruption means 1–2 minutes of downtime.
- Portuguese replies and test cases have no native-speaker review.

[All known limitations and work before production](docs/limitations.md).

## Run it

| Part | Command |
|---|---|
| Pipeline (offline tests) | `uv sync && uv run pytest -m "not snowflake"`; the full reproduce steps are in [`docs/data-pipeline.md`](docs/data-pipeline.md) |
| Agent | `cd agent && uv sync && uv run pytest`; local stack and terminal chat in `agent/README.md` |
| Web | `cd web && npm ci && npm test && npm run e2e` |
| Realtime | `cd infra/realtime && npm ci && npm test` |
| As-is analysis | `cd analysis && uv run pytest` |
| Evaluation harness | `cd eval && uv run pytest` |
| Infrastructure | `terraform test` in each root under `infra/terraform/`; applies need the owner's AWS SSO profile |

Team: Andrés Zeballos (data pipeline, infrastructure, UI) and Carlos Huapaya (agent, AI, evaluation).
