# bankagent: agent core (spec: `docs/design/2026-09-29-agent-core-design.md`)

LangGraph workflow on AgentCore Runtime. Code decides every route and enforces identity, permissions and the dispute
policy; Jev (TypeSafe, `jev-1.13.0`) makes bounded decisions; OpenAI-compatible models on Amazon Bedrock extract
details and write replies. Live smoke results (Jev, Bedrock, serving latency) and the definition-of-done transcript:
`docs/smoke-results.md`.

## Setup
```bash
cd agent && uv sync
uv run pytest            # offline suite (no network)
```
Local data (dev only, until the pipeline export exists): `uv run python scripts/build_local_serving.py`, then
`uv run python scripts/pick_demo_users.py`. Local stack: see the header of `docker-compose.yml`, then
`uv run python scripts/chat.py --user demo01 --password demo-01`.

## Environment
| Variable | Meaning |
|---|---|
| `SERVING_URI` | `s3://<bucket>/serving` or a local directory with `latest.json` |
| `JEV_API_KEY` | TypeSafe key (Secrets Manager in AWS; never committed) |
| `JEV_URL`, `JEV_MODEL` | TypeSafe Decisions endpoint and model (`jev-1.13.0`) |
| `LLM_EXTRACT_MODEL`, `LLM_COMPOSE_MODEL` | override `llm/models.yaml` (Bedrock model ids) |
| `TABLE_PREFIX`, `DYNAMODB_ENDPOINT`, `AWS_REGION` | DynamoDB tables `<prefix>-checkpoints/disputes/handoffs/decision_records` (region `us-east-1`) |
| `IDP_ISSUER`, `IDP_AUDIENCE`, `IDP_JWKS_URL` | mock IdP the agent trusts |
| `AWS_PROFILE` | credentials for Bedrock (SigV4 to the Bedrock Mantle endpoint) and the S3 serving set |

Models per role live in `llm/models.yaml` (currently `openai.gpt-oss-20b` for `extract` and `openai.gpt-oss-120b`
for `compose`, over the Bedrock Mantle chat-completions endpoint). Every call is input-to-JSON with a schema;
OpenAI has no tools.

## AgentCore deployment notes (spec 3 does the deployment)
Configure the runtime with a `CUSTOM_JWT` authorizer (discovery URL = the IdP's `/.well-known/openid-configuration`,
allowed audience `bankagent`) and `requestHeaderAllowlist: ["Authorization"]`; the agent re-verifies the token anyway.

## Data and privacy
- Jev receives transaction aliases (`c1…cN`) and non-identifying fields, never transaction, customer or product ids.
- Before sending dataset records to Bedrock or TypeSafe, the organizers' data-use confirmation is required (spec §12);
  without it, run the demo on the labeled synthetic fixture (`tests/fixtures/serving_fixture.py`). The organizers'
  confirmation was recorded on 2026-10-05.
- `config/demo_users.yaml` holds labeled test identities and is gitignored.

## Live smoke
Each script below calls a real service and runs **only with the owner's approval** of that specific run:
`scripts/smoke_jev.py` (one Jev request, synthetic state), `scripts/smoke_bedrock.py` (one call per role, synthetic
input) and `scripts/smoke_serving.py` (serving read latency; local directory or `s3://`). Results are appended to
`docs/smoke-results.md`.

## Known limitations
- Dispute policy and thresholds are labeled synthetic starting values, not calibrated (spec 2 tunes them).
- No Portuguese-speaking customers exist in the dataset; Portuguese is a session choice and PT test cases are team-written.
- One dispute per transaction; re-disputes go to a human.
- Refusals fall back to templates (the SDK's refusal middleware only covers beta endpoints).
- AgentCore `/ping` can only report Healthy/HealthyBusy; data outages surface in replies with an offer of a human.
- Decision-record writes are best-effort: a logging outage is logged but does not fail the customer's turn.
- `scripts/build_local_serving.py` approximates the pipeline export for development only.
- The gpt-oss models occasionally emit malformed JSON (a decoder restart or a split value mid-object). The boundary
  rejects it (`llm/client.py`) and the reply falls back to the fixed template; see `tests/test_llm.py`.
- `scripts/pick_demo_users.py` picks customers with an approved purchase and a declined payment; scenario data beyond
  that (for example a genuine double charge) needs an identity picked by query — report gaps, never fabricate.
