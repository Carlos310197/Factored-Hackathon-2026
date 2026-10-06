# Controls: where each one is enforced

Code and YAML make the decisions. Jev thresholds bound the judgments. Prompts only shape wording.

| Control | Enforced in | Proven by |
|---|---|---|
| Customer id comes only from the verified JWT `sub`, never from the message or body | Code: `agent/src/bankagent/auth/tokens.py:47-56`, `agent/src/bankagent/app.py:51-63`; BFF body schema `web/app/api/chat/route.ts:10-16` | `test_app.py::test_payload_customer_id_is_ignored`, `::test_tampered_token_rejected`, `::test_expired_token_reports_session_expired_in_requested_language` |
| Every read is scoped to the session's customer; a foreign record and a missing one return the same `NotFound` | Code: `agent/src/bankagent/tools/read.py:20-24,51-83` | `test_read_tools.py::test_foreign_and_missing_transactions_are_indistinguishable`, `::test_accounts_only_own`, `::test_scope_required` |
| Filing a dispute re-checks scope, ownership and the policy inside the tool | Code + YAML: `tools/write.py:52-60`, `policy/dispute_policy.yaml`, `policy/dispute.py:60-97` | `test_write_tools.py::test_foreign_transaction_is_not_found`, `::test_declined_rejected_by_policy_and_not_written`, `test_policy.py` |
| Filing needs a confirmation on a summary card built in code. The card's button sends `confirm:<card_hash>` and code checks it by equality against the pending card (no extract or Jev call; a stale or forged token files nothing and shows the card again); a free-text "sí" goes through Jev (p ≥ 0.90). Either way the hash is re-checked against the freshly read record before writing | Code: `graph/nodes.py` (`understand` token check, `_card_hash`, `file_dispute`); Jev threshold for free text: `decisions/thresholds.v1.yaml:22`, `decisions/routing.py:212` | `test_graph_paths.py::test_confirm_token_files_without_extract_or_jev`, `::test_stale_confirm_token_does_not_file`, `::test_dispute_confirm_file_verify`, `::test_confirmation_is_bound_to_the_card_the_customer_saw`, `test_routing.py::test_confirmation_outcomes` |
| No duplicate disputes; an unknown write outcome is settled by a read-back, not a blind retry | Code + DynamoDB: conditional put `store/repos.py:21`, read-back `tools/write.py:73-89` | `test_write_tools.py::test_unknown_write_outcome_resolved_by_read_back`, `test_graph_failures.py::test_duplicate_dispute_is_not_filed_twice` |
| Replies can't mention ids the customer doesn't own; claims are verified; one regeneration, then a template | Code + Jev: `guards.py:4-8`, `graph/nodes.py:618-651`, `decisions/verify.py` | `test_graph_failures.py::test_foreign_id_in_reply_is_blocked`, `::test_unverified_claims_regenerate_once_then_template` |
| Prompt injection is refused, then handed off; Jev only sees aliases of the customer's own candidates | Jev signal + code: `routing.py:157-180`, aliases `decisions/understand.py:94`, `routing.py:50` | `test_graph_failures.py::test_injection_refused_then_handed_off`, `test_decisions.py::test_request_uses_aliases_and_never_sends_ids` |
| The LLM has no tools; every graph edge is chosen in code | Code: `graph/build.py`, `llm/client.py` (JSON-schema output only) | `test_llm.py::test_compose_uses_json_schema_format_and_hides_fixed_block` |
| Human handoff for > 500 USD, fraud score > 30, unauthorized charges, legal threats | YAML + code: `dispute_policy.yaml:7-10`, `routing.py:121-154`, `handoff/packet.py` | `test_graph_paths.py::test_unrecognized_charge_drafts_dispute_and_hands_off`, `::test_legal_threat_hands_off_with_high_priority` |
| Runtime and realtime authorization | Infra + code: AgentCore `custom_jwt_authorizer` (`infra/terraform/agent/runtime.tf:20-29`); realtime rules (`infra/realtime/authorizer/rules.ts`): a customer subscribes only to `session/<own sid>` | `infra/terraform/agent/tests/agent.tftest.hcl`, `infra/realtime/test/authorizer.test.ts` |
| Staff credentials are never published | Code: `identity/app.py` `demo_users` returns customers only; the BFF returns `[]` for staff | `test_identity_ui.py::test_demo_users_only_in_demo_mode`, `web/tests/unit/auth-routes.test.ts` |

Paths without a prefix are under `agent/src/bankagent/` (code) or `agent/tests/` (tests).

## Failure behaviour (offline, deterministic fakes)

From `agent/tests/test_graph_failures.py`, `test_app.py` and `test_write_tools.py`. Each row is a test.

| Injected failure | What the customer sees | What is written |
|---|---|---|
| Jev down twice | A clarification, then a handoff notice | Handoff (`jev_unavailable`); no dispute |
| Jev down while the customer says "sí" | The summary card again | No dispute |
| Confirmation unclear 3 times | Asked again twice, then a handoff | Handoff (`confirmation_unclear`); no dispute |
| Same transaction disputed again in a new session | "Already disputed", with the existing reference | Still exactly 1 dispute |
| Injection attempt, twice | A refusal, then a handoff | Handoff (`injection_repeated`, high priority) |
| LLM compose fails | Template reply built from the receipts | Decision record `template` |
| Jev rejects the reply's claims | One regeneration, then the template | 2 drafts, 2 verifications |
| LLM puts another customer's transaction id in the reply | Template reply without it | Decision record `guard`; Jev never called |
| Serving data unavailable | "Can't access your information" + offer of a human | Nothing; Jev never called |
| Token without `dispute:create` | Abstain + offer of a human | No dispute |
| Turn budget spent | Template reply | Compose never called |
| Missing, expired or tampered token; JWKS unreachable | "Log in" / "session expired" / `identity_unavailable` | Workflow never runs |
| Write lands, then the call times out | Success with the same dispute id | Exactly 1 record |

Not covered end to end yet: a failed write turning into a handoff, and a read-back mismatch turning into a handoff (each is
unit-tested; the graph wiring is not).

## Deployed layers

The whole system as deployed, with the 10 numbered flows explained beside it. The SVG and PNG embed the draw.io source, so either opens for editing in draw.io. [System diagram](diagrams/system-architecture.drawio.svg).

| Layer | What | Where |
|---|---|---|
| Data | Organizer S3 drop → Snowflake `RAW` → dbt `STAGING` (typed, deduplicated, quarantined) → `CURATED` (enforced contracts) → versioned parquet + `latest.json` pointer | [`docs/data-pipeline.md`](data-pipeline.md), `dbt/`, `pipeline/`, [`docs/diagrams/pipeline.svg`](diagrams/pipeline.svg) |
| Agent | LangGraph workflow on Amazon Bedrock AgentCore Runtime (JWT authorizer). LLM: `mistral.ministral-3-14b-instruct` (extract) and `openai.gpt-oss-120b` (compose) on Bedrock. Typed decisions: Jev (`jev-1.13.0`) | `agent/`, [`docs/diagrams/agent-core.svg`](diagrams/agent-core.svg) |
| State | DynamoDB: checkpoints, disputes, handoffs, decision records, sessions, conversation messages | `infra/terraform/data/` |
| Web | Next.js customer chat, staff console, trace view and demo stage; the BFF holds the token in an httpOnly cookie | `web/`, [`docs/diagrams/ui-architecture.svg`](diagrams/ui-architecture.svg) |
| Realtime | AppSync Events: per-session channels, the handoff queue and live trace stages; a Lambda authorizer allows a customer only their own session | `infra/realtime/` |
| Identity | Mock OIDC IdP on Lambda (RS256, JWKS); the customer id lives in the token, never in a message | `agent/src/bankagent/identity/` |
| Infra | Terraform roots `bootstrap`, `platform`, `data`, `identity`, `realtime`, `agent`, `app`; GitHub Actions via OIDC, no stored secrets | `infra/terraform/` |

## Workflow

Factored AI & Data Hackathon 2026. One workflow, built end to end: **account and payment inquiries plus transaction-dispute
intake**, in Spanish and Portuguese, for a synthetic LATAM bank. Code decides every route and enforces identity, permissions
and the dispute policy. Typed judgments (Jev) decide the bounded questions. A language model only turns text into JSON and
writes the reply. Each step of a turn (tool call, judgment, policy check, action, refusal, handoff) is written as a
decision record you can open in the trace view; the write is best-effort (see [Limitations](limitations.md)).
