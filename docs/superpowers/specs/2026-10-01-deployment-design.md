# Deployment design: one-account AWS CDK stack, GitHub deploys and operations

Date: 2026-10-01 · Status: draft for review · Owner: Carlos
Related: `docs/superpowers/specs/2026-09-29-agent-core-design.md` (§3 architecture, §7 tables, §8 failures, §9.2 runtime needs), `docs/superpowers/specs/2026-09-30-ui-design.md` (§3 architecture, §4 change requests, §10 failures, §13 definition of done), `docs/superpowers/specs/2026-09-26-data-pipeline-design.md` (§5.4 serving export, §7 access), `docs/superpowers/specs/2026-10-01-evaluation-design.md` (§6 report setup), AWS skills `aws-cdk`, `agents-deploy`, `agents-harden`, `aws-observability`

## 1. Purpose and scope

This is the deployment half of the agent-core spec's "spec 3". The UI spec covered the surfaces and left out "deploying the AgentCore runtime and the identity service". This spec deploys every component of the system and covers the operations story.

It answers brief item 6, **"a credible route to operation"**: demonstrate tracing, bounded retries, safe fallback and a reproducible setup, and explain capacity limits, monitoring, access controls, data retention and the remaining deployment work. Tracing, retries and fallback behaviour are already specced in the agent core; this spec makes them run, observable and reproducible in AWS.

**In scope:**
- infrastructure as code for every AWS resource the other specs need;
- CI checks and continuous deployment from GitHub;
- the identity service's hosting;
- IAM, secrets and retention;
- tracing, metrics, alarms and an ops dashboard;
- the capacity statement and the remaining-work list.

**Out of scope:**
- application behaviour (already specced elsewhere);
- the Snowflake pipeline itself (only its S3 role lives here);
- alarm notifications;
- cost guardrails;
- post-deploy smoke tests with automatic rollback;
- Snowflake app-event streaming.

The last four are listed as remaining work (§9).

**Decisions taken (2026-10-01):**

| Topic | Decision |
|---|---|
| Accounts and environments | **One AWS account** (the owner's, admin access), **one environment `demo`**, region us-east-2. Staging and production are remaining work (§9). |
| Automation level | IaC plus continuous deployment: GitHub Actions deploys on every push to `main` |
| IaC tool | AWS CDK in Python (`infra/`, uv), with CloudFormation L1 resources where no L2 construct exists |
| Stack structure | One CDK app, six stacks split by lifecycle (§3), deployed in one workflow |
| Identity service hosting | The Python `identity/` unit as one Lambda behind an API Gateway HTTP API |
| Web build | Amplify Hosting, auto-build **off**; the deploy workflow starts the build after CDK |
| Operations built | CloudWatch alarms and one ops dashboard. **No email or SNS notifications**: alarm state shows on the dashboard only. |

## 2. Facts this design rests on

- **Brief:** the submission "is not expected to operate a live banking service"; a prototype "with evidence of production readiness and an honest account of the work required before deployment" is what's asked. So a single environment is enough, and the remaining work is written down rather than built.
- **Deadline:** submissions close 2026-10-05.
- **AgentCore Runtime** (UI spec §2): it passes `Authorization` through to the container and strips other headers except `X-Amzn-Bedrock-AgentCore-Runtime-Custom-*`. Sessions are keyed by the runtime session id. The container is ARM64 and serves `/invocations` and `/ping`.
- **The AgentCore JWT authorizer and the AppSync authorizer both need the identity service's discovery URL over HTTPS**, so identity must deploy before both.
- **Amplify Hosting SSR** reads server secrets from secret environment variables; route handlers get AWS access through an IAM compute role (to be verified, UI spec §2).
- **AgentCore Observability** needs CloudWatch Transaction Search enabled once per account, and the ADOT Python distro in the container.
- **The data pipeline already uses GitHub OIDC** (for Snowflake). AWS gets the same pattern: no stored AWS keys anywhere.
- **Inconsistencies fixed by this spec:**
  - pipeline spec §7 says "Agent (Fargate) task role", but the agent runs on AgentCore;
  - local `.env` uses `TYPESAFE_API_KEY` while the agent core reads `JEV_API_KEY`. `JEV_API_KEY` is the name everywhere.

## 3. Stacks

One CDK app in `infra/` (`infra/app.py`, `cdk.json`, its own `pyproject.toml`). Environment `demo`, us-east-2. Every resource name is prefixed `lb-demo-`. Stacks are listed in deploy order; each consumes only outputs of stacks above it, so CDK orders them.

| # | Stack | Owns | Changes |
|---|---|---|---|
| 1 | `Data` | The six DynamoDB tables: `checkpoints`, `disputes`, `handoffs`, `decision_records` (agent-core §7.2), `sessions`, `conversation_messages` (UI §4). On-demand billing, point-in-time recovery on, TTLs as specced, Streams on `conversation_messages`, `handoffs` and `decision_records`. The serving bucket: block public access, TLS-only bucket policy, SSE-S3, a lifecycle rule on `serving/` as a backstop to the export's own cleanup. The `SI_SERVING` role that Snowflake assumes (pipeline §5.4). | Rarely. `RemovalPolicy.RETAIN` on every resource; termination protection on. |
| 2 | `Identity` | The `identity/` Lambda (Python 3.12, ARM64) behind an API Gateway HTTP API. The issuer is the API's default `https://<api-id>.execute-api.us-east-2.amazonaws.com` URL. Stage throttling: rate 10/s, burst 20. Reads the RS256 signing key from Secrets Manager. | Occasionally |
| 3 | `Agent` | ECR image asset (ARM64, tagged with the git SHA) → `AWS::BedrockAgentCore::Runtime` with a `CustomJWTAuthorizer` (discovery URL from `Identity`, the allowed audience), PUBLIC network mode (egress to Bedrock, TypeSafe and S3), runtime endpoint `live`. The execution role (§4.2). Environment: table prefix, serving URI, issuer, model config, `GIT_SHA`, the secret's name for `JEV_API_KEY` (read at startup). | Every agent change |
| 4 | `Realtime` | AppSync Events API with namespaces `session`, `queue` and `trace`, and the `onSubscribe` handler (UI §3). The Lambda authorizer (verifies realtime tokens against cached JWKS). The `realtime-publisher` Lambda on the three Streams: bisect on error, `ReportBatchItemFailures`, 5 retries, SQS on-failure destination (the DLQ). | Occasionally |
| 5 | `Web` | Amplify app connected to the GitHub repo: branch `main`, app root `web/`, platform `WEB_COMPUTE`, **auto-build off**. The SSR compute role (§4.2). Branch environment variables from the stacks above (issuer URL, runtime ARN, AppSync endpoints, table names). The cookie-signing key as a secret environment variable. | Rarely |
| 6 | `Ops` | CloudWatch alarms and the `lb-demo-ops` dashboard (§6). No SNS topic. | Occasionally |

Splitting by lifecycle keeps stateful resources in a stack that almost never changes. A broken agent or web deploy cannot replace a table or the bucket.

## 4. Access controls

### 4.1 Trust paths

No browser ever holds AWS credentials. Each hop authenticates.

| From → To | How |
|---|---|
| Browser → BFF | httpOnly, Secure, SameSite=Lax cookie holding the 15-minute JWT |
| BFF → identity | HTTPS; login and OTP routes are public and throttled at the HTTP API stage |
| BFF → AgentCore | SigV4 from the Amplify compute role (`bedrock-agentcore:InvokeAgentRuntime` on this runtime ARN only) **plus** the customer's Bearer JWT, which the AgentCore authorizer checks and `app.py` re-verifies. If task 1 finds that a JWT-authorized runtime is Bearer-only, the BFF calls with the Bearer token alone and the compute role loses that permission. |
| Browser → AppSync | Subscribe-only realtime token → Lambda authorizer → `onSubscribe` channel check (UI §3 rule 4) |
| Publisher → AppSync | IAM, `appsync:EventPublish` on this API only |
| Snowflake → S3 | The `SI_SERVING` role with an external-ID trust condition, `serving/*` only |
| GitHub → AWS | OIDC. The deploy role trusts only `repo:<org>/<repo>:ref:refs/heads/main`; a read-only diff role trusts `pull_request` |

### 4.2 Roles

One role per principal, least privilege, no `*` resource except where the service requires it (X-Ray, CloudWatch `PutMetricData`), each with a written reason.

| Role | Allowed |
|---|---|
| Agent execution | `bedrock:InvokeModel*` on the two configured model or inference-profile ARNs. `s3:GetObject` and `s3:ListBucket` on `serving/*`. DynamoDB item operations on its six tables and their indexes, with no `Scan`, and no `DeleteItem` on `disputes` or `handoffs`. `secretsmanager:GetSecretValue` on `lb-demo/jev`. ECR pull. Logs, X-Ray, and metrics in namespace `LatamBank`. |
| Identity Lambda | `GetSecretValue` on `lb-demo/idp-signing-key`; logs |
| Publisher Lambda | Read on the three streams; `appsync:EventPublish`; `sqs:SendMessage` to the DLQ |
| AppSync authorizer | Logs only (JWKS is fetched over HTTPS) |
| Amplify compute | Read and write on `sessions`, `conversation_messages` and `handoffs`; read on `decision_records`; `InvokeAgentRuntime` (subject to §4.1) |
| GitHub deploy | `sts:AssumeRole` into the CDK bootstrap roles only |
| GitHub diff | `sts:AssumeRole` into the CDK lookup role only |

### 4.3 Secrets

- **Secrets Manager:**
  - `lb-demo/jev`, the TypeSafe key;
  - `lb-demo/idp-signing-key`, the RSA private key (the `kid` is published in the JWKS);
  - `lb-demo/amplify-github-token`, used by CDK to connect Amplify to the repo.
- **Secret creation:** all three are created by `bootstrap.sh`, not by CDK, so a deploy can never rotate or delete them. CDK only references them by name.
- **Amplify secret environment variables:** the cookie-signing key.
- **Never stored** in the repo, GitHub secrets or logs. GitHub holds only the two role ARNs, which are not secret.
- **Rotation:** manual for the prototype. The README documents signing-key rotation (add the new key to the JWKS, switch signing, remove the old key after 15 minutes).

### 4.4 Data protection

- DynamoDB and S3 are encrypted at rest with AWS-owned keys. Customer-managed KMS keys are remaining work.
- The curated marts hold no names, contact details or full card numbers (pipeline §5.3), so the stores hold pseudonymous ids, transaction facts and transcript text.
- **Logs never include message text by default.** `LOG_MESSAGE_TEXT` defaults to `false` and stays off in `demo`. Decision records store input hashes plus model outputs (agent-core §7.4).

### 4.5 Retention

| Data | Kept for |
|---|---|
| `checkpoints` | 30 days (TTL) |
| `decision_records`, `conversation_messages` | 90 days (TTL) |
| `sessions` | 90 days (TTL, matching messages) |
| `disputes`, `handoffs` | No TTL in the prototype; a 1-year policy is remaining work |
| CloudWatch log groups | 30 days, set on every group CDK creates |
| Serving runs | The last 3 (pipeline §5.4), with a 30-day lifecycle backstop |
| DynamoDB point-in-time recovery | 35 days (service default) |

## 5. CI/CD

### 5.1 Workflows

`.github/workflows/pipeline.yml` (the data pipeline) stays as specced and runs independently.

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | pull request | `agent-test`: uv pytest, offline. `web-test`: Vitest, the `onSubscribe` `EvaluateCode` tests, Playwright with mocked backends, the axe scan. `infra-check`: infra pytest (§8), `cdk synth` with cdk-nag, `cdk diff` using the diff role, posted as a PR comment, then the stateful-replacement guard (§7). |
| `deploy.yml` | push to `main`, `paths-ignore: docs/**`; `concurrency: deploy-demo` with `cancel-in-progress: false` | `test` (same as CI) → `deploy` on `ubuntu-24.04-arm` (native ARM64 image build, no QEMU): `cdk deploy --all --require-approval never` → `web`: `aws amplify start-job --branch-name main --job-type RELEASE`, then poll until it finishes → `verify` (§5.3) |

### 5.2 Ordering and traceability

- Amplify auto-build is off, so the web never builds against stale environment variables. It is built only after CDK has updated them.
- The agent image tag and the runtime's `GIT_SHA` environment variable are the commit SHA. `app.py` writes `GIT_SHA` into every decision record's versions. The evaluation report reads it as "agent git SHA" (evaluation spec §6, item 1).
- The web build gets `NEXT_PUBLIC_GIT_SHA` and shows it in the footer of staff pages.

### 5.3 `verify` job

A health check, not a functional smoke test:

- the issuer's `/.well-known/openid-configuration` returns 200 and its JWKS has exactly one key;
- `GetAgentRuntime` reports status `READY`, and the `live` endpoint points at the version just deployed;
- the Amplify job ended `SUCCEED`, and `GET /login` returns 200.

Any failure marks the deploy red. There's no automatic rollback (§7).

### 5.4 One-time bootstrap (`infra/bootstrap.sh` plus README)

The bootstrap runs once from the owner's laptop with admin credentials. After it, every change ships through `deploy.yml`.

1. `cdk bootstrap aws://<account>/us-east-2`.
2. Enable CloudWatch Transaction Search (for AgentCore Observability).
3. Create the GitHub OIDC provider and the deploy and diff roles (a small `Bootstrap` CDK stack deployed only by this script).
4. Create the three secrets. Values are read with a silent prompt and never echoed.
5. First `cdk deploy --all`, then the Amplify job, from the laptop.
6. Snowflake:
   1. `CREATE STORAGE INTEGRATION SI_SERVING` with the role ARN from the `Data` stack output.
   2. `DESC INTEGRATION` → put its IAM user ARN and external ID into `cdk.context.json`.
   3. Redeploy `Data`, which narrows the role's trust to that principal and external ID.
7. `scripts/seed_demo.py`: checks that the tables are empty and that the scenario identities config (UI §4.9) resolves to customers present in the serving set.

## 6. Observability

### 6.1 Tracing

- The agent container runs under the ADOT Python distro (`opentelemetry-instrument`) and exports to AgentCore Observability, which shows in CloudWatch GenAI Observability and X-Ray.
- Each graph node is a span with the attributes `session_id`, `turn_id`, `node` and `kind`. Jev, Bedrock, DynamoDB and S3 calls are child spans (botocore and httpx are auto-instrumented).
- **Change request to the agent core (additive):** each decision record also stores `trace_id`. The staff trace page shows a "CloudWatch trace ↗" link, so the audit view (decision records) and the latency view (traces) point to each other.
- The identity, publisher and authorizer Lambdas have active X-Ray tracing.

### 6.2 Metrics

`app.py` emits CloudWatch embedded-metric-format log lines (no extra API calls). Namespace `LatamBank`, dimension `Language`:

| Metric | Extra dimension |
|---|---|
| `TurnLatencyMs` | none |
| `TurnCount` | `Route`: `act`, `clarify`, `abstain`, `handoff`, `safe_fallback` |
| `HandoffCount` | `Priority` |
| `JevErrorCount`, `JevLatencyMs` | none |
| `LlmErrorCount`, `LlmLatencyMs` | `Role`: `extract`, `compose` |
| `TemplateFallbackCount` | none |
| `InjectionBlockedCount` | none |

Lambda, DynamoDB, AppSync, SQS, API Gateway and Amplify metrics come from AWS.

### 6.3 Alarms

There are no notifications; alarm state is read from the dashboard. Thresholds are sized for demo traffic. Missing data counts as `notBreaching`, so a quiet stack stays green.

| Alarm | Condition |
|---|---|
| Turn latency | p95 `TurnLatencyMs` > 15 s in 3 of 5 one-minute periods |
| Safe-fallback rate | `safe_fallback` / `TurnCount` > 20% over 10 minutes, with at least 5 turns |
| Jev failing | `JevErrorCount` ≥ 5 in 5 minutes |
| Bedrock failing | `LlmErrorCount` ≥ 5 in 5 minutes |
| Realtime DLQ | `ApproximateNumberOfMessagesVisible` > 0 |
| Publisher lag | stream `IteratorAge` > 60 s |
| DynamoDB throttling | `ThrottledRequests` > 0, summed across the six tables |
| Identity errors | HTTP API 5xx ≥ 3 in 5 minutes, or Lambda `Errors` ≥ 3 in 5 minutes |
| Web errors | Amplify `5xxErrors` ≥ 5 in 5 minutes |

A composite alarm, **`DemoUnhealthy`**, is in alarm when any of the above is. It's the one status to check before a demo.

### 6.4 Dashboard `lb-demo-ops`

One page, five rows:

1. **Outcomes:** turns by route, handoffs by priority, injection blocks; split by language.
2. **Latency:** turn p50 and p95, Jev p95, Bedrock p95 per role.
3. **Dependencies:** Jev errors, Bedrock errors, template fallbacks.
4. **Realtime:** publisher invocations and errors, iterator age, DLQ depth, AppSync connections.
5. **Platform:** identity 4xx and 5xx, DynamoDB throttles and consumed capacity, Amplify requests and 5xx, an alarm-status widget with every §6.3 alarm, and `DemoUnhealthy`.

This is the operator view. Quality metrics stay in the evaluation report. The UI spec's "no metrics dashboard" still holds: this dashboard lives in CloudWatch, not in the app.

## 7. Failure handling

Runtime behaviour is specced in agent-core §8 and UI §10. This table covers deployment and platform failures.

| Failure | Behavior |
|---|---|
| A test or `cdk deploy` fails | `deploy.yml` stops. CloudFormation rolls the failing stack back to its last good state; stacks already deployed stay. The web isn't rebuilt. |
| Amplify build fails | The previous build keeps serving. The deploy is red. |
| `verify` fails | The deploy is red. Roll back as below. |
| The runtime update fails to stabilize (bad image or environment) | The runtime resource update fails, and CloudFormation restores the previous configuration. |
| Jev secret missing or invalid | `app.py` still starts and `/ping` stays healthy. Every Jev call fails → clarify or handoff (agent-core §4.4). The `Jev failing` alarm turns red. No other model substitutes. |
| Identity service down | No new logins. Existing tokens keep verifying from cached JWKS until they expire (at most 15 minutes). |
| A deploy would replace or delete a stateful resource | The stateful-replacement guard in `infra-check` fails the PR when the `cdk diff` for `Data` shows a removal or replacement. `RETAIN` keeps the resource if it gets through anyway. |

**Rollback runbook (README):**
1. `git revert` the bad commit and push; the normal deploy restores the previous state.
2. Emergency only, when the agent alone is broken and a deploy is too slow: point the `live` runtime endpoint at the previous runtime version with `UpdateAgentRuntimeEndpoint`, then revert in git so IaC matches again.

## 8. Capacity limits

Each value is filled in during plan task 1 from Service Quotas and documentation, plus single-user measurements after the first deploy. The README labels each value "quota" or "measured".

| Component | What limits it |
|---|---|
| AgentCore Runtime | One microVM per session; the concurrent-session quota; cold-start time (measured). Turn budget 20 s (agent-core §8). |
| Bedrock | On-demand token and request quotas per minute for Haiku 4.5 and Sonnet 5.5 in us-east-2. Expected to be the first ceiling under load. |
| Jev (TypeSafe) | Alpha endpoint, unpublished rate limit. Measured where possible; stated as a risk. |
| DynamoDB | On-demand. `decision_records` is partitioned by session, so there's no hot key at demo scale. |
| DuckDB over S3 | Per-turn read latency, measured. The fallback is the 90-day agent export (agent-core §7.1). |
| AppSync Events | Connection and publish quotas, far above demo needs |
| Amplify SSR | Request timeout vs the 20 s turn. The fallback is 202-plus-push (UI §10). |
| Identity HTTP API | Stage throttling 10 rps, burst 20 |

No load test is run. The README states capacity from quotas and measured single-user latency, labeled as such.

## 9. Remaining deployment work

This goes in a README section, in this order:

1. **Identity:** replace the mock IdP with a real one (Cognito or the bank's IdP) with MFA.
2. **Environments:** before production, separate staging and production environments (ideally separate AWS accounts) with promotion between them. The prototype runs a single `demo` environment in one account.
3. **Safer deploys:** a post-deploy functional smoke test with automatic rollback, and canary traffic on the AgentCore endpoint.
4. **On-call:** alarm notifications routed to on-call (SNS to paging) and a runbook per alarm.
5. **Cost guardrails:** AWS Budgets, a per-turn cost metric and a cost alarm.
6. **Hardening:** customer-managed KMS keys, automatic secret rotation, WAF on Amplify and the HTTP API, a custom domain.
7. **Retention:** a policy for `disputes` and `handoffs` (1 year, then archive), and a deletion process for data-subject requests.
8. **Private networking:** AgentCore VPC mode with VPC endpoints for S3, DynamoDB and Bedrock; egress allowed only to TypeSafe.
9. **Capacity:** load testing and quota increases.
10. **Analytics:** stream app events (sessions, disputes, decision records) to Snowflake, so ops metrics and the baseline share one warehouse.
11. **Data use:** approval for sending dataset records to Bedrock and TypeSafe (open item carried from earlier specs).

## 10. Testing

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

## 11. Definition of done

- `infra/` deploys all six stacks into a clean account by following `bootstrap.sh` and the README.
- A push to `main` runs `deploy.yml` green through `verify`. A PR shows its `cdk diff` and passes `infra-check`.
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

## 12. Open items and risks

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
