# Data handling

**Data use.** The organizers confirmed that dataset records may be sent to Snowflake, Amazon Bedrock, TypeSafe (Jev) and the
evaluation persona provider. PII columns (names, document, birth date, contact details, address, credit score, income) never
leave Snowflake `RAW`, and product numbers are cut to the last four digits.

| Party | Receives | Where in code |
|---|---|---|
| Amazon Bedrock, via a role in a second AWS account (the AI Account) | The customer message and the last 2 exchanges (extract); receipts with `customer_id`, `product_id` and fraud fields removed, and fraud triggers dropped from policy rule details and reason codes (compose, handoff open questions) | `llm/extract.py:65-67`, `llm/compose.py` (`redact`), `llm/client.py` (`BEDROCK_ROLE_ARN`) |
| Jev / TypeSafe (external) | `understand`: policy text, session facts, the message, and candidate transactions as aliases `c1..cN` (no transaction, customer or product id) | `decisions/understand.py:95-131` |
| Jev / TypeSafe (external) | `verify_reply`: the reply, its claims and the receipts with `customer_id`, `product_id` and fraud fields removed | `decisions/verify.py` (`REDACTED_FIELDS`); every Jev and Bedrock call in the offline suite is checked: the test doubles refuse any payload with a customer id, product id or fraud field (`tests/fakes.py::assert_no_egress`, `tests/test_egress_guard.py`) |
| Evaluation persona model (OpenCode, offline eval only) | Synthetic goal cards and the simulated conversation; no customer records | `eval/src/evalkit/persona.py` |
| Snowflake | The organizer drop (read from their bucket) and the curated export to our bucket; no chat data | `pipeline/load.py`, `pipeline/export.py` |
| AppSync Events | Message text, control and progress events per session; handoff summaries on the staff queue; node and kind per trace step | `infra/realtime/publisher/map.ts:29-49` |

| Store | Retention |
|---|---|
| Conversation messages, sessions, decision records | 90 days (DynamoDB TTL) |
| Graph checkpoints | 30 days (DynamoDB TTL) |
| Disputes, handoffs | No TTL (they are the record of the case) |
| CloudWatch logs (all services) | 30 days |
| Serving parquet | Newest 3 runs, never the one `latest.json` points to |
| Login ticket / access token | 2 min / 15 min |

All DynamoDB tables have point-in-time recovery and deletion protection.
