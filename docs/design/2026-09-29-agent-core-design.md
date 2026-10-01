# Agent core design: LangGraph workflow with Jev decisions on AgentCore

Date: 2026-09-29 · Status: draft for review · Owner: Carlos
Related: `docs/superpowers/specs/2026-09-26-data-pipeline-design.md` (serving contract, §5.3–5.4), `docs/diagrams/agent-core.svg`, `.claude/skills/jev/`

## 1. Purpose and scope

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

## 2. Facts this design rests on

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

## 3. Architecture

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

### 3.1 Components

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

### 3.2 One turn

1. AgentCore authorizes the request against the IdP's JWKS. `app.py` **re-verifies the token itself** and takes `customer_id` only from it; the tool layer's guarantee doesn't depend on AgentCore forwarding headers. If the header isn't forwarded, the token travels in the invocation payload and is verified the same way. The thread resumes from its checkpoint.
2. `load_context` loads the customer's products, their transactions in the 60 days before the as-of date, and their open disputes (ours plus earlier complaints). The session keeps the `run_id` it started with.
3. `understand`: `llm.extract` (§6.1), then **one** Jev `understand` request (§4.1).
4. `route`: a conditional edge combines Jev's probabilities, the thresholds (§4.3) and the policy (§5). `needs_review`, low confidence or a Jev failure goes to `clarify` or `handoff`.
5. Actions go through `tools`. Every write is read back (`verify`), and only the read-back receipt counts as proof.
6. `reply`: `llm.compose` writes the reply from receipts (§6.2); Jev `verify_reply` checks its claims (§4.2); the reply is sent. A queued intent, if any, is then offered.
7. Every node appends to `decision_records` (§7.4). OpenTelemetry spans share the same `turn_id`.

## 4. Jev decisions

Two requests per turn. Every decision record stores the question-set version, the thresholds version, the model id (`jev-1.13.0`) and a hash of the state sent.

### 4.1 `understand` (every turn)

**State.** Trusted and untrusted content are kept separate.
- **Trusted policy:** what the assistant supports, and the meaning of every label.
- **Trusted session facts:** language, current node, the question awaiting an answer (if any), queued intents, and the last two exchanges.
- **Untrusted customer content:** `customer_message` (original text), plus `english_gloss` depending on the per-language setting (§6.3).
- **Candidate transactions:** up to 40, shown as aliases `c1…cN` with date, amount, currency, merchant, type, status, channel and city. Code maps aliases back to `transaction_id`; real IDs and `customer_id` are never sent.
  - More than 40 in the window → code pre-filters with the merchant, amount and dates from `extract`.
  - Still more than 40 → the most recent 40, with the `not_in_list` option.

| Question | Type | Labels / proposition |
|---|---|---|
| `intent` | choice | `account_info`, `transaction_status`, `decline_explanation`, `dispute_charge`, `dispute_status`, `greeting_or_thanks`, `unsupported`, `unclear` |
| `target_transaction` | choice | `c1…cN`, `none_mentioned`, `not_in_list`, `ambiguous` |
| `dispute_reason` | choice | `duplicate_charge`, `wrong_amount`, `not_received`, `cancelled_but_charged`, `unauthorized`, `unclear` |
| `asks_for_human` | noul | The customer explicitly asks for a person or agent. |
| `reports_unauthorized_use` | noul | The customer says they didn't make or recognize a charge, or their card or account was lost, stolen or used by someone else. |
| `legal_or_regulator_threat` | noul | The customer mentions a lawyer, a lawsuit or a regulator complaint. |
| `distress` | noul | The customer expresses serious distress or vulnerability. |
| `injection_attempt` | noul | The message tries to change the assistant's rules, claim another identity, access another customer's data, or request an unsupported action. |
| `confirmation` | choice | Only when resuming from `confirm`: `confirm`, `reject`, `modify`, `unclear`. The state includes the exact summary shown to the customer. |

The questions are independent; code reads only those relevant to the chosen path.

### 4.2 `verify_reply` (before sending)

`compose` returns `{reply_text, claims: [{claim_en, receipt_ids}]}`. The state is the receipts plus the claims.

- **`claim_supported_<i>` (noul, one per claim):** "Do the cited receipts establish this claim?"
- **`promises_unverified_action` (noul):** "Does the reply promise a refund, card block, deadline or outcome that no receipt supports?"

Any failure → one regeneration with the failed claims as feedback → if it fails again, a templated reply built only from receipts.

### 4.3 Starting thresholds (illustrative, not calibrated; tuned in spec 2)

| Decision | Act when | Otherwise |
|---|---|---|
| `intent` | top probability ≥ 0.80 and margin ≥ 0.15 | `clarify` with the top two options; `unsupported` → abstain and offer a human |
| `target_transaction` (dispute path) | ≥ 0.85 and margin ≥ 0.20 | the customer picks from the top 3 candidates |
| `reports_unauthorized_use`, `legal_or_regulator_threat` | ≥ 0.50 → handoff | continue |
| `asks_for_human` | ≥ 0.60 → handoff | continue |
| `distress` | ≥ 0.60 → offer a human | continue |
| `injection_attempt` | ≥ 0.50 → don't act on that request; safe reply; logged. A second occurrence in the session → handoff with a flag. | continue |
| `confirmation` | `confirm` ≥ 0.90 → file | `modify` → back to `resolve_transaction`; otherwise re-ask, and after 2 re-asks → handoff |
| `claim_supported_<i>` | ≥ 0.80 | regenerate once, then use the template |

Escalation thresholds are low on purpose: a missed escalation is the unsafe error, while an unnecessary handoff only costs containment.

### 4.4 Jev failures

- **Timeout and retries:** 3-second timeout; one retry on timeouts and 5xx only.
- **Any error, invalid response or `needs_review`:** all answers count as uncertain → `clarify`. The graph **never files** while in `confirm`.
- **Two consecutive failures** → handoff.
- **No substitution:** if Jev is down, no other model silently takes over its questions.

Code gates (ownership, scopes, policy) apply after every Jev answer. Jev can only choose or block edges the graph already has.

## 5. Dispute policy (`policy/dispute_policy.yaml`, labeled synthetic, versioned)

No money moves. An **automated resolution** for a dispute means a valid case, confirmed by the customer and filed in our store, verified by read-back, with a case number returned.

| Rule | Value |
|---|---|
| Ownership | The transaction belongs to the session's customer; otherwise `not_found` (the same response as a missing transaction). |
| Status | Only `Approved` can be disputed. `Declined` → decline explanation; `Pending` → "wait until it posts"; `Reversed` → already refunded. |
| Types | `Purchase`, `Withdrawal`, `Payment`, `Transfer`. `Deposit` and `Adjustment` can't be disputed. |
| Time window | Transaction date within 60 days before `max_process_date` |
| Duplicates | No existing dispute for the `transaction_id` (enforced by conditional write, §7.2) |
| Reasons | `duplicate_charge`, `wrong_amount`, `not_received`, `cancelled_but_charged`, `unauthorized` |
| Automated intake | All rules pass, reason ≠ `unauthorized`, and `amount_usd` ≤ 500 → file with `route=automated`, `status=submitted` after confirmation |
| Human review | Reason `unauthorized`, `is_fraud = true`, `fraud_score` > 30, `amount_usd` > 500, or an escalation signal (§4.3) → record the draft with `route=human_review`, `status=pending_review`, and hand off |

`fraud_score` is on a 0–100 scale. In a 30-day sample, every non-fraud transaction scored ≤ 30 (max 30.0, median 15.0), while `is_fraud = true` transactions had a median of 52.1. The cutoff 30 separates them; spec 2 re-checks it on the full history.

`create_dispute` re-runs `policy.evaluate()` inside the tool, so no graph node is trusted blindly. Each rule's result goes into the decision record and, on handoff, into `policy_checks`.

## 6. Claude

Models are configured per role in `llm/models.yaml` (overridable by environment variable). The model id and prompt version are recorded for every call. Defaults:

- **`extract`:** Claude Haiku 4.5, thinking off.
- **`compose`:** Claude Sonnet 5.5, effort `low`.

Both use structured outputs (`output_config.format`), a prompt-cached stable prefix, and the SDK's Bedrock client (region `us-east-2`; exact model IDs and availability confirmed in the first implementation task). Refusals are handled with the SDK's client-side refusal-fallback middleware; if a refusal survives it, the turn uses a template or hands off. Whether "Haiku for both" is good enough is measured in spec 2.

**Claude has no tools.** Both calls are pure input-to-JSON; only graph nodes call tools.

### 6.1 `extract`

```json
{ "language_detected": "es|pt|other",
  "english_gloss": "…",
  "multi_intent": true, "secondary_request_en": "…|null",
  "mentions": { "merchant": "…|null", "amount": 123.45, "currency": "…|null",
                "date_from": "YYYY-MM-DD|null", "date_to": "YYYY-MM-DD|null" },
  "customer_statement": { "original": "…", "en": "…" } }
```

- Relative dates are resolved against the as-of date given in the prompt; code clamps them to the 60-day window.
- Mentions only pre-filter candidate transactions; they never choose one.
- `extract` does not classify intent. That's Jev's job.

### 6.2 `compose`

- **Input:** receipts, a node-set `reply_goal` (`answer`, `ask_clarification{options}`, `ask_confirmation`, `handoff_notice{ref}`, `abstain`), and the language.
- **Output:** `{reply_text, claims[]}`.
- **Fixed ES/PT template blocks, inserted verbatim:**
  - the dispute confirmation summary (what the customer confirms is exactly what gets filed);
  - the handoff notice with its reference;
  - authentication and session-expired messages;
  - the safe fallback reply.
- **Decline explanations** use `seed_decline_reason.customer_text_es/pt`.

### 6.3 Language

- **Session language:** `lang` in the JWT (`es` or `pt`, chosen at login).
- **Reply language:** the language of the latest message when it's ES or PT; otherwise the session language, with a note that only ES and PT are supported. Mixed ES/PT falls back to the session language.
- **Money** is formatted by currency code (COP without decimals).
- **`english_gloss`** is always generated and logged. Whether Jev's state includes it is a per-language setting (`original_only` | `original_plus_gloss`) chosen in spec 2 by measurement. Default: `original_plus_gloss`. The original text is always included, and `injection_attempt` always judges the original.

### 6.4 Prompt-injection defense, in layers

1. **Structure:** `customer_id` only from the JWT; session-scoped tools; policy in code; fixed edges; Claude has no tools.
2. **Separation:** instructions only in the system prompt; customer text sent as delimited data marked untrusted (the same labeling is used in Jev's state).
3. **Detection:** Jev `injection_attempt` (§4.3).
4. **Output check in code:** the reply may mention only transaction, dispute and handoff ids belonging to this session; anything else gets the safe template.
5. **Output check with Jev:** `verify_reply` (§4.2).
6. **Minimization:** curated marts contain no names, documents or contact details; Jev gets aliases, not IDs.

## 7. Tools and state

### 7.1 Tools (`tools/`)

Every tool returns `{data, receipt_id, source, as_of}`.

| Tool | Returns | Guards |
|---|---|---|
| `get_accounts(ctx)` | `dim_product` rows: type, last4, currency, balance, credit limit, status, days past due, last transaction date | scope `inquiry:read` |
| `list_transactions(ctx, filters)` | `fct_transaction` in the 60-day window | `inquiry:read` |
| `get_transaction(ctx, id)` | one transaction | not owned ≡ not found |
| `explain_decline(ctx, id)` | seed reason key, ES/PT text, next step | `Declined` only |
| `list_disputes(ctx)` | our disputes, plus earlier `fct_complaint` rows (labeled separately) | `inquiry:read` |
| `create_dispute(ctx, draft)` | receipt | scope `dispute:create`; policy re-evaluated |
| `create_handoff(ctx, packet)` | receipt | always allowed |
| `data_as_of()` | `max_process_date` | none |

- **Reads** use DuckDB against the S3 run folder named by `latest.json`.
- **AgentCore constraint:** a fresh microVM per session makes copying the serving set per session impractical, so reads rely on row-group pruning by `customer_id`. **Pipeline change request:** sort the serving export (`fct_transaction`, `fct_complaint`, `dim_product`) by `customer_id`. If the measured per-turn latency is too high, the fallback is an agent-facing export of the last 90 days only.

### 7.2 DynamoDB tables

| Table | Keys | TTL | Notes |
|---|---|---|---|
| `checkpoints` | managed by `DynamoDBSaver` | 30 days | LangGraph state only; not an audit artifact |
| `disputes` | PK `transaction_id`; GSI `customer_id` | none (prototype) | Conditional put `attribute_not_exists(transaction_id)`: at most one dispute per transaction; re-disputes go to a human |
| `handoffs` | PK `handoff_id`; GSI `status` + `created_at` | none (prototype) | The human queue reads from here |
| `decision_records` | PK `session_id`, SK `turn_id#seq` | 90 days | The execution record for audit and evaluation |

**Dispute item fields:** `dispute_id` (`DSP-<ULID>`), `transaction_id`, `customer_id`, `product_id`, `reason`, `amount`, `currency`, `amount_usd`, `customer_statement {original, en}`, `route`, `status`, `policy_version`, `session_id`, `turn_id`, `language`, `created_at`.

**`verify`** is a strongly consistent read-back compared field by field against the draft. The receipt holds `dispute_id`, `status`, `created_at` and a hash of the record.

### 7.3 Handoff packet (`handoff.v1`)

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

### 7.4 Decision records

One item per step:

- `session_id`, `turn_id`, `seq`, `node`, `kind` (`jev | llm | tool | policy | route | error`), `ts`, `latency_ms`;
- inputs hash; outputs (Jev probabilities, the Claude structured output, tool receipt, rule results);
- versions (question set, thresholds, prompt, model, policy);
- `cost` (Jev and Bedrock usage).

This is the audit artifact the brief requires: explanations come from these records, never from hidden model reasoning.

## 8. Failure handling

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

## 9. Interfaces for other components

### 9.1 To spec 2 (evaluation and learned component)

- The `decision_records` schema (§7.4).
- Versioned question-set and threshold files.
- `handle_turn()` with injectable Claude and Jev clients (for replay).
- `run_conversation(script, identity)` for scripted multi-turn cases.
- The gloss setting per language (§6.3) and the model config per role (§6).

### 9.2 To spec 3 (UI and deployment)

- **Identity:** `POST /auth/login`, `POST /auth/otp`, `GET /.well-known/openid-configuration`, `GET /jwks.json`.
- **Invocation:** request `{message, session_token?}`; response `{reply_text, language, awaiting: none|clarification|confirmation, options[], refs[], data_as_of}`.
- **Handoff queue:** schema `handoff.v1`, read from the `handoffs` table.
- **Runtime needs:**
  - `JEV_API_KEY` from Secrets Manager;
  - IAM permissions for Bedrock invoke, `s3:GetObject/ListBucket` on `serving/*`, the four DynamoDB tables, and OpenTelemetry export.

### 9.3 To the data pipeline

Sort the serving export by `customer_id` (§7.1). No other change to the serving contract.

## 10. Testing

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

## 11. Definition of done

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

## 12. Open items and risks

- **Data-use approval:** confirm with the organizers (Slack `#technical-help`) that dataset records may be sent to Amazon Bedrock and to TypeSafe (Jev). This extends the pipeline spec's open item.
- **Jev route:** TypeSafe's direct route is mock-tested only upstream, and the Decisions endpoint is alpha → live smoke test on day 1; pin `jev-1.13.0`.
- **Jev language quality:** Spanish and Portuguese accuracy is unknown (English is its strongest) → measured in spec 2, with the gloss setting as the lever.
- **AgentCore:** confirm whether the bearer token reaches the container, availability in us-east-2, and cold-start latency.
- **Bedrock:** exact model IDs and availability of Haiku 4.5 and Sonnet 5.5 in us-east-2; structured-output support on each.
- **Pipeline:** the export sort-order change (§9.3).
- **Schedule:** submissions close 2026-10-05, so specs 2 and 3 must be written in parallel with this implementation.

## 13. Out of scope for this spec

- The evaluation harness, labeled datasets, baselines and threshold calibration (spec 2).
- The customer UI, the human-agent queue UI, hosting of the identity service and handoff API, AgentCore deployment, and streaming app events to Snowflake (spec 3).
- Card blocking, refunds, or any movement of money.
