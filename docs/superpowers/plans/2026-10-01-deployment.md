# Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the whole LATAM Bank system to one AWS account (environment `demo`, us-east-2) from a Python CDK app. GitHub Actions deploys it on every push to `main`, and the deployment is traced, metered, alarmed and documented.

**Architecture:**
- **One CDK app** in `infra/` with six stacks, split by lifecycle:
  1. `LbDemo-Data`: DynamoDB tables (built from the agent's own `TABLE_SPECS`) plus a TLS-only policy on the existing serving bucket;
  2. `LbDemo-Identity`: the mock IdP as a container Lambda behind an HTTP API;
  3. `LbDemo-Agent`: the AgentCore Runtime from an ARM64 image asset, with a JWT authorizer and a `live` endpoint;
  4. `LbDemo-Realtime`: AppSync Events plus the UI plan's TypeScript authorizer and publisher, bundled by CDK;
  5. `LbDemo-Web`: the Amplify app, branch and SSR compute role;
  6. `LbDemo-Ops`: alarms and a dashboard, with no notifications.
- **A separate `LbDemo-GitHub` stack**, deployed only by the bootstrap script, holds the GitHub OIDC roles.
- **Agent changes:** the agent gains a secret-backed settings loader, git-SHA and trace-id stamping on decision records, EMF metrics and per-node spans.
- **The pipeline:** `ci.yml` and `deploy.yml` share one reusable test workflow. `deploy.yml` runs `cdk deploy --all` on an ARM64 runner, then starts the Amplify build, then runs a health check.

**Tech Stack:** AWS CDK v2 (Python 3.12, uv) with `aws-cdk-lib` ≥ 2.220 and `cdk-nag`; CloudFormation L1 `AWS::BedrockAgentCore::Runtime` / `RuntimeEndpoint` and `AWS::Amplify::App` / `Branch`; `aws_appsync.EventApi`; `aws_lambda_nodejs.NodejsFunction` (esbuild) for the UI plan's TypeScript handlers; Mangum (FastAPI on Lambda); ADOT Python (`aws-opentelemetry-distro`); CloudWatch EMF; GitHub Actions with `aws-actions/configure-aws-credentials` (OIDC); pytest and moto.

**Spec:** `docs/superpowers/specs/2026-10-01-deployment-design.md`

**Depends on:**
- `docs/superpowers/plans/2026-09-29-agent-core.md`, Tasks 1–13: the `agent/` package, its Dockerfile and `create_tables` specs. Required before Tasks 2–4.
- `docs/superpowers/plans/2026-09-30-ui.md`:
  - Tasks 2–4 (agent tables and entrypoint changes): required before Task 2;
  - Tasks 7–8 (the realtime handler code): required before Task 8;
  - Tasks 9–23 (the web app): required before Task 9.
- `docs/superpowers/plans/2026-09-26-data-pipeline.md`, Task 2: created the serving bucket `latam-bank-serving-<suffix>` and the Snowflake role `snowflake-serving-writer` **by hand**. This plan references them; it doesn't create them.
- Task 1 has no dependencies and should run first. Tasks 5, 12 and 13 need only Task 1.

**Supersedes in the UI plan** (Task 8 adds a note to that file):
- Task 7 Step 6: the TypeScript `RealtimeStack` and `bin/app.ts`;
- Task 7 Steps 8–9 and Task 8 Steps 5 and 7: the TypeScript stack, its synth, deploy and probe deploy commands;
- Task 24 Steps 2–3: the hand-made BFF IAM policy and the console-created Amplify app.

The handler code and its Vitest tests from UI Tasks 7–8 stay. The probe script stays, and is run against this plan's stack in Task 14.

**Plan status:** written on 2026-10-01 against the agent-core, UI and pipeline plans as written. It was **not executed during planning**. CDK L1 property class names and some AWS facts are checked in Task 1. A failing step means fixing the code, not the test's intent.

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

## Global Constraints

- **Account and region:** one AWS account, region `us-east-2`, environment `demo`. No other environment or account.
- **Names:**
  - stacks: `LbDemo-Data`, `LbDemo-Identity`, `LbDemo-Agent`, `LbDemo-Realtime`, `LbDemo-Web`, `LbDemo-Ops`, and `LbDemo-GitHub` (bootstrap only);
  - resource names start with `lb-demo-`; tables are `lb-demo-<name>`;
  - runtime `lb_demo_agent` with endpoint `live`;
  - dashboard `lb-demo-ops`; composite alarm `lb-demo-DemoUnhealthy`.
- **Secrets (Secrets Manager):** `lb-demo/jev`, `lb-demo/idp-signing-key` and `lb-demo/amplify-github-token`.
  - They're created only by `infra/bootstrap.sh`. CDK references them by name and never creates, rotates or deletes them.
  - Never in the repo, GitHub secrets or logs.
  - GitHub holds only two **repository variables**: `AWS_DEPLOY_ROLE_ARN` and `AWS_DIFF_ROLE_ARN`.
- **The Jev key variable is named `JEV_API_KEY` everywhere**, local `.env` included. In AWS the agent gets `JEV_SECRET_ID=lb-demo/jev` and reads the key at startup.
- **Stateful resources** (the six tables) have `RemovalPolicy.RETAIN`, and `LbDemo-Data` has termination protection on.
- **IAM:** one role per principal. No `Action: "*"`. `Resource: "*"` only for the actions in `infra/tests/test_iam.py::STAR_OK`, each with a reason.
- **Retention:**

  | Data | Kept for |
  |---|---|
  | `checkpoints` | 30 days (TTL) |
  | `decision_records`, `conversation_messages`, `sessions` | 90 days (TTL) |
  | `disputes`, `handoffs` | no TTL |
  | every log group | 30 days |

- **Alarms:** no SNS topic and no alarm actions. Missing data counts as `notBreaching`.
- **Metrics:** namespace `LatamBank`. Observability code is best-effort: it never raises into a customer's turn.
- **Logs:** never include message text (`LOG_MESSAGE_TEXT=false`).
- **Commands:**
  - `infra/`: run from `infra/` (`uv run pytest`, `npx aws-cdk@2 synth`);
  - `agent/`: run from `agent/` (`uv run pytest`);
  - `infra/realtime/`: `npm test`.
  - Before any `infra/` synth or test, run `npm ci` in `infra/realtime/`: `NodejsFunction` bundles with its local esbuild.
- **Approval:** anything that creates or changes AWS resources, or calls Jev or Bedrock, runs **only after the owner explicitly approves that step**.
- **Commits:** each task ends with a commit that stages only that task's files and never `.env*`. End each message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

These five conditions aren't exercised by the spec's scenarios and are the most likely to hurt. Each has a pinned test in the task that owns the code.

1. **The identity Lambda cold-starts while the demo-identities object is missing or unreadable** (seed not run yet, or the object deleted). Expected: `503 {"error":"identity_unavailable"}`, a logged exception, and **no cached failure**: the next request retries and succeeds once the object exists. Pinned in Task 4 (`test_cold_start_failure_returns_503_and_retries`).
2. **The Jev secret is missing or access is denied when the agent starts.** Expected: the container starts with an empty key, a logged error, and Jev calls failing into clarify or handoff. Never a crash loop. Pinned in Task 2 (`test_missing_secret_leaves_key_empty_and_does_not_raise`).
3. **A malformed or unexpected decision record** (no `latency_ms`, a non-dict payload, a `turn_end` without a preceding route, OpenTelemetry not configured). Expected: the record is still written, no exception reaches the turn, and metrics are skipped or partial. Pinned in Task 3 (`test_observer_never_raises_on_odd_records`).
4. **A `cdk diff` for `LbDemo-Data` that replaces or removes a table, printed with ANSI colour codes** (as the CDK CLI does in CI). Expected: the guard exits non-zero and names the resource. Pinned in Task 13 (`test_guard_flags_replacement_with_ansi_codes`).
5. **A deploy that fails mid-way** (for example `LbDemo-Agent` fails after `LbDemo-Identity` updated). Expected: the Amplify build and `verify` never start, and a later push isn't cancelled mid-deploy. Pinned in Task 13 (`test_deploy_jobs_are_chained_and_never_cancelled`).

## File Structure

```
agent/                                              (existing; agent-core + UI plans)
  pyproject.toml, uv.lock            + mangum, aws-opentelemetry-distro, dev opentelemetry-sdk   (Tasks 3, 4)
  Dockerfile                         ADOT entrypoint                                            (Task 3)
  Dockerfile.identity                Lambda image for the mock IdP                              (Task 4)
  src/bankagent/settings.py          + git_sha, load_settings() (Jev key from Secrets Manager)  (Task 2)
  src/bankagent/app.py               runtime() uses load_settings(); turn_end + language        (Task 2)
  src/bankagent/store/tables.py      sessions TTL                                               (Task 2)
  src/bankagent/store/repos.py       DecisionLog.append(trace_id=…); SessionRepo ttl            (Task 2)
  src/bankagent/observability.py     ObservedLog, EMF, route classes, node spans                (Task 3)
  src/bankagent/runtime.py           wraps store.log with ObservedLog                           (Task 3)
  src/bankagent/graph/build.py       nodes wrapped in spans                                     (Task 3)
  src/bankagent/identity/lambda_handler.py   Mangum entrypoint, S3 users, secret key            (Task 4)
  scripts/seed_demo.py               uploads demo identities, checks tables and customers       (Task 12)
  tests/test_deploy_settings.py (2), test_observability.py (3), test_identity_lambda.py (4), test_seed_demo.py (12)
infra/
  pyproject.toml, uv.lock, cdk.json, app.py                                                     (Task 5)
  lb_infra/__init__.py, config.py, specs.py, nag.py, assembly.py                                (Task 5)
  lb_infra/stacks/__init__.py, data.py (5), identity.py (6), agent.py (7), realtime.py (8),
                  web.py (9), ops.py (10), github.py (12)
  bootstrap.sh                                                                                  (Task 12)
  scripts/__init__.py, stateful_guard.py, verify.py, amplify_release.sh                         (Task 13)
  tests/conftest.py, test_data.py (5), test_identity.py (6), test_agent.py (7), test_realtime.py (8),
        test_web.py (9), test_ops.py (10), test_iam.py, test_nag.py (11), test_github.py (12),
        test_guard.py, test_verify.py, test_workflows.py (13)
  realtime/                          (UI plan) handlers and tests kept; TS CDK app files deleted (Task 8)
web/
  lib/trace/xray.ts; lib/trace/viewModel.ts (+traceUrl); lib/server/records.ts (+trace_id)      (Task 9)
  components/trace/TraceTurn.tsx (+link); components/staff/BuildTag.tsx                         (Task 9)
  app/agent/layout.tsx, app/trace/layout.tsx, app/demo/layout.tsx; tests/unit/xray.test.ts      (Task 9)
amplify.yml                          + NEXT_PUBLIC_GIT_SHA                                       (Task 9)
.github/workflows/app-tests.yml, app-ci.yml, deploy.yml                                         (Task 13)
README.md                            Operations section                                          (Task 14)
```

---

## Phase A: verify the platform

### Task 1: Platform checks

**Scope limits:** read-only checks and a written record. Nothing here creates AWS resources.

**Check when done:** "Task 1 results" at the end of this file has a yes/no plus evidence for every step, and names which conditional notes in later tasks apply.

**Files:**
- Modify: `docs/superpowers/plans/2026-10-01-deployment.md` (append "Task 1 results")

**Interfaces:**
- Produces: facts that Tasks 3, 5, 7, 9, 12 and 13 read. Each later task names the step it depends on.

- [ ] **Step 1: CloudFormation schema for the AgentCore runtime**

Run:
```bash
aws cloudformation describe-type --region us-east-2 --type RESOURCE --type-name AWS::BedrockAgentCore::Runtime \
  --query Schema --output text | python3 -c "import json,sys; s=json.load(sys.stdin); print(sorted(s['properties'])); print(json.dumps(s['definitions'].get('CustomJWTAuthorizerConfiguration'), indent=1)); print(json.dumps(s['definitions'].get('RequestHeaderConfiguration'), indent=1))"
aws cloudformation describe-type --region us-east-2 --type RESOURCE --type-name AWS::BedrockAgentCore::RuntimeEndpoint --query Schema --output text | python3 -c "import json,sys; print(sorted(json.load(sys.stdin)['properties']))"
```
Expected:
- `properties` includes `AgentRuntimeArtifact`, `AgentRuntimeName`, `AuthorizerConfiguration`, `EnvironmentVariables`, `NetworkConfiguration`, `ProtocolConfiguration`, `RequestHeaderConfiguration` and `RoleArn`;
- the JWT definition has `DiscoveryUrl` and `AllowedAudience`;
- the endpoint has `AgentRuntimeId`, `AgentRuntimeVersion` and `Name`.

Record "CFN AgentCore Runtime with JWT authorizer: yes/no". **If no:** Task 7 uses its fallback note (`AwsCustomResource`).

- [ ] **Step 2: CDK Python L1 and L2 classes exist**

Run:
```bash
cd /tmp && rm -rf cdkpy && mkdir cdkpy && cd cdkpy && uv init -q --no-workspace && uv add -q "aws-cdk-lib>=2.220,<3" "constructs>=10.4,<11" "cdk-nag>=2.35"
uv run python - <<'PY'
import aws_cdk, aws_cdk.aws_bedrockagentcore as ac, aws_cdk.aws_appsync as ap, aws_cdk.aws_amplify as am
print("cdk", aws_cdk.__version__ if hasattr(aws_cdk, "__version__") else "?")
print("Runtime nested:", sorted(n for n in dir(ac.CfnRuntime) if n.endswith("Property")))
print("EventApi:", hasattr(ap, "EventApi"), "AppSyncAuthProvider:", hasattr(ap, "AppSyncAuthProvider"))
import inspect; print("CfnApp compute_role_arn:", "compute_role_arn" in inspect.signature(am.CfnApp.__init__).parameters)
PY
uv pip list 2>/dev/null | grep -i -E "aws-cdk-lib|cdk-nag"
```
Expected:
- `Runtime nested` lists at least `AgentRuntimeArtifactProperty`, `AuthorizerConfigurationProperty`, `ContainerConfigurationProperty`, `CustomJWTAuthorizerConfigurationProperty`, `NetworkConfigurationProperty` and `RequestHeaderConfigurationProperty`;
- `EventApi: True AppSyncAuthProvider: True`;
- `CfnApp compute_role_arn: True`.

Record the exact nested names and versions. **If `compute_role_arn` is False:** Task 9 uses its fallback note.

- [ ] **Step 3: Bedrock signing service used by the agent's client**

Run from `agent/`:
```bash
uv run python - <<'PY'
import inspect, re, anthropic
src = inspect.getsource(anthropic.AnthropicBedrockMantle) if hasattr(anthropic, "AnthropicBedrockMantle") else ""
mod = inspect.getsource(inspect.getmodule(anthropic.AnthropicBedrockMantle)) if src else ""
print(sorted(set(re.findall(r'service(?:_name)?\s*=\s*["\']([a-z0-9-]+)["\']', mod))))
print(sorted(set(re.findall(r'https://[a-z0-9.{}_-]*amazonaws\.com', mod))))
PY
```
Record the signing service name and host.
- **If the service is `bedrock`:** Task 7 keeps `BEDROCK_ACTIONS = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]`.
- **If it's something else (for example `bedrock-mantle`):** open the AWS *Service Authorization Reference* page for that service prefix, and record the action names that invoke inference and their resource ARN formats. Task 7 uses them instead.

- [ ] **Step 4: The serving bucket and its public-access block**

Run (the bucket name is in the pipeline's `.env` as `SERVING_BUCKET`):
```bash
B="$(grep '^SERVING_BUCKET=' ../.env 2>/dev/null | cut -d= -f2- || true)"; echo "bucket=$B"
aws s3api get-public-access-block --bucket "$B" --query PublicAccessBlockConfiguration
aws s3api get-bucket-policy --bucket "$B" 2>&1 | head -3
aws s3 ls "s3://$B/serving/latest.json"
```
Expected: all four public-access-block flags `true`; `NoSuchBucketPolicy` (no policy yet); `latest.json` listed.
- Record the bucket name. Task 5 puts it in `cdk.json`.
- **If a bucket policy already exists:** record its statements. Task 5's `CfnBucketPolicy` must include them, because a bucket has exactly one policy.
- **If the bucket doesn't exist:** create it now with pipeline plan Task 2 Step 3 (private, us-east-2) and re-run this step.

- [ ] **Step 5: The GitHub repository, its visibility and ARM64 runners**

Run:
```bash
gh repo view --json nameWithOwner,visibility,defaultBranchRef
```
Record `nameWithOwner` (it becomes `githubRepo` in `cdk.json`, and the OIDC trust subject) and the visibility.
- **If the repo is private:** check the organization or account billing settings for "Arm64 standard runners" on private repos. If they're not available, Task 13 uses its fallback note (QEMU `buildx` on `ubuntu-latest`).
- **If the repo will be renamed before submission:** rename it **before** Task 12. The OIDC subject is bound to the name.

- [ ] **Step 6: Account settings and quotas for the capacity table**

Run:
```bash
aws xray get-trace-segment-destination --region us-east-2
aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')]"
aws service-quotas list-service-quotas --region us-east-2 --service-code bedrock-agentcore --query "Quotas[].[QuotaName,Value]" --output table
aws service-quotas list-service-quotas --region us-east-2 --service-code bedrock --query "Quotas[?contains(QuotaName, 'Claude') && (contains(QuotaName, 'Haiku 4.5') || contains(QuotaName, 'Sonnet 5.5'))].[QuotaName,Value]" --output table
aws service-quotas list-service-quotas --region us-east-2 --service-code appsync --query "Quotas[?contains(QuotaName, 'Event')].[QuotaName,Value]" --output table
```
Record:
- the trace-segment destination (`CloudWatchLogs` means Transaction Search is already on);
- whether a GitHub OIDC provider already exists, and its ARN if so (Task 12 reuses it);
- every quota value. They go into the README capacity table in Task 14.

- [ ] **Step 7: Observability settings for AgentCore containers**

Read `.claude/skills/agents-optimize/` for the AgentCore observability instructions (open the skill's `SKILL.md`, then the referenced observability file):

```bash
ls .claude/skills/agents-optimize/
grep -rn -i -E "OTEL_|opentelemetry-instrument|AGENT_OBSERVABILITY_ENABLED|aws-opentelemetry-distro|log group|runtime-logs" .claude/skills/agents-optimize/ | head -40
```

Record:
- the environment variables the skill requires for a custom container on AgentCore Runtime. Task 7 sets them as `OTEL_ENV`; the default set is listed in Task 7.
- the runtime's application log group name pattern. Task 7 sets its retention; the default pattern is `/aws/bedrock-agentcore/runtimes/<runtimeId>-<endpointName>`.

- [ ] **Step 8: Record the results and commit**

Append to this file, under `## Task 1 results (YYYY-MM-DD)`, one line per step with its evidence (an output excerpt) and the conditional notes that apply.

```bash
git add docs/superpowers/plans/2026-10-01-deployment.md
git commit -m "docs: record deployment platform check results

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Phase B: agent changes (Python, `agent/`)

All commands in this phase run from `agent/`. These tasks change files created by the agent-core and UI plans, so read each file before editing it.

### Task 2: Deployed settings: Jev key from Secrets Manager, git SHA, sessions TTL, trace id on records

**Scope limits:** `settings.py`, `app.py` (only `runtime()` and the `turn_end` payload), `store/tables.py`, `store/repos.py`. No graph or observability code.

**Check when done:** `uv run pytest tests/test_deploy_settings.py tests/test_app_ui.py -v` passes, and `uv run pytest -q` passes.

**Files:**
- Modify: `agent/src/bankagent/settings.py`, `agent/src/bankagent/app.py`, `agent/src/bankagent/store/tables.py`, `agent/src/bankagent/store/repos.py`, `agent/tests/test_app_ui.py`
- Test: `agent/tests/test_deploy_settings.py`

**Interfaces:**
- Consumes: `Settings`, `Settings.from_env` (agent-core Task 1); `TABLE_SPECS`, `create_tables`, `Store`, `SessionRepo`, `DecisionLog` (agent-core Task 6, UI Task 2); `handle` (UI Task 4).
- Produces:
  - `Settings.git_sha: str` (default `"dev"`, from `GIT_SHA`);
  - `load_settings(env: Mapping[str, str] = os.environ, secrets_client=None) -> Settings`;
  - `DecisionLog.append(..., latency_ms=None, trace_id: str | None = None)`, which stores a top-level `trace_id` only when given;
  - `SessionRepo.TTL_DAYS = 90`, with `ensure()` writing `ttl`;
  - the `turn_end` payload `{duration_ms, awaiting, language}`.

- [ ] **Step 1: Write the failing tests**

`agent/tests/test_deploy_settings.py`:
```python
import logging
import time

import boto3
import pytest
from moto import mock_aws

from bankagent.settings import load_settings
from bankagent.store.repos import Store
from bankagent.store.tables import TABLE_SPECS, create_tables

BASE = {"SERVING_URI": "s3://bucket/serving"}


class Boom:
    def get_secret_value(self, **_):
        raise AssertionError("Secrets Manager must not be called")


@pytest.fixture
def sm():
    with mock_aws():
        yield boto3.client("secretsmanager", region_name="us-east-2")


def test_jev_key_read_from_secret_and_stripped(sm):
    sm.create_secret(Name="lb-demo/jev", SecretString="tsk-123\n")
    assert load_settings({**BASE, "JEV_SECRET_ID": "lb-demo/jev"}, sm).jev_api_key == "tsk-123"


def test_explicit_env_key_wins_over_secret():
    s = load_settings({**BASE, "JEV_API_KEY": "from-env", "JEV_SECRET_ID": "lb-demo/jev"}, Boom())
    assert s.jev_api_key == "from-env"


def test_no_secret_id_means_no_secrets_call():
    assert load_settings(BASE, Boom()).jev_api_key == ""


def test_missing_secret_leaves_key_empty_and_does_not_raise(sm, caplog):
    caplog.set_level(logging.ERROR)
    s = load_settings({**BASE, "JEV_SECRET_ID": "lb-demo/missing"}, sm)
    assert s.jev_api_key == ""
    assert "Jev secret" in caplog.text and "lb-demo/missing" in caplog.text


def test_git_sha_from_env_with_default():
    assert load_settings({**BASE, "GIT_SHA": "abc1234"}).git_sha == "abc1234"
    assert load_settings(BASE).git_sha == "dev"


@pytest.fixture
def store():
    with mock_aws():
        create_tables(boto3.client("dynamodb", region_name="us-east-2"), "t")
        yield Store.connect("t", "us-east-2")


def test_sessions_expire_after_90_days(store):
    assert TABLE_SPECS["sessions"]["ttl"] == "ttl"
    item = store.sessions.ensure("S-1", "CLI-A", "es")
    assert time.time() + 89 * 86400 < item["ttl"] <= time.time() + 90 * 86400 + 5


def test_decision_record_keeps_trace_id_only_when_given(store):
    store.log.append("S-1", "T1", "understand", "route", {"next": "reply"}, trace_id="1-6720f2a0-0123456789abcdef01234567")
    store.log.append("S-1", "T1", "reply", "llm", {"role": "compose"})
    first, second = store.log.list("S-1")
    assert first["trace_id"] == "1-6720f2a0-0123456789abcdef01234567"
    assert "trace_id" not in second
```

Append to `agent/tests/test_app_ui.py`:
```python
def test_turn_end_carries_the_reply_language():
    r = rt()
    entry.handle({"message": "saldo"}, auth("msg-00000042"), r)
    end = r.service.deps.store.log.records[-1]
    assert end["kind"] == "turn_end" and end["payload"]["language"] in ("es", "pt")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_deploy_settings.py tests/test_app_ui.py::test_turn_end_carries_the_reply_language -v`
Expected: FAIL (`ImportError: cannot import name 'load_settings'`, and a `KeyError: 'language'`).

- [ ] **Step 3: Settings**

In `agent/src/bankagent/settings.py`:
- Make sure the imports include:
```python
import logging
import os
from collections.abc import Mapping

import boto3
```
- Add `log = logging.getLogger(__name__)` after the imports.
- Add the last field of the `Settings` dataclass (after `jwks_url`):
```python
    git_sha: str = "dev"
```
- In `Settings.from_env`, add the argument after `jwks_url=…`:
```python
            git_sha=env.get("GIT_SHA", "dev"),
```
- Append to the end of the file:
```python
def load_settings(env: Mapping[str, str] = os.environ, secrets_client=None) -> Settings:
    """Settings for the deployed runtime (deployment spec §4.3). When JEV_SECRET_ID is set and JEV_API_KEY isn't,
    the key is read from Secrets Manager once. A failure leaves it empty: every Jev call then fails and the graph
    clarifies or hands off (agent-core §4.4). The container still starts, so /ping stays healthy."""
    merged = dict(env)
    secret_id = merged.get("JEV_SECRET_ID")
    if secret_id and not merged.get("JEV_API_KEY"):
        try:
            client = secrets_client or boto3.client("secretsmanager",
                                                    region_name=merged.get("AWS_REGION", "us-east-2"))
            merged["JEV_API_KEY"] = client.get_secret_value(SecretId=secret_id)["SecretString"].strip()
        except Exception:
            log.exception("could not read the Jev secret %s; Jev calls will fail", secret_id)
    return Settings.from_env(merged)
```

- [ ] **Step 4: Entrypoint**

In `agent/src/bankagent/app.py`:
- Replace `from bankagent.settings import Settings` with `from bankagent.settings import load_settings`.
- In `runtime()`, replace `_runtime = build_runtime(Settings.from_env())` with:
```python
        _runtime = build_runtime(load_settings())
```
- In `handle`, replace the `turn_end` append:
```python
    store.log.append(sid, turn_id, "turn", "turn_end",
                     {"duration_ms": int((time.monotonic() - start) * 1000), "awaiting": reply.get("awaiting", "none")})
```
with:
```python
    store.log.append(sid, turn_id, "turn", "turn_end",
                     {"duration_ms": int((time.monotonic() - start) * 1000), "awaiting": reply.get("awaiting", "none"),
                      "language": reply.get("language", ctx.lang)})
```
Then run `grep -n "Settings" src/bankagent/app.py`. Expected: no remaining use of `Settings`. If one remains, import `Settings` again alongside `load_settings`.

- [ ] **Step 5: Tables and repositories**

In `agent/src/bankagent/store/tables.py`, replace:
```python
    "sessions": {"keys": [("session_id", "S", "HASH")], "gsis": [], "ttl": None},
```
with:
```python
    "sessions": {"keys": [("session_id", "S", "HASH")], "gsis": [], "ttl": "ttl"},  # 90 days (deployment §4.5)
```

In `agent/src/bankagent/store/repos.py`, in `class SessionRepo`, add the class attribute `TTL_DAYS = 90` under the docstring, and replace the `item = {...}` line in `ensure` with:
```python
        now = self.clock()
        item = {"session_id": session_id, "customer_id": customer_id, "language": lang, "control": "agent",
                "created_at": _iso(now), "ttl": int(now) + self.TTL_DAYS * 86400}
```

In `class DecisionLog`, replace the whole `append` method with:
```python
    def append(self, session_id: str, turn_id: str, node: str, kind: str, payload: dict,
               versions: dict | None = None, latency_ms: int | None = None, trace_id: str | None = None) -> None:
        key = (session_id, turn_id)
        seq = self._seq.get(key, 0) + 1
        self._seq[key] = seq
        now = self.clock()
        item = {"session_id": session_id, "sk": f"{turn_id}#{seq:04d}", "turn_id": turn_id, "seq": seq, "node": node,
                "kind": kind, "ts": datetime.fromtimestamp(now, timezone.utc).isoformat(), "payload": payload,
                "versions": versions or {}, "latency_ms": latency_ms, "ttl": int(now) + self.TTL_DAYS * 86400}
        if trace_id:
            item["trace_id"] = trace_id  # links the audit record to its CloudWatch/X-Ray trace (deployment §6.1)
        self.t.put_item(Item=to_dynamo(item))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_deploy_settings.py tests/test_app_ui.py -v`
Expected: all pass.
Run: `uv run pytest -q`
Expected: the whole offline suite passes.

- [ ] **Step 7: Rename the local Jev variable**

In the repo-root `.env` (gitignored, never staged), rename `TYPESAFE_API_KEY=` to `JEV_API_KEY=`, keeping the value. Then:
Run: `grep -c '^JEV_API_KEY=' ../.env; grep -c '^TYPESAFE_API_KEY=' ../.env`
Expected: `1` then `0`. Don't print the value.

- [ ] **Step 8: Commit**

```bash
cd .. && git add agent/src/bankagent/settings.py agent/src/bankagent/app.py agent/src/bankagent/store/tables.py agent/src/bankagent/store/repos.py agent/tests/test_deploy_settings.py agent/tests/test_app_ui.py
git commit -m "feat(agent): secret-backed Jev key, git SHA, sessions TTL and trace id on decision records

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Observability: stamped records, EMF metrics, node spans and the ADOT image

**Scope limits:** a new `observability.py`, the wiring in `runtime.py` and `graph/build.py`, plus `pyproject.toml` and `Dockerfile`. No change to node logic.

**Check when done:** `uv run pytest tests/test_observability.py -v` passes, and `uv run pytest -q` passes.

**Files:**
- Create: `agent/src/bankagent/observability.py`
- Modify: `agent/src/bankagent/runtime.py`, `agent/src/bankagent/graph/build.py`, `agent/pyproject.toml`, `agent/Dockerfile`
- Test: `agent/tests/test_observability.py`

**Interfaces:**
- Consumes: `DecisionLog.append(..., trace_id=…)` and `Settings.git_sha` (Task 2); `build_graph`, `NODES`, `TRACER` (agent-core Task 10); `build_runtime` (agent-core Task 11, resolver Task 12).
- Produces:
  - `NAMESPACE = "LatamBank"`;
  - `current_trace_id() -> str | None`: X-Ray format `1-<8 hex>-<24 hex>`, or `None` when there's no valid span;
  - `emf(values: dict[str, float | list[float]], units: dict[str, str], dims: dict[str, str], dim_sets: list[list[str]], write=print) -> None`;
  - `classify_route(turn: TurnFacts) -> str`, returning one of `act | clarify | abstain | handoff | safe_fallback`;
  - `ObservedLog(inner, git_sha: str, write=print)`: same `append`/`list` as `DecisionLog`, other attributes delegated;
  - `traced_node(name: str, fn) -> fn`: a wrapper with the signature `(state, config)`.

- [ ] **Step 1: Write the failing tests**

`agent/tests/test_observability.py`:
```python
import json

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from bankagent.observability import NAMESPACE, ObservedLog, TurnFacts, classify_route, current_trace_id, emf, traced_node


class InnerLog:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def append(self, session_id, turn_id, node, kind, payload, versions=None, latency_ms=None, **kw):
        if self.fail:
            raise RuntimeError("ddb down")
        self.calls.append({"node": node, "kind": kind, "payload": payload, "versions": versions,
                           "latency_ms": latency_ms, **kw})

    def list(self, session_id):
        return ["listed", session_id]

    seq_marker = "delegated"


def docs(lines):
    return [json.loads(x) for x in lines]


def run_turn(log, records, language="es"):
    for node, kind, payload, latency in records:
        log.append("S-1", "T1", node, kind, payload, {"model": "m"}, latency)
    log.append("S-1", "T1", "turn", "turn_end", {"duration_ms": 2400, "awaiting": "none", "language": language})


def metric(lines, name, **dims):
    for d in docs(lines):
        meta = d["_aws"]["CloudWatchMetrics"][0]
        if any(m["Name"] == name for m in meta["Metrics"]) and all(d.get(k) == v for k, v in dims.items()):
            return d[name], meta
    return None, None


def test_emf_document_shape():
    out = []
    emf({"TurnCount": 1}, {"TurnCount": "Count"}, {"Language": "es", "Route": "act"}, [["Language", "Route"], ["Route"]],
        out.append)
    d = json.loads(out[0])
    meta = d["_aws"]["CloudWatchMetrics"][0]
    assert meta["Namespace"] == NAMESPACE == "LatamBank"
    assert meta["Dimensions"] == [["Language", "Route"], ["Route"]]
    assert meta["Metrics"] == [{"Name": "TurnCount", "Unit": "Count"}]
    assert d["TurnCount"] == 1 and d["Language"] == "es" and d["Route"] == "act" and isinstance(d["_aws"]["Timestamp"], int)


@pytest.mark.parametrize("facts,expected", [
    (TurnFacts(next="answer_inquiry"), "act"),
    (TurnFacts(next="handoff"), "handoff"),
    (TurnFacts(next="resolve_transaction", handoff_priority="critical"), "handoff"),
    (TurnFacts(next="reply", goal_kind="abstain", template=True), "abstain"),
    (TurnFacts(next="reply", goal_kind="refuse_injection"), "abstain"),
    (TurnFacts(next="clarify", error=True), "safe_fallback"),
    (TurnFacts(next="reply", template=True), "safe_fallback"),
    (TurnFacts(next="clarify"), "clarify"),
    (TurnFacts(next=None), "act"),
])
def test_classify_route(facts, expected):
    assert classify_route(facts) == expected


def test_stamps_git_sha_and_keeps_versions():
    inner = InnerLog()
    ObservedLog(inner, "abc1234", write=lambda _: None).append("S-1", "T1", "understand", "jev", {"answers": {}},
                                                               {"model": "jev-1.13.0"}, 120)
    assert inner.calls[0]["versions"] == {"model": "jev-1.13.0", "git_sha": "abc1234"}
    assert "trace_id" not in inner.calls[0]  # no active span → no kwarg (fakes without trace_id keep working)


def test_turn_metrics_on_turn_end():
    out, inner = [], InnerLog()
    run_turn(ObservedLog(inner, "sha", write=out.append), [
        ("understand", "llm", {"role": "extract"}, 300),
        ("understand", "jev", {"answers": {}}, 900),
        ("understand", "route", {"next": "handoff", "reasons": ["reports_unauthorized_use"], "goal": {"kind": "handoff"}}, None),
        ("handoff", "tool", {"source": "handoffs", "handoff_id": "HND-1", "priority": "critical"}, None),
        ("reply", "llm", {"role": "compose"}, 1100),
    ], language="pt")
    assert metric(out, "TurnCount", Route="handoff", Language="pt")[0] == 1
    v, meta = metric(out, "TurnLatencyMs", Language="pt")
    assert v == 2400 and ["Language"] in meta["Dimensions"] and [] in meta["Dimensions"]
    assert metric(out, "JevLatencyMs", Language="pt")[0] == [900]
    assert metric(out, "HandoffCount", Priority="critical")[0] == 1
    assert metric(out, "LlmLatencyMs", Role="extract")[0] == [300]
    assert metric(out, "LlmLatencyMs", Role="compose")[0] == [1100]
    assert metric(out, "JevErrorCount", Language="pt")[0] == 0


def test_error_counts_and_injection():
    out = []
    run_turn(ObservedLog(InnerLog(), "sha", write=out.append), [
        ("understand", "error", {"role": "jev", "error": "timeout"}, None),
        ("understand", "error", {"role": "extract", "error": "5xx"}, None),
        ("understand", "route", {"next": "reply", "reasons": ["injection_attempt"], "goal": {"kind": "refuse_injection"}}, None),
        ("reply", "template", {"goal": "refuse_injection"}, None),
    ])
    assert metric(out, "JevErrorCount", Language="es")[0] == 1
    assert metric(out, "LlmErrorCount", Role="extract")[0] == 1
    assert metric(out, "InjectionBlockedCount", Language="es")[0] == 1
    assert metric(out, "TemplateFallbackCount", Language="es")[0] == 1
    assert metric(out, "TurnCount", Route="abstain")[0] == 1


def test_observer_never_raises_on_odd_records():
    out = []
    log = ObservedLog(InnerLog(), "sha", write=out.append)
    log.append("S-1", "T9", "understand", "jev", "not-a-dict", None, None)
    log.append("S-1", "T9", "turn", "turn_end", None)  # no route seen, payload missing
    log.append("S-2", "T1", "turn", "turn_end", {"duration_ms": "fast"})
    broken = ObservedLog(InnerLog(), "sha", write=lambda _: (_ for _ in ()).throw(OSError("stdout closed")))
    broken.append("S-3", "T1", "turn", "turn_end", {"duration_ms": 5, "language": "es"})
    assert metric(out, "TurnCount", Route="act", Language="unknown")[0] == 1


def test_inner_failure_still_propagates_but_metrics_were_recorded():
    out = []
    log = ObservedLog(InnerLog(fail=True), "sha", write=out.append)
    with pytest.raises(RuntimeError):
        log.append("S-1", "T1", "turn", "turn_end", {"duration_ms": 10, "language": "es"})
    assert metric(out, "TurnCount", Route="act")[0] == 1


def test_list_and_attributes_are_delegated():
    log = ObservedLog(InnerLog(), "sha", write=lambda _: None)
    assert log.list("S-1") == ["listed", "S-1"] and log.seq_marker == "delegated"


def test_trace_id_in_xray_format_inside_a_span():
    provider = TracerProvider()
    tracer = provider.get_tracer("t")
    assert current_trace_id() is None
    with tracer.start_as_current_span("x") as span:
        tid = current_trace_id()
        raw = f"{span.get_span_context().trace_id:032x}"
    assert tid == f"1-{raw[:8]}-{raw[8:]}"


def test_traced_node_keeps_signature_and_result():
    def node(state, config):
        return {"seen": (state["turn_id"], config["configurable"]["ctx"])}

    wrapped = traced_node("understand", node)
    ctx = type("Ctx", (), {"session_id": "S-1"})()
    assert wrapped({"turn_id": "T1"}, {"configurable": {"ctx": ctx}}) == {"seen": ("T1", ctx)}
    import inspect
    assert list(inspect.signature(wrapped).parameters) == ["state", "config"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv add --dev "opentelemetry-sdk>=1.27" && uv run pytest tests/test_observability.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'bankagent.observability'`).

- [ ] **Step 3: Write `observability.py`**

`agent/src/bankagent/observability.py`:
```python
"""Deployment spec §6: decision records also feed tracing and CloudWatch metrics.

ObservedLog wraps DecisionLog. For every record it:
- stamps versions.git_sha and the current X-Ray trace id;
- adds a span event;
- collects per-turn facts.
On `turn_end` it writes CloudWatch EMF log lines (stdout → the runtime's log group → metrics, no API calls).
Observability is best-effort: nothing here may raise into a customer's turn."""
import inspect
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps

from opentelemetry import trace

NAMESPACE = "LatamBank"
MAX_OPEN_TURNS = 500  # turns without a turn_end (crashes) are dropped oldest-first
ROLES = ("extract", "compose")
log = logging.getLogger(__name__)
TRACER = trace.get_tracer("bankagent")


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    raw = f"{ctx.trace_id:032x}"
    return f"1-{raw[:8]}-{raw[8:]}"  # ADOT uses X-Ray-compatible ids: 8 hex of epoch seconds + 24 random


def emf(values: dict, units: dict, dims: dict, dim_sets: list[list[str]], write=print) -> None:
    doc = {"_aws": {"Timestamp": int(time.time() * 1000),
                    "CloudWatchMetrics": [{"Namespace": NAMESPACE, "Dimensions": dim_sets,
                                           "Metrics": [{"Name": n, "Unit": units[n]} for n in values]}]},
           **dims, **values}
    write(json.dumps(doc))


@dataclass
class TurnFacts:
    next: str | None = None
    goal_kind: str | None = None
    reasons: tuple = ()
    handoff_priority: str | None = None
    error: bool = False
    template: bool = False
    jev_ms: list = field(default_factory=list)
    jev_errors: int = 0
    llm_ms: dict = field(default_factory=lambda: {r: [] for r in ROLES})
    llm_errors: dict = field(default_factory=lambda: {r: 0 for r in ROLES})
    templates: int = 0


def classify_route(t: TurnFacts) -> str:
    if t.handoff_priority is not None or t.next == "handoff":
        return "handoff"
    if t.goal_kind in ("abstain", "refuse_injection"):
        return "abstain"
    if t.error or t.template:
        return "safe_fallback"
    if t.next == "clarify":
        return "clarify"
    return "act"


class ObservedLog:
    def __init__(self, inner, git_sha: str, write=print):
        self.inner, self.git_sha, self.write = inner, git_sha, write
        self._turns: OrderedDict[tuple[str, str], TurnFacts] = OrderedDict()

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def list(self, session_id: str):
        return self.inner.list(session_id)

    def append(self, session_id, turn_id, node, kind, payload, versions=None, latency_ms=None) -> None:
        trace_id = None
        try:
            trace_id = current_trace_id()
            trace.get_current_span().add_event("decision_record", {"session_id": str(session_id),
                                                                   "turn_id": str(turn_id), "node": str(node),
                                                                   "kind": str(kind)})
            self._observe(session_id, turn_id, node, kind, payload, latency_ms)
        except Exception:
            log.exception("observability failed for %s/%s", node, kind)
        extra = {"trace_id": trace_id} if trace_id else {}
        self.inner.append(session_id, turn_id, node, kind, payload, {**(versions or {}), "git_sha": self.git_sha},
                          latency_ms, **extra)

    def _observe(self, session_id, turn_id, node, kind, payload, latency_ms) -> None:
        p = payload if isinstance(payload, dict) else {}
        key = (session_id, turn_id)
        t = self._turns.get(key) or TurnFacts()
        self._turns[key] = t
        while len(self._turns) > MAX_OPEN_TURNS:
            self._turns.popitem(last=False)
        role = p.get("role")
        if kind == "jev" and isinstance(latency_ms, (int, float)):
            t.jev_ms.append(latency_ms)
        elif kind == "llm" and role in ROLES and isinstance(latency_ms, (int, float)):
            t.llm_ms[role].append(latency_ms)
        elif kind == "error":
            t.error = True
            if role == "jev":
                t.jev_errors += 1
            elif role in ROLES:
                t.llm_errors[role] += 1
        elif kind == "template":
            t.template, t.templates = True, t.templates + 1
        elif kind == "route":
            t.next = p.get("next")
            t.reasons = tuple(p.get("reasons") or ())
            t.goal_kind = (p.get("goal") or {}).get("kind") if isinstance(p.get("goal"), dict) else None
        elif kind == "tool" and node == "handoff":
            t.handoff_priority = str(p.get("priority") or "unknown")
        if kind == "turn_end":
            del self._turns[key]
            self._flush(t, p)

    def _flush(self, t: TurnFacts, end: dict) -> None:
        lang = end.get("language") if end.get("language") in ("es", "pt") else "unknown"
        duration = end.get("duration_ms")
        injected = int(any(r.startswith("injection") for r in t.reasons))
        base = {"TurnCount": 1, "JevErrorCount": t.jev_errors, "TemplateFallbackCount": t.templates,
                "InjectionBlockedCount": injected}
        units = {"TurnCount": "Count", "JevErrorCount": "Count", "TemplateFallbackCount": "Count",
                 "InjectionBlockedCount": "Count", "TurnLatencyMs": "Milliseconds", "JevLatencyMs": "Milliseconds"}
        if isinstance(duration, (int, float)):
            base["TurnLatencyMs"] = duration
        if t.jev_ms:
            base["JevLatencyMs"] = t.jev_ms
        self._emit(base, units, {"Language": lang}, [["Language"], []])
        self._emit({"TurnCount": 1}, units, {"Language": lang, "Route": classify_route(t)},
                   [["Language", "Route"], ["Route"]])
        if t.handoff_priority is not None:
            self._emit({"HandoffCount": 1}, {"HandoffCount": "Count"},
                       {"Language": lang, "Priority": t.handoff_priority}, [["Language", "Priority"], ["Priority"]])
        for role in ROLES:
            values = {"LlmErrorCount": t.llm_errors[role]}
            if t.llm_ms[role]:
                values["LlmLatencyMs"] = t.llm_ms[role]
            self._emit(values, {"LlmErrorCount": "Count", "LlmLatencyMs": "Milliseconds"},
                       {"Language": lang, "Role": role}, [["Language", "Role"], ["Role"], []])

    def _emit(self, values, units, dims, dim_sets) -> None:
        try:
            emf(values, units, dims, dim_sets, self.write)
        except Exception:
            log.exception("EMF write failed")


def traced_node(name: str, fn):
    """One span per graph node (deployment spec §6.1). LangGraph passes `config` by parameter name, so the wrapper
    keeps the exact (state, config) signature. Interrupts are control flow, not errors."""
    @wraps(fn)
    def wrapper(state, config):
        ctx = (config or {}).get("configurable", {}).get("ctx")
        attrs = {"node": name, "turn_id": str((state or {}).get("turn_id", "")),
                 "session_id": str(getattr(ctx, "session_id", ""))}
        with TRACER.start_as_current_span(f"node.{name}", attributes=attrs, record_exception=False,
                                          set_status_on_exception=False):
            return fn(state, config)

    wrapper.__signature__ = inspect.signature(lambda state, config: None)
    return wrapper
```

- [ ] **Step 4: Wire it in**

In `agent/src/bankagent/graph/build.py`:
- Add the import `from bankagent.observability import traced_node`.
- Replace `g.add_node(name, getattr(nodes, name))` with:
```python
        g.add_node(name, traced_node(name, getattr(nodes, name)))
```

In `agent/src/bankagent/runtime.py`:
- Add the import `from bankagent.observability import ObservedLog`.
- In `build_runtime`, right after the line `store = Store.connect(...)`, add:
```python
    store.log = ObservedLog(store.log, settings.git_sha)  # git SHA + trace id on every record, EMF metrics (§6)
```
If `Store` is a frozen dataclass (assignment raises `FrozenInstanceError`), use `store = dataclasses.replace(store, log=ObservedLog(store.log, settings.git_sha))` instead, with `import dataclasses`.

- [ ] **Step 5: Image and dependencies**

Run: `uv add "aws-opentelemetry-distro>=0.10"`
Expected: `pyproject.toml` and `uv.lock` updated.

In `agent/Dockerfile`, replace the last line:
```dockerfile
CMD ["uv", "run", "--no-dev", "python", "-m", "bankagent.app"]
```
with:
```dockerfile
# ADOT auto-instrumentation → AgentCore Observability (deployment spec §6.1). OTEL_* settings come from the runtime env.
CMD ["uv", "run", "--no-dev", "opentelemetry-instrument", "python", "-m", "bankagent.app"]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_observability.py -v`
Expected: all pass.
Run: `uv run pytest -q`
Expected: the whole offline suite passes. Graph tests still pass because `traced_node` keeps each node's behaviour and signature.
Run: `docker build --platform linux/arm64 -t bankagent:obs . && docker run --rm --entrypoint uv bankagent:obs run --no-dev opentelemetry-instrument --version`
Expected: a version line (the CLI exists in the image).

- [ ] **Step 7: Commit**

```bash
cd .. && git add agent/src/bankagent/observability.py agent/src/bankagent/runtime.py agent/src/bankagent/graph/build.py agent/pyproject.toml agent/uv.lock agent/Dockerfile agent/tests/test_observability.py
git commit -m "feat(agent): EMF metrics, node spans and trace-linked decision records

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The identity service as a Lambda

**Scope limits:** a Lambda entrypoint around the existing FastAPI app, and its image. No change to the IdP's routes or tokens.

**Check when done:** `uv run pytest tests/test_identity_lambda.py -v` passes, and the identity image builds for ARM64.

**Files:**
- Create: `agent/src/bankagent/identity/lambda_handler.py`, `agent/Dockerfile.identity`
- Modify: `agent/pyproject.toml` (+ `mangum`), `agent/.dockerignore` (unchanged content; verify `config` stays excluded)
- Test: `agent/tests/test_identity_lambda.py`

**Interfaces:**
- Consumes:
  - `create_app(users, private_pem, public_pem, kid, issuer, audience, ..., demo_mode=False)` (agent-core Task 3, UI Task 3);
  - `load_users(path)`, `generate_keypair()`.
- Produces:
  - `build(env, s3, secrets) -> Mangum`;
  - `handler(event, context) -> dict` (Lambda entrypoint `bankagent.identity.lambda_handler.handler`).
  - Environment variables: `IDP_ISSUER`, `IDP_AUDIENCE`, `IDP_KID`, `IDP_SIGNING_SECRET_ID`, `DEMO_USERS_S3_URI`, `IDP_DEMO_MODE`.

- [ ] **Step 1: Write the failing tests**

`agent/tests/test_identity_lambda.py`:
```python
import json

import boto3
import pytest
from moto import mock_aws

import bankagent.identity.lambda_handler as lh
from bankagent.auth.tokens import generate_keypair

USERS_YAML = """# LABELED TEST identities (fixture)
users:
  - username: demo01
    password_hash: x
    otp: "123456"
    customer_id: CLI-FIXA00000001
    lang: es
"""
ENV = {"IDP_ISSUER": "https://abc.execute-api.us-east-2.amazonaws.com", "IDP_AUDIENCE": "bankagent",
       "IDP_KID": "lb-demo-1", "IDP_SIGNING_SECRET_ID": "lb-demo/idp-signing-key",
       "DEMO_USERS_S3_URI": "s3://serving-bucket/identity/demo_users.yaml", "IDP_DEMO_MODE": "1"}


def http_event(path, method="GET"):
    return {"version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "",
            "headers": {"host": "abc.execute-api.us-east-2.amazonaws.com"},
            "requestContext": {"http": {"method": method, "path": path, "protocol": "HTTP/1.1", "sourceIp": "1.2.3.4",
                                        "userAgent": "pytest"}, "stage": "$default", "requestId": "r1",
                               "domainName": "abc.execute-api.us-east-2.amazonaws.com", "apiId": "abc"},
            "isBase64Encoded": False}


@pytest.fixture
def aws(monkeypatch):
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-2")
        s3.create_bucket(Bucket="serving-bucket", CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
        sm = boto3.client("secretsmanager", region_name="us-east-2")
        sm.create_secret(Name="lb-demo/idp-signing-key", SecretString=generate_keypair()[0])
        for k, v in ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setattr(lh, "_handler", None)
        yield s3


def test_discovery_and_jwks_served_from_secret_key(aws):
    aws.put_object(Bucket="serving-bucket", Key="identity/demo_users.yaml", Body=USERS_YAML.encode())
    r = lh.handler(http_event("/.well-known/openid-configuration"), None)
    assert r["statusCode"] == 200 and json.loads(r["body"])["issuer"] == ENV["IDP_ISSUER"]
    keys = json.loads(lh.handler(http_event("/jwks.json"), None)["body"])["keys"]
    assert len(keys) == 1 and keys[0]["kid"] == "lb-demo-1"


def test_cold_start_failure_returns_503_and_retries(aws):
    r = lh.handler(http_event("/.well-known/openid-configuration"), None)  # users object not uploaded yet
    assert r["statusCode"] == 503 and json.loads(r["body"]) == {"error": "identity_unavailable"}
    assert lh._handler is None  # the failure is not cached
    aws.put_object(Bucket="serving-bucket", Key="identity/demo_users.yaml", Body=USERS_YAML.encode())
    assert lh.handler(http_event("/.well-known/openid-configuration"), None)["statusCode"] == 200


def test_bad_s3_uri_is_a_cold_start_failure(aws, monkeypatch):
    monkeypatch.setenv("DEMO_USERS_S3_URI", "https://not-s3/demo_users.yaml")
    assert lh.handler(http_event("/jwks.json"), None)["statusCode"] == 503
```

If agent-core Task 3's `load_users` expects different YAML keys than `USERS_YAML`, copy the format from `agent/tests/test_identity.py`'s fixture into `USERS_YAML` (keep the labeled header line).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv add "mangum>=0.19" && uv run pytest tests/test_identity_lambda.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'bankagent.identity.lambda_handler'`).

- [ ] **Step 3: Write the entrypoint**

`agent/src/bankagent/identity/lambda_handler.py`:
```python
"""AWS Lambda entrypoint for the mock IdP (deployment spec §3, Identity stack).
On cold start it reads the RS256 key from Secrets Manager and the labeled test identities from S3. The identities
file names dataset customer ids, so it is gitignored and never baked into an image. Then it serves the FastAPI
app through Mangum. A failed cold start answers 503 and is retried on the next request."""
import logging
import os
import tempfile
from pathlib import Path

import boto3
from cryptography.hazmat.primitives import serialization
from mangum import Mangum

from bankagent.identity.app import create_app
from bankagent.identity.users import load_users

log = logging.getLogger(__name__)
_handler = None
UNAVAILABLE = {"statusCode": 503, "headers": {"content-type": "application/json"},
               "body": '{"error": "identity_unavailable"}'}


def _split_s3(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://") or "/" not in uri[5:]:
        raise ValueError(f"not an s3:// object URI: {uri!r}")
    bucket, key = uri[5:].split("/", 1)
    return bucket, key


def build(env=os.environ, s3=None, secrets=None) -> Mangum:
    region = env.get("AWS_REGION", "us-east-2")
    s3 = s3 or boto3.client("s3", region_name=region)
    secrets = secrets or boto3.client("secretsmanager", region_name=region)
    private_pem = secrets.get_secret_value(SecretId=env["IDP_SIGNING_SECRET_ID"])["SecretString"]
    public_pem = serialization.load_pem_private_key(private_pem.encode(), None).public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    bucket, key = _split_s3(env["DEMO_USERS_S3_URI"])
    path = Path(tempfile.gettempdir()) / "demo_users.yaml"
    path.write_bytes(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    app = create_app(load_users(str(path)), private_pem, public_pem, env.get("IDP_KID", "idp-1"), env["IDP_ISSUER"],
                     env.get("IDP_AUDIENCE", "bankagent"), demo_mode=env.get("IDP_DEMO_MODE") == "1")
    return Mangum(app, lifespan="off")


def handler(event, context):
    global _handler
    if _handler is None:
        try:
            _handler = build()
        except Exception:
            log.exception("identity cold start failed")
            return UNAVAILABLE
    return _handler(event, context)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_identity_lambda.py -v`
Expected: 3 passed.

- [ ] **Step 5: Write the image**

`agent/Dockerfile.identity`:
```dockerfile
# Lambda container image for the mock IdP (deployment spec §3). Only the IdP's dependencies are installed,
# pinned by uv.lock; the agent's heavy dependencies (LangGraph, DuckDB, Anthropic) are left out.
FROM public.ecr.aws/lambda/python:3.12-arm64
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
COPY pyproject.toml uv.lock /build/
RUN cd /build && uv export --frozen --no-dev --no-emit-project --no-hashes -o /build/pins.txt \
 && uv pip install --system --target "${LAMBDA_TASK_ROOT}" -c /build/pins.txt \
      fastapi "pyjwt[crypto]" pyyaml mangum httpx pydantic
COPY src/bankagent ${LAMBDA_TASK_ROOT}/bankagent
CMD ["bankagent.identity.lambda_handler.handler"]
```

Run: `docker build --platform linux/arm64 -f Dockerfile.identity -t bankagent-idp:test . && docker run --rm --entrypoint python bankagent-idp:test -c "import bankagent.identity.lambda_handler as h; print('ok', h.UNAVAILABLE['statusCode'])"`
Expected: `ok 503`.
- **If the import fails on a missing module** (an import the IdP needs that isn't in the list): add that package to the `uv pip install` line and rebuild. Never add `langgraph`, `duckdb` or `anthropic`.

Run: `grep -n '^config$' .dockerignore`
Expected: one match. Demo identities are never copied into an image.

- [ ] **Step 6: Commit**

```bash
cd .. && git add agent/src/bankagent/identity/lambda_handler.py agent/Dockerfile.identity agent/pyproject.toml agent/uv.lock agent/tests/test_identity_lambda.py
git commit -m "feat(identity): Lambda entrypoint with key from Secrets Manager and identities from S3

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Phase C: the CDK app (`infra/`)

All commands in this phase run from `infra/` unless stated. Run `cd realtime && npm ci && cd ..` once before the first synth or test: `NodejsFunction` bundles the realtime handlers with that package's esbuild.

### Task 5: CDK scaffold, configuration, cdk-nag and the `LbDemo-Data` stack

**Scope limits:** the uv project, `app.py`, the shared configuration, the table-spec loader, the nag helper, and the Data stack. No other stack.

**Check when done:** `uv run pytest tests/test_data.py -v` passes, and `npx aws-cdk@2 synth -q` succeeds.

**Files:**
- Create: `infra/pyproject.toml`, `infra/cdk.json`, `infra/app.py`, `infra/lb_infra/__init__.py` (empty), `infra/lb_infra/config.py`, `infra/lb_infra/specs.py`, `infra/lb_infra/nag.py`, `infra/lb_infra/assembly.py`, `infra/lb_infra/stacks/__init__.py` (empty), `infra/lb_infra/stacks/data.py`, `infra/tests/conftest.py`
- Modify: `.gitignore` (+ `infra/cdk.out/`, `infra/*-outputs.json`, `infra/diff.txt`)
- Test: `infra/tests/test_data.py`

**Interfaces:**
- Consumes: `TABLE_SPECS` and `STREAM_TABLES` from `agent/src/bankagent/store/tables.py` (loaded by file path); the Task 1 results (bucket name, repo name).
- Produces:
  - constants in `lb_infra.config`: `PREFIX = "lb-demo"`, `REGION`, `AUDIENCE = "bankagent"`, `STAFF_AUDIENCE = "bankagent-staff"`, `RUNTIME_NAME = "lb_demo_agent"`, `ENDPOINT_NAME = "live"`, `SECRETS`, `DEMO_USERS_KEY`, `MESSAGE_ID_HEADER`, `REPO`;
  - `Config(github_repo, serving_bucket, git_sha="local", chat_async="0")` and `Config.from_context(node)`;
  - `table_name(name) -> str`;
  - `load_table_specs() -> tuple[dict, tuple[str, ...]]`;
  - `nag.apply(app)` and `nag.suppress(stack, ids)`;
  - `build_all(app, cfg, env) -> dict[str, Stack]` (keys `data`, plus one key per stack added by later tasks);
  - `DataStack.tables: dict[str, dynamodb.Table]` and `DataStack.bucket: s3.IBucket`;
  - pytest fixtures `stacks`, `templates`, `CFG` and `ENV` in `tests/conftest.py`.

- [ ] **Step 1: Scaffold the project**

`infra/pyproject.toml`:
```toml
[project]
name = "lb-infra"
version = "0.1.0"
description = "LATAM Bank demo deployment (spec: docs/superpowers/specs/2026-10-01-deployment-design.md)"
requires-python = ">=3.12"
dependencies = ["aws-cdk-lib>=2.220,<3", "constructs>=10.4,<11", "cdk-nag>=2.35,<3", "boto3>=1.35"]

[dependency-groups]
dev = ["pytest>=8", "pyyaml>=6"]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`infra/cdk.json`. Replace the two values with the facts recorded in Task 1, Steps 4 and 5:
```json
{
  "app": "uv run python app.py",
  "context": {
    "githubRepo": "<Task 1 Step 5: nameWithOwner>",
    "servingBucket": "<Task 1 Step 4: bucket name>",
    "chatAsync": "0",
    "gitSha": "local"
  }
}
```
`Config.from_context` refuses values that still start with `<`, so a forgotten value fails synth loudly.

Run: `uv sync`
Expected: a `uv.lock` is created, with no errors.

Append to the repo-root `.gitignore`:
```
# CDK
infra/cdk.out/
infra/*-outputs.json
infra/diff.txt
```

- [ ] **Step 2: Write the failing tests**

`infra/tests/conftest.py`:
```python
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from lb_infra.assembly import build_all
from lb_infra.config import Config

CFG = Config(github_repo="example-org/example-repo", serving_bucket="latam-bank-serving-test", git_sha="abc1234")
ENV = cdk.Environment(account="111111111111", region="us-east-2")


@pytest.fixture(scope="session")
def stacks():
    return build_all(cdk.App(), CFG, ENV)


@pytest.fixture(scope="session")
def templates(stacks):
    return {key: Template.from_stack(stack) for key, stack in stacks.items()}
```

`infra/tests/test_data.py`:
```python
import pytest

from lb_infra.config import Config
from lb_infra.specs import load_table_specs

EXPECTED_TTL = {"checkpoints": "ttl", "disputes": None, "handoffs": None, "decision_records": "ttl",
                "sessions": "ttl", "conversation_messages": "ttl"}
STREAMS = {"handoffs", "decision_records", "conversation_messages"}


def by_name(template):
    return {r["Properties"]["TableName"]: r for r in template.find_resources("AWS::DynamoDB::Table").values()}


def test_six_tables_retained_on_demand_with_pitr(templates):
    tables = by_name(templates["data"])
    assert set(tables) == {f"lb-demo-{n}" for n in EXPECTED_TTL}
    for res in tables.values():
        assert res["DeletionPolicy"] == "Retain" and res["UpdateReplacePolicy"] == "Retain"
        assert res["Properties"]["BillingMode"] == "PAY_PER_REQUEST"
        assert res["Properties"]["PointInTimeRecoverySpecification"] == {"PointInTimeRecoveryEnabled": True}


def test_ttl_and_streams(templates):
    tables = by_name(templates["data"])
    for name, ttl in EXPECTED_TTL.items():
        props = tables[f"lb-demo-{name}"]["Properties"]
        assert props.get("TimeToLiveSpecification") == ({"AttributeName": ttl, "Enabled": True} if ttl else None)
        assert props.get("StreamSpecification") == ({"StreamViewType": "NEW_IMAGE"} if name in STREAMS else None)


def test_keys_and_indexes_match_the_agent_specs(templates):
    specs, streams = load_table_specs()
    assert set(streams) == STREAMS
    tables = by_name(templates["data"])
    for name, spec in specs.items():
        props = tables[f"lb-demo-{name}"]["Properties"]
        assert props["KeySchema"] == [{"AttributeName": a, "KeyType": k} for a, _, k in spec["keys"]]
        assert sorted(g["IndexName"] for g in props.get("GlobalSecondaryIndexes", [])) == sorted(i for i, _ in spec["gsis"])


def test_data_stack_is_termination_protected(stacks):
    assert stacks["data"].termination_protection is True


def test_serving_bucket_is_referenced_not_created_and_denies_plain_http(templates):
    t = templates["data"]
    assert t.find_resources("AWS::S3::Bucket") == {}
    (policy,) = t.find_resources("AWS::S3::BucketPolicy").values()
    assert policy["Properties"]["Bucket"] == "latam-bank-serving-test"
    statements = policy["Properties"]["PolicyDocument"]["Statement"]
    deny = [s for s in statements if s.get("Sid") == "DenyInsecureTransport"]
    assert deny and deny[0]["Effect"] == "Deny" and deny[0]["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}


def test_context_placeholders_are_refused():
    class Node:
        def try_get_context(self, key):
            return {"githubRepo": "<Task 1 Step 5: nameWithOwner>", "servingBucket": "b"}.get(key)

    with pytest.raises(ValueError, match="githubRepo"):
        Config.from_context(Node())
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_data.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'lb_infra'`).

- [ ] **Step 4: Configuration, the spec loader and nag**

`infra/lb_infra/config.py`:
```python
"""Settings for the single `demo` environment (deployment spec §1, §3). Fixed names live here; values that
differ per checkout come from CDK context (infra/cdk.json, or -c on the command line)."""
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREFIX = "lb-demo"
REGION = "us-east-2"
AUDIENCE = "bankagent"
STAFF_AUDIENCE = "bankagent-staff"
RUNTIME_NAME = "lb_demo_agent"  # AgentCore runtime names allow only letters, digits and "_"
ENDPOINT_NAME = "live"
MESSAGE_ID_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Message-Id"
DEMO_USERS_KEY = "identity/demo_users.yaml"
SECRETS = {"jev": "lb-demo/jev", "signing_key": "lb-demo/idp-signing-key",
           "github_token": "lb-demo/amplify-github-token"}


def table_name(name: str) -> str:
    return f"{PREFIX}-{name}"


@dataclass(frozen=True)
class Config:
    github_repo: str
    serving_bucket: str
    git_sha: str = "local"
    chat_async: str = "0"

    @classmethod
    def from_context(cls, node) -> "Config":
        def need(key: str) -> str:
            value = node.try_get_context(key)
            if not value or str(value).startswith("<"):
                raise ValueError(f"set the CDK context value {key!r} in infra/cdk.json (deployment plan Task 1)")
            return str(value)

        return cls(github_repo=need("githubRepo"), serving_bucket=need("servingBucket"),
                   git_sha=str(node.try_get_context("gitSha") or "local"),
                   chat_async=str(node.try_get_context("chatAsync") or "0"))
```

`infra/lb_infra/specs.py`:
```python
"""Table shapes come from the agent's own TABLE_SPECS (agent/src/bankagent/store/tables.py), so CDK and
create_tables() can never disagree. The module is loaded by file path: infra doesn't install the agent."""
import importlib.util

from lb_infra.config import REPO

TABLES_PY = REPO / "agent" / "src" / "bankagent" / "store" / "tables.py"


def load_table_specs() -> tuple[dict, tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location("lb_agent_tables", TABLES_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TABLE_SPECS, tuple(module.STREAM_TABLES)
```

`infra/lb_infra/nag.py`:
```python
"""cdk-nag AwsSolutions checks. Every accepted finding carries a written reason (deployment spec §5.1)."""
from aws_cdk import Aspects, Stack
from cdk_nag import AwsSolutionsChecks, NagSuppressions

REASONS = {
    "AwsSolutions-IAM4": "AWSLambdaBasicExecutionRole is the AWS-managed minimum for Lambda logging.",
    "AwsSolutions-IAM5": "Wildcards only name sub-resources of named resources (table indexes, log streams, secret "
                         "suffixes, channel namespaces, CDK bootstrap roles), plus the actions that accept only "
                         "'*' (infra/tests/test_iam.py STAR_OK).",
    "AwsSolutions-APIG1": "Identity API access logs are remaining work (spec §9 item 6); the Lambda logs each request.",
    "AwsSolutions-APIG4": "The identity API is the public login endpoint by design; the stage is throttled (spec §4.1).",
    "AwsSolutions-L1": "Node.js 22 is pinned to match the UI plan's handlers and their tests.",
    "AwsSolutions-SQS3": "This queue is itself the publisher's dead-letter queue.",
}


def apply(app) -> None:
    Aspects.of(app).add(AwsSolutionsChecks(verbose=True))


def suppress(stack: Stack, ids: list[str]) -> None:
    NagSuppressions.add_stack_suppressions(stack, [{"id": i, "reason": REASONS[i]} for i in ids])
```

- [ ] **Step 5: The Data stack, the assembly and the app**

`infra/lb_infra/stacks/data.py`:
```python
"""LbDemo-Data (deployment spec §3 #1): the six tables and the serving bucket's TLS-only policy.
Rarely changes; everything is retained and the stack is termination-protected."""
from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3

from lb_infra.config import Config, table_name
from lb_infra.specs import load_table_specs

_TYPES = {"S": dynamodb.AttributeType.STRING, "N": dynamodb.AttributeType.NUMBER, "B": dynamodb.AttributeType.BINARY}


def _attr(key) -> dynamodb.Attribute:
    name, typ, _ = key
    return dynamodb.Attribute(name=name, type=_TYPES[typ])


class DataStack(Stack):
    def __init__(self, scope, cid: str, *, cfg: Config, **kw):
        super().__init__(scope, cid, termination_protection=True, **kw)
        specs, streams = load_table_specs()
        self.tables: dict[str, dynamodb.Table] = {}
        for name, spec in specs.items():
            keys = spec["keys"]
            table = dynamodb.Table(
                self, f"Table-{name}", table_name=table_name(name),
                partition_key=_attr(keys[0]), sort_key=_attr(keys[1]) if len(keys) > 1 else None,
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=True),
                time_to_live_attribute=spec["ttl"],
                stream=dynamodb.StreamViewType.NEW_IMAGE if name in streams else None,
                removal_policy=RemovalPolicy.RETAIN)
            for index, gkeys in spec["gsis"]:
                table.add_global_secondary_index(index_name=index, partition_key=_attr(gkeys[0]),
                                                 sort_key=_attr(gkeys[1]) if len(gkeys) > 1 else None,
                                                 projection_type=dynamodb.ProjectionType.ALL)
            self.tables[name] = table

        # The bucket was created by the data pipeline (pipeline plan Task 2); this stack only references it.
        self.bucket = s3.Bucket.from_bucket_name(self, "Serving", cfg.serving_bucket)
        b = cfg.serving_bucket
        s3.CfnBucketPolicy(self, "ServingTlsOnly", bucket=b, policy_document={
            "Version": "2012-10-17",
            "Statement": [{"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
                           "Resource": [f"arn:aws:s3:::{b}", f"arn:aws:s3:::{b}/*"],
                           "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]})
```
**If Task 1 Step 4 recorded an existing bucket policy:** add its statements to the `Statement` list above, unchanged. A bucket has exactly one policy, so this one replaces it.

`infra/lb_infra/assembly.py`:
```python
"""Builds every stack of the demo environment, in deploy order (deployment spec §3). Used by app.py and the tests."""
import aws_cdk as cdk

from lb_infra.config import Config
from lb_infra.stacks.data import DataStack


def build_all(app: cdk.App, cfg: Config, env: cdk.Environment) -> dict[str, cdk.Stack]:
    data = DataStack(app, "LbDemo-Data", cfg=cfg, env=env)
    return {"data": data}
```

`infra/app.py`:
```python
#!/usr/bin/env python3
"""LATAM Bank demo deployment: one account, environment `demo`, us-east-2 (deployment spec §3)."""
import os

import aws_cdk as cdk

from lb_infra import nag
from lb_infra.assembly import build_all
from lb_infra.config import REGION, Config

app = cdk.App()
cfg = Config.from_context(app.node)
env = cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=REGION)
build_all(app, cfg, env)
nag.apply(app)
app.synth()
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_data.py -v`
Expected: 6 passed.
Run: `npx aws-cdk@2 synth -q`
Expected: exit 0, using the `cdk.json` context values. cdk-nag may print warnings here; Task 11 makes them clean.

- [ ] **Step 7: Commit**

```bash
cd .. && git add infra/pyproject.toml infra/uv.lock infra/cdk.json infra/app.py infra/lb_infra infra/tests .gitignore
git commit -m "feat(infra): CDK app scaffold and the LbDemo-Data stack built from the agent's table specs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `LbDemo-Identity`: the IdP Lambda behind an HTTP API

**Scope limits:** the Identity stack and its tests. The Lambda code comes from Task 4.

**Check when done:** `uv run pytest tests/test_identity.py -v` passes.

**Files:**
- Create: `infra/lb_infra/stacks/identity.py`
- Modify: `infra/lb_infra/assembly.py`
- Test: `infra/tests/test_identity.py`

**Interfaces:**
- Consumes: `DataStack.bucket`; `agent/Dockerfile.identity` and the handler `bankagent.identity.lambda_handler.handler` (Task 4).
- Produces:
  - `IdentityStack.issuer: str` (`https://<apiId>.execute-api.us-east-2.amazonaws.com`, no trailing slash);
  - `IdentityStack.api: apigwv2.HttpApi`;
  - `IdentityStack.fn: lambda_.DockerImageFunction`;
  - the output `Issuer`;
  - the `build_all` key `identity`.

- [ ] **Step 1: Write the failing tests**

`infra/tests/test_identity.py`:
```python
import json

from aws_cdk.assertions import Match


def test_lambda_is_arm64_image_with_idp_environment(templates):
    t = templates["identity"]
    (fn,) = t.find_resources("AWS::Lambda::Function").values()
    p = fn["Properties"]
    assert p["PackageType"] == "Image" and p["Architectures"] == ["arm64"] and p["TracingConfig"] == {"Mode": "Active"}
    env = p["Environment"]["Variables"]
    assert env["IDP_AUDIENCE"] == "bankagent" and env["IDP_KID"] == "lb-demo-1" and env["IDP_DEMO_MODE"] == "1"
    assert env["IDP_SIGNING_SECRET_ID"] == "lb-demo/idp-signing-key"
    assert env["DEMO_USERS_S3_URI"] == "s3://latam-bank-serving-test/identity/demo_users.yaml"
    assert "execute-api" in json.dumps(env["IDP_ISSUER"])


def test_http_api_proxies_everything_and_is_throttled(templates):
    t = templates["identity"]
    t.has_resource_properties("AWS::ApiGatewayV2::Route", {"RouteKey": "ANY /{proxy+}"})
    t.has_resource_properties("AWS::ApiGatewayV2::Stage", {
        "StageName": "$default", "AutoDeploy": True,
        "DefaultRouteSettings": {"ThrottlingRateLimit": 10, "ThrottlingBurstLimit": 20}})


def test_lambda_reads_only_its_secret_and_the_identities_object(templates):
    statements = [s for pol in templates["identity"].find_resources("AWS::IAM::Policy").values()
                  for s in pol["Properties"]["PolicyDocument"]["Statement"]]
    text = json.dumps(statements)
    assert "secretsmanager:GetSecretValue" in text and "lb-demo/idp-signing-key" in text
    assert "latam-bank-serving-test/identity/demo_users.yaml" in text
    assert "dynamodb:" not in text and "bedrock" not in text


def test_logs_kept_30_days_and_issuer_output(templates):
    t = templates["identity"]
    t.has_resource_properties("AWS::Logs::LogGroup", {"LogGroupName": "/aws/lambda/lb-demo-identity",
                                                      "RetentionInDays": 30})
    t.has_output("Issuer", {"Value": Match.any_value()})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_identity.py -v`
Expected: FAIL (`KeyError: 'identity'`).

- [ ] **Step 3: Write the stack**

`infra/lb_infra/stacks/identity.py`:
```python
"""LbDemo-Identity (deployment spec §3 #2): the mock OIDC IdP as one container Lambda behind an HTTP API.
The issuer is the API's default URL, so the AgentCore and AppSync authorizers can reach its discovery doc."""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration

from lb_infra import nag
from lb_infra.config import AUDIENCE, DEMO_USERS_KEY, PREFIX, REPO, SECRETS, Config


class IdentityStack(Stack):
    def __init__(self, scope, cid: str, *, cfg: Config, data, **kw):
        super().__init__(scope, cid, **kw)
        self.api = apigwv2.HttpApi(self, "Api", api_name=f"{PREFIX}-identity", create_default_stage=False)
        apigwv2.HttpStage(self, "DefaultStage", http_api=self.api, stage_name="$default", auto_deploy=True,
                          throttle=apigwv2.ThrottleSettings(rate_limit=10, burst_limit=20))
        self.issuer = f"https://{self.api.api_id}.execute-api.{self.region}.amazonaws.com"

        log_group = logs.LogGroup(self, "Logs", log_group_name=f"/aws/lambda/{PREFIX}-identity",
                                  retention=logs.RetentionDays.ONE_MONTH, removal_policy=RemovalPolicy.DESTROY)
        self.fn = lambda_.DockerImageFunction(
            self, "Fn", function_name=f"{PREFIX}-identity",
            code=lambda_.DockerImageCode.from_image_asset(str(REPO / "agent"), file="Dockerfile.identity",
                                                          platform=ecr_assets.Platform.LINUX_ARM64),
            architecture=lambda_.Architecture.ARM_64, memory_size=512, timeout=Duration.seconds(10),
            tracing=lambda_.Tracing.ACTIVE, log_group=log_group,
            environment={"IDP_ISSUER": self.issuer, "IDP_AUDIENCE": AUDIENCE, "IDP_KID": f"{PREFIX}-1",
                         "IDP_SIGNING_SECRET_ID": SECRETS["signing_key"],
                         "DEMO_USERS_S3_URI": f"s3://{cfg.serving_bucket}/{DEMO_USERS_KEY}", "IDP_DEMO_MODE": "1"})
        secretsmanager.Secret.from_secret_name_v2(self, "SigningKey", SECRETS["signing_key"]).grant_read(self.fn)
        data.bucket.grant_read(self.fn, DEMO_USERS_KEY)
        self.api.add_routes(path="/{proxy+}", methods=[apigwv2.HttpMethod.ANY],
                            integration=HttpLambdaIntegration("Idp", self.fn))
        CfnOutput(self, "Issuer", value=self.issuer)
        nag.suppress(self, ["AwsSolutions-IAM4", "AwsSolutions-IAM5", "AwsSolutions-APIG1", "AwsSolutions-APIG4"])
```

In `infra/lb_infra/assembly.py`, add `from lb_infra.stacks.identity import IdentityStack`, and replace the body of `build_all` with:
```python
    data = DataStack(app, "LbDemo-Data", cfg=cfg, env=env)
    identity = IdentityStack(app, "LbDemo-Identity", cfg=cfg, data=data, env=env)
    return {"data": data, "identity": identity}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_identity.py tests/test_data.py -v`
Expected: all pass. If synth reports a circular dependency between `Fn` and `Api`, move `IDP_ISSUER` out of the constructor's `environment` and set it after the route with `self.fn.add_environment("IDP_ISSUER", self.issuer)`. The function→API reference is one-directional, so this should not happen.

- [ ] **Step 5: Commit**

```bash
cd .. && git add infra/lb_infra/stacks/identity.py infra/lb_infra/assembly.py infra/tests/test_identity.py
git commit -m "feat(infra): LbDemo-Identity stack, the mock IdP as a container Lambda behind a throttled HTTP API

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `LbDemo-Agent`: the AgentCore Runtime

**Scope limits:** the image asset, the execution role, the runtime, the `live` endpoint and log retention.

**Check when done:** `uv run pytest tests/test_agent.py -v` passes.

**Files:**
- Create: `infra/lb_infra/stacks/agent.py`
- Modify: `infra/lb_infra/config.py` (+ `BEDROCK_ACTIONS`, `bedrock_resources`, `OTEL_ENV`), `infra/lb_infra/assembly.py`
- Test: `infra/tests/test_agent.py`

**Interfaces:**
- Consumes: `DataStack.tables`, `IdentityStack.issuer`, `agent/Dockerfile` (Task 3), and the Task 1 results (Steps 1, 2, 3 and 7).
- Produces:
  - `AgentStack.runtime_id: str`;
  - `AgentStack.invoke_url: str` (`https://bedrock-agentcore.us-east-2.amazonaws.com/runtimes/<url-encoded ARN>/invocations?qualifier=live`);
  - `AgentStack.role: iam.Role`;
  - outputs `RuntimeId`, `RuntimeArn` and `InvokeUrl`;
  - the `build_all` key `agent`.

- [ ] **Step 1: Write the failing tests**

`infra/tests/test_agent.py`:
```python
import json


def runtime(templates):
    (res,) = templates["agent"].find_resources("AWS::BedrockAgentCore::Runtime").values()
    return res["Properties"]


def agent_statements(templates):
    return [s for pol in templates["agent"].find_resources("AWS::IAM::Policy").values()
            for s in pol["Properties"]["PolicyDocument"]["Statement"]]


def actions(stmt):
    a = stmt["Action"]
    return a if isinstance(a, list) else [a]


def test_runtime_shape(templates):
    p = runtime(templates)
    assert p["AgentRuntimeName"] == "lb_demo_agent"
    assert p["NetworkConfiguration"] == {"NetworkMode": "PUBLIC"} and p["ProtocolConfiguration"] == "HTTP"
    jwt = p["AuthorizerConfiguration"]["CustomJWTAuthorizer"]
    assert jwt["AllowedAudience"] == ["bankagent"]
    assert "/.well-known/openid-configuration" in json.dumps(jwt["DiscoveryUrl"])
    assert set(p["RequestHeaderConfiguration"]["RequestHeaderAllowlist"]) == {
        "Authorization", "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Message-Id"}


def test_runtime_environment_has_no_secret_values(templates):
    env = runtime(templates)["EnvironmentVariables"]
    assert env["JEV_SECRET_ID"] == "lb-demo/jev" and "JEV_API_KEY" not in env
    assert env["GIT_SHA"] == "abc1234" and env["TABLE_PREFIX"] == "lb-demo" and env["LOG_MESSAGE_TEXT"] == "false"
    assert env["SERVING_URI"] == "s3://latam-bank-serving-test/serving" and env["IDP_AUDIENCE"] == "bankagent"
    assert "/jwks.json" in json.dumps(env["IDP_JWKS_URL"])
    assert env["OTEL_PYTHON_DISTRO"] == "aws_distro"


def test_live_endpoint_tracks_the_new_version(templates):
    templates["agent"].has_resource_properties("AWS::BedrockAgentCore::RuntimeEndpoint", {"Name": "live"})


def test_execution_role_trusts_agentcore_in_this_account(templates):
    roles = templates["agent"].find_resources("AWS::IAM::Role")
    trust = [r["Properties"]["AssumeRolePolicyDocument"]["Statement"][0] for r in roles.values()
             if r["Properties"].get("RoleName") == "lb-demo-agent-exec"][0]
    assert trust["Principal"] == {"Service": "bedrock-agentcore.amazonaws.com"}
    assert trust["Condition"]["StringEquals"]["aws:SourceAccount"] == "111111111111"


def test_least_privilege_data_access(templates):
    stmts = agent_statements(templates)
    every = [a for s in stmts for a in actions(s)]
    assert "dynamodb:Scan" not in every and "dynamodb:*" not in every
    deletes = [s for s in stmts if "dynamodb:DeleteItem" in actions(s)]
    assert len(deletes) == 1 and "checkpoints" in json.dumps(deletes[0]["Resource"])
    text = json.dumps(stmts)
    assert "bedrock:InvokeModel" in text or "bedrock-mantle" in text
    assert "latam-bank-serving-test/serving/*" in text and "lb-demo/jev" in text


def test_invoke_url_uses_the_live_qualifier(templates):
    out = templates["agent"].find_outputs("InvokeUrl")
    assert "qualifier=live" in json.dumps(out)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_agent.py -v`
Expected: FAIL (`KeyError: 'agent'`).

- [ ] **Step 3: Configuration for the runtime**

Append to `infra/lb_infra/config.py`:
```python
# Bedrock actions for the agent's Claude client. Task 1 Step 3 records the client's signing service; if it isn't
# "bedrock", replace these with the actions recorded there.
BEDROCK_ACTIONS = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]


def bedrock_resources(account: str, region: str) -> list[str]:
    return [f"arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
            f"arn:aws:bedrock:{region}:{account}:inference-profile/*anthropic.claude-*"]


# ADOT settings for a custom container on AgentCore Runtime (deployment spec §6.1). Task 1 Step 7 confirms them
# against the agents-optimize skill; add any variable it lists that is missing here.
OTEL_ENV = {
    "AGENT_OBSERVABILITY_ENABLED": "true",
    "OTEL_PYTHON_DISTRO": "aws_distro",
    "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_RESOURCE_ATTRIBUTES": f"service.name={RUNTIME_NAME}",
}
```

- [ ] **Step 4: Write the stack**

`infra/lb_infra/stacks/agent.py`. If Task 1 Step 2 recorded different nested class names, change **only the names**:
```python
"""LbDemo-Agent (deployment spec §3 #3): the agent image → AgentCore Runtime with a JWT authorizer, plus the `live`
endpoint the BFF invokes. Changes on every agent commit: GIT_SHA and the image digest make a new runtime version."""
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_bedrockagentcore as ac
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs

from lb_infra import nag
from lb_infra.config import (AUDIENCE, BEDROCK_ACTIONS, ENDPOINT_NAME, MESSAGE_ID_HEADER, OTEL_ENV, PREFIX, REPO,
                             RUNTIME_NAME, SECRETS, Config, bedrock_resources)

TABLE_ACTIONS = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query",
                 "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem", "dynamodb:ConditionCheckItem",
                 "dynamodb:DescribeTable"]


class AgentStack(Stack):
    def __init__(self, scope, cid: str, *, cfg: Config, data, identity, **kw):
        super().__init__(scope, cid, **kw)
        acct, region = self.account, self.region
        image = ecr_assets.DockerImageAsset(self, "Image", directory=str(REPO / "agent"),
                                            platform=ecr_assets.Platform.LINUX_ARM64)
        self.role = iam.Role(self, "Exec", role_name=f"{PREFIX}-agent-exec", assumed_by=iam.ServicePrincipal(
            "bedrock-agentcore.amazonaws.com", conditions={
                "StringEquals": {"aws:SourceAccount": acct},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{acct}:*"}}))
        image.repository.grant_pull(self.role)
        tables = data.tables
        add = self.role.add_to_policy
        add(iam.PolicyStatement(actions=BEDROCK_ACTIONS, resources=bedrock_resources(acct, region)))
        add(iam.PolicyStatement(actions=["s3:GetObject"], resources=[f"arn:aws:s3:::{cfg.serving_bucket}/serving/*"]))
        add(iam.PolicyStatement(actions=["s3:ListBucket"], resources=[f"arn:aws:s3:::{cfg.serving_bucket}"],
                                conditions={"StringLike": {"s3:prefix": ["serving/*", "serving/"]}}))
        add(iam.PolicyStatement(actions=TABLE_ACTIONS, resources=[t.table_arn for t in tables.values()]
                                + [f"{t.table_arn}/index/*" for t in tables.values()]))
        add(iam.PolicyStatement(actions=["dynamodb:DeleteItem"], resources=[tables["checkpoints"].table_arn]))
        add(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"],
                                resources=[f"arn:aws:secretsmanager:{region}:{acct}:secret:{SECRETS['jev']}-*"]))
        add(iam.PolicyStatement(actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                                         "logs:DescribeLogStreams"],
                                resources=[f"arn:aws:logs:{region}:{acct}:log-group:/aws/bedrock-agentcore/runtimes/*"]))
        add(iam.PolicyStatement(actions=["logs:DescribeLogGroups"],
                                resources=[f"arn:aws:logs:{region}:{acct}:log-group:*"]))
        add(iam.PolicyStatement(actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules",
                                         "xray:GetSamplingTargets"], resources=["*"]))
        add(iam.PolicyStatement(actions=["cloudwatch:PutMetricData"], resources=["*"],
                                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}))
        add(iam.PolicyStatement(
            actions=["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                     "bedrock-agentcore:GetWorkloadAccessTokenForUserId"],
            resources=[f"arn:aws:bedrock-agentcore:{region}:{acct}:workload-identity-directory/default",
                       f"arn:aws:bedrock-agentcore:{region}:{acct}:workload-identity-directory/default/"
                       f"workload-identity/{RUNTIME_NAME}-*"]))

        env = {"SERVING_URI": f"s3://{cfg.serving_bucket}/serving", "TABLE_PREFIX": PREFIX,
               "IDP_ISSUER": identity.issuer, "IDP_AUDIENCE": AUDIENCE, "IDP_JWKS_URL": f"{identity.issuer}/jwks.json",
               "JEV_SECRET_ID": SECRETS["jev"], "GIT_SHA": cfg.git_sha, "LOG_MESSAGE_TEXT": "false", **OTEL_ENV}
        runtime = ac.CfnRuntime(
            self, "Runtime", agent_runtime_name=RUNTIME_NAME, role_arn=self.role.role_arn,
            agent_runtime_artifact=ac.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=ac.CfnRuntime.ContainerConfigurationProperty(container_uri=image.image_uri)),
            network_configuration=ac.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="HTTP",
            authorizer_configuration=ac.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=ac.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"{identity.issuer}/.well-known/openid-configuration", allowed_audience=[AUDIENCE])),
            request_header_configuration=ac.CfnRuntime.RequestHeaderConfigurationProperty(
                request_header_allowlist=["Authorization", MESSAGE_ID_HEADER]),
            environment_variables=env, description="LATAM Bank customer-service agent (demo)")
        runtime.node.add_dependency(self.role)  # the role and its policy exist before AgentCore validates them
        endpoint = ac.CfnRuntimeEndpoint(self, "Live", agent_runtime_id=runtime.attr_agent_runtime_id,
                                         name=ENDPOINT_NAME, agent_runtime_version=runtime.attr_agent_runtime_version)
        logs.LogRetention(self, "RuntimeLogRetention", retention=logs.RetentionDays.ONE_MONTH,
                          log_group_name=f"/aws/bedrock-agentcore/runtimes/{runtime.attr_agent_runtime_id}-{ENDPOINT_NAME}"
                          ).node.add_dependency(endpoint)

        self.runtime_id = runtime.attr_agent_runtime_id
        self.invoke_url = (f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3A"
                           f"{region}%3A{acct}%3Aruntime%2F{runtime.attr_agent_runtime_id}/invocations"
                           f"?qualifier={ENDPOINT_NAME}")
        CfnOutput(self, "RuntimeId", value=self.runtime_id)
        CfnOutput(self, "RuntimeArn", value=runtime.attr_agent_runtime_arn)
        CfnOutput(self, "InvokeUrl", value=self.invoke_url)
        nag.suppress(self, ["AwsSolutions-IAM4", "AwsSolutions-IAM5"])
```
**If Task 1 Step 7 recorded a different runtime log-group pattern:** change `log_group_name` to match it.

**If Task 1 Step 1 = no** (no CloudFormation resource): replace `CfnRuntime` and `CfnRuntimeEndpoint` with an `aws_cdk.custom_resources.AwsCustomResource`:
- `on_create`: `AwsSdkCall(service="BedrockAgentCoreControl", action="createAgentRuntime", parameters={...})`, with the same fields in API casing (`agentRuntimeName`, `agentRuntimeArtifact.containerConfiguration.containerUri`, `roleArn`, `networkConfiguration`, `authorizerConfiguration.customJWTAuthorizer`, `requestHeaderConfiguration`, `environmentVariables`), and `physical_resource_id=PhysicalResourceId.from_response("agentRuntimeId")`.
- `on_update`: `updateAgentRuntime`, with `agentRuntimeId` from the physical id.
- `on_delete`: `deleteAgentRuntime`.
- The policy is `bedrock-agentcore:*AgentRuntime*` on `arn:aws:bedrock-agentcore:{region}:{acct}:runtime/*`, plus `iam:PassRole` on the execution role.

Read `runtime_id` with `get_response_field("agentRuntimeId")`. Keep the outputs and tests; change only the resource lookups in `test_agent.py` to the custom resource's `Create` payload.

In `infra/lb_infra/assembly.py`, add `from lb_infra.stacks.agent import AgentStack`. After the `identity = …` line, add:
```python
    agent = AgentStack(app, "LbDemo-Agent", cfg=cfg, data=data, identity=identity, env=env)
```
and add `"agent": agent` to the returned dict.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_agent.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
cd .. && git add infra/lb_infra/stacks/agent.py infra/lb_infra/config.py infra/lb_infra/assembly.py infra/tests/test_agent.py
git commit -m "feat(infra): LbDemo-Agent stack, AgentCore runtime with JWT authorizer, live endpoint and scoped role

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `LbDemo-Realtime`: AppSync Events from Python, reusing the UI plan's handlers

**Scope limits:** the Python stack; deleting the UI plan's TypeScript CDK app files; a note in the UI plan. No handler code changes.

**Check when done:** `uv run pytest tests/test_realtime.py -v` passes, and `cd realtime && npm test` still passes.

**Files:**
- Create: `infra/lb_infra/stacks/realtime.py`
- Modify: `infra/lb_infra/assembly.py`, `infra/realtime/package.json`, `infra/realtime/tsconfig.json`, `docs/superpowers/plans/2026-09-30-ui.md` (a note under "Plan status")
- Delete: `infra/realtime/bin/app.ts`, `infra/realtime/lib/realtime-stack.ts`, `infra/realtime/cdk.json`, `infra/realtime/test/stack.test.ts`, `infra/realtime/scripts/stream-arns.sh`
- Test: `infra/tests/test_realtime.py`

**Interfaces:**
- Consumes:
  - `infra/realtime/authorizer/index.ts` (env `IDP_ISSUER`, `IDP_JWKS_URL`);
  - `infra/realtime/publisher/index.ts` (env `EVENTS_HTTP_DOMAIN`);
  - `infra/realtime/handlers/namespace.js` (UI plan Tasks 7–8);
  - `DataStack.tables`, `IdentityStack.issuer`.
- Produces:
  - `RealtimeStack.api: appsync.EventApi`, `.publisher`, `.authorizer` and `.dlq: sqs.Queue`;
  - outputs `HttpDomain` and `RealtimeDomain`;
  - the `build_all` key `realtime`.

- [ ] **Step 1: Write the failing tests**

`infra/tests/test_realtime.py`:
```python
import json


def test_event_api_with_three_namespaces(templates):
    t = templates["realtime"]
    assert len(t.find_resources("AWS::AppSync::Api")) == 1
    names = sorted(r["Properties"]["Name"] for r in t.find_resources("AWS::AppSync::ChannelNamespace").values())
    assert names == ["queue", "session", "trace"]


def test_publish_is_iam_only_and_subscribe_is_lambda(templates):
    (api,) = templates["realtime"].find_resources("AWS::AppSync::Api").values()
    cfg = api["Properties"]["EventConfig"]
    assert [m["AuthType"] for m in cfg["DefaultPublishAuthModes"]] == ["AWS_IAM"]
    assert [m["AuthType"] for m in cfg["DefaultSubscribeAuthModes"]] == ["AWS_LAMBDA"]


def test_three_stream_sources_with_bisect_retries_and_dlq(templates):
    maps = templates["realtime"].find_resources("AWS::Lambda::EventSourceMapping")
    assert len(maps) == 3
    for m in maps.values():
        p = m["Properties"]
        assert p["BisectBatchOnFunctionError"] is True and p["MaximumRetryAttempts"] == 5
        assert p["FunctionResponseTypes"] == ["ReportBatchItemFailures"] and p["StartingPosition"] == "LATEST"
        assert "OnFailure" in p["DestinationConfig"]


def test_publisher_can_publish_and_authorizer_knows_the_issuer(templates):
    t = templates["realtime"]
    text = json.dumps(t.find_resources("AWS::IAM::Policy"))
    assert "appsync:EventPublish" in text
    fns = t.find_resources("AWS::Lambda::Function")
    envs = [f["Properties"].get("Environment", {}).get("Variables", {}) for f in fns.values()]
    assert any("IDP_JWKS_URL" in e and "/jwks.json" in json.dumps(e["IDP_JWKS_URL"]) for e in envs)
    assert any("EVENTS_HTTP_DOMAIN" in e for e in envs)
    for f in fns.values():
        if f["Properties"].get("Runtime", "").startswith("nodejs"):
            assert f["Properties"]["Runtime"] == "nodejs22.x" and f["Properties"]["Architectures"] == ["arm64"]


def test_dlq_retains_14_days_and_requires_tls(templates):
    t = templates["realtime"]
    t.has_resource_properties("AWS::SQS::Queue", {"QueueName": "lb-demo-publisher-dlq", "MessageRetentionPeriod": 1209600})
    assert "aws:SecureTransport" in json.dumps(t.find_resources("AWS::SQS::QueuePolicy"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_realtime.py -v`
Expected: FAIL (`KeyError: 'realtime'`).

- [ ] **Step 3: Write the stack**

`infra/lb_infra/stacks/realtime.py`. If Task 1 Step 2 recorded different `EventApi` property names, change **only the names**:
```python
"""LbDemo-Realtime (deployment spec §3 #4): AppSync Events + the UI plan's TypeScript authorizer and publisher
(infra/realtime/*, bundled here by esbuild). Producers only write DynamoDB; the publisher turns Stream records into
channel events; failed records go to the DLQ after 5 retries (UI spec §3, §10)."""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_appsync as appsync
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_nodejs as nodejs
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from aws_cdk.aws_lambda_event_sources import DynamoEventSource, SqsDlq

from lb_infra import nag
from lb_infra.config import PREFIX, REPO, Config

RT = REPO / "infra" / "realtime"
STREAM_KINDS = ("handoffs", "decision_records", "conversation_messages")


class RealtimeStack(Stack):
    def __init__(self, scope, cid: str, *, cfg: Config, data, identity, **kw):
        super().__init__(scope, cid, **kw)

        def fn(cid_: str, name: str, entry: str, timeout: int, environment: dict) -> nodejs.NodejsFunction:
            group = logs.LogGroup(self, f"{cid_}Logs", log_group_name=f"/aws/lambda/{PREFIX}-{name}",
                                  retention=logs.RetentionDays.ONE_MONTH, removal_policy=RemovalPolicy.DESTROY)
            return nodejs.NodejsFunction(
                self, cid_, function_name=f"{PREFIX}-{name}", entry=str(RT / entry),
                project_root=str(RT), deps_lock_file_path=str(RT / "package-lock.json"),
                runtime=lambda_.Runtime.NODEJS_22_X, architecture=lambda_.Architecture.ARM_64,
                timeout=Duration.seconds(timeout), tracing=lambda_.Tracing.ACTIVE, log_group=group,
                environment=environment, bundling=nodejs.BundlingOptions(minify=True, source_map=True))

        self.authorizer = fn("Authorizer", "rt-authorizer", "authorizer/index.ts", 5,
                             {"IDP_ISSUER": identity.issuer, "IDP_JWKS_URL": f"{identity.issuer}/jwks.json"})
        iam_mode, lambda_mode = appsync.AppSyncAuthorizationType.IAM, appsync.AppSyncAuthorizationType.LAMBDA
        self.api = appsync.EventApi(self, "Events", api_name=f"{PREFIX}-events",
                                    authorization_config=appsync.EventApiAuthConfig(
                                        auth_providers=[
                                            appsync.AppSyncAuthProvider(authorization_type=iam_mode),
                                            appsync.AppSyncAuthProvider(
                                                authorization_type=lambda_mode,
                                                lambda_authorizer_config=appsync.AppSyncLambdaAuthorizerConfig(
                                                    handler=self.authorizer, results_cache_ttl=Duration.seconds(0)))],
                                        connection_auth_mode_types=[lambda_mode, iam_mode],
                                        default_publish_auth_mode_types=[iam_mode],
                                        default_subscribe_auth_mode_types=[lambda_mode]))
        code = appsync.Code.from_asset(str(RT / "handlers" / "namespace.js"))
        for namespace in ("session", "queue", "trace"):
            self.api.add_channel_namespace(namespace, code=code)

        self.dlq = sqs.Queue(self, "PublisherDlq", queue_name=f"{PREFIX}-publisher-dlq",
                             retention_period=Duration.days(14), enforce_ssl=True)
        self.publisher = fn("Publisher", "rt-publisher", "publisher/index.ts", 30,
                            {"EVENTS_HTTP_DOMAIN": self.api.http_dns})
        self.api.grant_publish(self.publisher)
        for kind in STREAM_KINDS:
            self.publisher.add_event_source(DynamoEventSource(
                data.tables[kind], starting_position=lambda_.StartingPosition.LATEST, batch_size=25,
                bisect_batch_on_error=True, report_batch_item_failures=True, retry_attempts=5,
                on_failure=SqsDlq(self.dlq)))
        CfnOutput(self, "HttpDomain", value=self.api.http_dns)
        CfnOutput(self, "RealtimeDomain", value=self.api.realtime_dns)
        nag.suppress(self, ["AwsSolutions-IAM4", "AwsSolutions-IAM5", "AwsSolutions-L1", "AwsSolutions-SQS3"])
```

In `infra/lb_infra/assembly.py`, add `from lb_infra.stacks.realtime import RealtimeStack`, then:
```python
    realtime = RealtimeStack(app, "LbDemo-Realtime", cfg=cfg, data=data, identity=identity, env=env)
```
after the agent line, and add `"realtime": realtime` to the returned dict.

- [ ] **Step 4: Retire the TypeScript CDK app**

```bash
cd realtime
git rm bin/app.ts lib/realtime-stack.ts cdk.json test/stack.test.ts scripts/stream-arns.sh
npm pkg delete scripts.synth scripts.cdk dependencies.aws-cdk-lib dependencies.constructs devDependencies.aws-cdk
npm install
cd ..
```
In `infra/realtime/tsconfig.json`, set `"include": ["authorizer", "publisher", "handlers", "scripts", "test"]`.

Run: `cd realtime && npm test && cd ..`
Expected: the handler and rule tests pass (the stack test is gone).

- [ ] **Step 5: Note in the UI plan**

In `docs/superpowers/plans/2026-09-30-ui.md`, insert this paragraph directly after the "**Plan status:**" paragraph:
```markdown
**Deployment note (2026-10-01):** infrastructure is deployed by `docs/superpowers/plans/2026-10-01-deployment.md`. Its Python stack `LbDemo-Realtime` replaces this plan's TypeScript `RealtimeStack` (Task 7 Step 6, Steps 8–9 deploy commands; Task 8 Steps 5 and 7), and its `LbDemo-Web` stack replaces Task 24 Steps 2–3. The handler code, its tests and `scripts/probe-subscribe.ts` stay as written here.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_realtime.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
cd .. && git add infra/lb_infra/stacks/realtime.py infra/lb_infra/assembly.py infra/tests/test_realtime.py infra/realtime docs/superpowers/plans/2026-09-30-ui.md
git commit -m "feat(infra): LbDemo-Realtime in Python CDK reusing the UI handlers; retire the TS CDK app

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `LbDemo-Web`: Amplify Hosting, plus the build tag and trace link in the web app

**Scope limits:** the Web stack; `amplify.yml`; three small additions to `web/` (an X-Ray link helper, the trace link, a build tag on staff pages). No other UI changes.

**Check when done:** `uv run pytest tests/test_web.py -v` passes, and `cd ../web && npm test` passes.

**Files:**
- Create: `infra/lb_infra/stacks/web.py`, `web/lib/trace/xray.ts`, `web/components/staff/BuildTag.tsx`, `web/app/agent/layout.tsx`, `web/app/trace/layout.tsx`, `web/app/demo/layout.tsx`
- Modify: `infra/lb_infra/assembly.py`, `amplify.yml`, `web/lib/server/records.ts`, `web/lib/trace/viewModel.ts`, `web/components/trace/TraceTurn.tsx`
- Test: `infra/tests/test_web.py`, `web/tests/unit/xray.test.ts`

**Interfaces:**
- Consumes:
  - `DataStack.tables`, `IdentityStack.issuer`, `AgentStack.invoke_url`, `RealtimeStack.api`;
  - the web env schema in `web/lib/server/env.ts` (UI Task 11);
  - `buildTrace`/`TraceTurn` (UI Task 15);
  - `TraceTurnView` (UI Task 21).
- Produces:
  - `WebStack.app_id: str`;
  - outputs `AppId` and `AppUrl`;
  - `web_env(cfg, identity, agent, realtime) -> dict[str, str]`;
  - `xrayTraceUrl(traceId: string, region?: string): string | null`;
  - `TraceTurn.traceUrl?: string`;
  - the `build_all` key `web`.

- [ ] **Step 1: Write the failing tests**

`infra/tests/test_web.py`:
```python
import json

WEB_ENV_KEYS = {"IDP_URL", "IDP_ISSUER", "IDP_AUDIENCE", "STAFF_AUDIENCE", "AGENTCORE_INVOKE_URL", "TABLE_PREFIX",
                "NEXT_PUBLIC_EVENTS_HTTP_DOMAIN", "NEXT_PUBLIC_EVENTS_REGION", "DEMO_MODE", "CHAT_ASYNC"}


def test_amplify_app_is_ssr_with_compute_role_and_token_from_secrets_manager(templates):
    (app,) = templates["web"].find_resources("AWS::Amplify::App").values()
    p = app["Properties"]
    assert p["Platform"] == "WEB_COMPUTE" and p["Repository"] == "https://github.com/example-org/example-repo"
    assert "resolve:secretsmanager:lb-demo/amplify-github-token" in json.dumps(p["AccessToken"])
    assert "ComputeRoleArn" in p
    assert {"Name": "AMPLIFY_MONOREPO_APP_ROOT", "Value": "web"} in p["EnvironmentVariables"]


def test_main_branch_never_auto_builds_and_gets_the_stack_outputs(templates):
    (branch,) = templates["web"].find_resources("AWS::Amplify::Branch").values()
    p = branch["Properties"]
    assert p["BranchName"] == "main" and p["EnableAutoBuild"] is False and p["Stage"] == "PRODUCTION"
    env = {e["Name"]: e["Value"] for e in p["EnvironmentVariables"]}
    assert set(env) == WEB_ENV_KEYS
    assert env["TABLE_PREFIX"] == "lb-demo" and env["DEMO_MODE"] == "1" and env["CHAT_ASYNC"] == "0"
    assert env["IDP_AUDIENCE"] == "bankagent" and env["STAFF_AUDIENCE"] == "bankagent-staff"
    assert "qualifier=live" in json.dumps(env["AGENTCORE_INVOKE_URL"])


def test_compute_role_is_dynamodb_only(templates):
    stmts = [s for pol in templates["web"].find_resources("AWS::IAM::Policy").values()
             for s in pol["Properties"]["PolicyDocument"]["Statement"]]
    actions = {a for s in stmts for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])}
    assert actions and all(a.startswith("dynamodb:") for a in actions)
    # cross-stack ARNs are Fn::ImportValue names built from logical ids, which drop "_" ("Tabledecisionrecords…")
    records = [s for s in stmts if "decisionrecords" in json.dumps(s["Resource"]).lower()]
    assert records and all(set(s["Action"]) <= {"dynamodb:GetItem", "dynamodb:Query"} for s in records)
    roles = templates["web"].find_resources("AWS::IAM::Role")
    assert any(r["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"] ==
               {"Service": "amplify.amazonaws.com"} for r in roles.values())
```

`web/tests/unit/xray.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import type { DecisionRecord } from "@/lib/server/records";
import { buildTrace } from "@/lib/trace/viewModel";
import { xrayTraceUrl } from "@/lib/trace/xray";

const TID = "1-6720f2a0-0123456789abcdef01234567";
const rec = (seq: number, kind: string, extra: Partial<DecisionRecord> = {}): DecisionRecord => ({
  session_id: "S-1", sk: `T1#000${seq}`, turn_id: "T1", seq, node: kind === "turn_end" ? "turn" : "understand", kind,
  ts: `2026-10-01T00:00:0${seq}Z`,
  payload: kind === "turn_end" ? { duration_ms: 900, awaiting: "none" } : { next: "reply", reasons: [], goal: {} },
  versions: {}, ...extra,
});

describe("xrayTraceUrl", () => {
  it("builds the CloudWatch X-Ray console link", () => {
    expect(xrayTraceUrl(TID)).toBe(
      `https://us-east-2.console.aws.amazon.com/cloudwatch/home?region=us-east-2#xray:traces/${TID}`);
  });
  it("rejects anything that isn't an X-Ray trace id", () => {
    expect(xrayTraceUrl("javascript:alert(1)")).toBeNull();
    expect(xrayTraceUrl("1-xyz-123")).toBeNull();
  });
});

describe("buildTrace trace link", () => {
  it("links a turn when one of its records carries trace_id", () => {
    const [turn] = buildTrace([rec(1, "route", { trace_id: TID }), rec(2, "turn_end")], []);
    expect(turn.traceUrl).toBe(xrayTraceUrl(TID));
  });
  it("has no link without trace_id", () => {
    expect(buildTrace([rec(1, "route"), rec(2, "turn_end")], [])[0].traceUrl).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_web.py -v`
Expected: FAIL (`KeyError: 'web'`).
Run: `cd ../web && npx vitest run tests/unit/xray.test.ts; cd ../infra`
Expected: FAIL (cannot resolve `@/lib/trace/xray`).

- [ ] **Step 3: Write the stack**

`infra/lb_infra/stacks/web.py`:
```python
"""LbDemo-Web (deployment spec §3 #5): the Amplify Hosting app for web/ (SSR), its compute role, and the branch
environment wired from the other stacks. Auto-build is off: deploy.yml starts the build after CDK (spec §5.2)."""
from aws_cdk import CfnOutput, SecretValue, Stack
from aws_cdk import aws_amplify as amplify
from aws_cdk import aws_iam as iam

from lb_infra import nag
from lb_infra.config import AUDIENCE, PREFIX, REGION, SECRETS, STAFF_AUDIENCE, Config


def web_env(cfg: Config, identity, agent, realtime) -> dict[str, str]:
    return {"IDP_URL": identity.issuer, "IDP_ISSUER": identity.issuer, "IDP_AUDIENCE": AUDIENCE,
            "STAFF_AUDIENCE": STAFF_AUDIENCE, "AGENTCORE_INVOKE_URL": agent.invoke_url, "TABLE_PREFIX": PREFIX,
            "NEXT_PUBLIC_EVENTS_HTTP_DOMAIN": realtime.api.http_dns, "NEXT_PUBLIC_EVENTS_REGION": REGION,
            "DEMO_MODE": "1", "CHAT_ASYNC": cfg.chat_async}


def _vars(env: dict[str, str]):
    return [amplify.CfnApp.EnvironmentVariableProperty(name=k, value=v) for k, v in env.items()]


class WebStack(Stack):
    def __init__(self, scope, cid: str, *, cfg: Config, data, identity, agent, realtime, **kw):
        super().__init__(scope, cid, **kw)
        t = data.tables
        role = iam.Role(self, "Compute", role_name=f"{PREFIX}-web-compute",
                        assumed_by=iam.ServicePrincipal("amplify.amazonaws.com"))
        # The BFF invokes AgentCore with the customer's Bearer token, not IAM (UI plan Task 13), so no
        # bedrock-agentcore permission here. It never publishes to AppSync either.
        role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query",
                     "dynamodb:ConditionCheckItem"],
            resources=[t["sessions"].table_arn, t["conversation_messages"].table_arn, t["handoffs"].table_arn,
                       f"{t['handoffs'].table_arn}/index/*"]))
        role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:Query"],
                                               resources=[t["decision_records"].table_arn]))
        app = amplify.CfnApp(
            self, "App", name=f"{PREFIX}-web", repository=f"https://github.com/{cfg.github_repo}",
            access_token=SecretValue.secrets_manager(SECRETS["github_token"]).unsafe_unwrap(),
            platform="WEB_COMPUTE", compute_role_arn=role.role_arn,
            environment_variables=_vars({"AMPLIFY_MONOREPO_APP_ROOT": "web"}))
        amplify.CfnBranch(self, "Main", app_id=app.attr_app_id, branch_name="main", enable_auto_build=False,
                          framework="Next.js - SSR", stage="PRODUCTION",
                          environment_variables=[amplify.CfnBranch.EnvironmentVariableProperty(name=k, value=v)
                                                 for k, v in web_env(cfg, identity, agent, realtime).items()])
        self.app_id = app.attr_app_id
        CfnOutput(self, "AppId", value=self.app_id)
        CfnOutput(self, "AppUrl", value=f"https://main.{app.attr_default_domain}")
        nag.suppress(self, ["AwsSolutions-IAM5"])
```

**If Task 1 Step 2 found no `compute_role_arn` on `CfnApp`:** remove that argument and attach the role with a custom resource after the app:
```python
        from aws_cdk import custom_resources as cr
        cr.AwsCustomResource(self, "AttachComputeRole",
            on_update=cr.AwsSdkCall(service="Amplify", action="updateApp",
                                    parameters={"appId": app.attr_app_id, "computeRoleArn": role.role_arn},
                                    physical_resource_id=cr.PhysicalResourceId.of(f"{PREFIX}-web-compute")),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(actions=["amplify:UpdateApp"], resources=[app.attr_arn]),
                iam.PolicyStatement(actions=["iam:PassRole"], resources=[role.role_arn])]))
```
and in `test_web.py`, replace the `"ComputeRoleArn" in p` assertion with a check that one `Custom::AWS` resource's `Update` payload contains `computeRoleArn`.

In `infra/lb_infra/assembly.py`, add `from lb_infra.stacks.web import WebStack`, then:
```python
    web = WebStack(app, "LbDemo-Web", cfg=cfg, data=data, identity=identity, agent=agent, realtime=realtime, env=env)
```
and add `"web": web` to the returned dict.

- [ ] **Step 4: The web additions**

`web/lib/trace/xray.ts`:
```ts
// Link from a trace block to its CloudWatch X-Ray trace (deployment spec §6.1). Only well-formed X-Ray ids pass,
// so a record can never inject an arbitrary URL.
const XRAY_ID = /^1-[0-9a-f]{8}-[0-9a-f]{24}$/;

export function xrayTraceUrl(traceId: string, region = "us-east-2"): string | null {
  if (!XRAY_ID.test(traceId)) return null;
  return `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}#xray:traces/${traceId}`;
}
```

In `web/lib/server/records.ts`, in `interface DecisionRecord`, add the field `trace_id?: string;` after `latency_ms?: number;`.

In `web/lib/trace/viewModel.ts`:
- add `import { xrayTraceUrl } from "./xray";`;
- in `interface TraceTurn`, add `traceUrl?: string;` after the `versions` line;
- in `buildTurn`, directly before its `return {`, add:
```ts
  const traced = recs.find((r) => typeof r.trace_id === "string" && r.trace_id);
  const traceUrl = traced?.trace_id ? xrayTraceUrl(traced.trace_id) : null;
```
- and add as the last property of the returned object:
```ts
    ...(traceUrl ? { traceUrl } : {}),
```

In `web/components/trace/TraceTurn.tsx`, in `TraceTurnView`'s returned JSX, directly after the `{strip}` element, add:
```tsx
      {turn.traceUrl ? (
        <a href={turn.traceUrl} target="_blank" rel="noreferrer"
          className="inline-block mt-1 text-[11px] text-c-signal underline underline-offset-2">CloudWatch trace ↗</a>
      ) : null}
```

`web/components/staff/BuildTag.tsx`:
```tsx
// Build traceability on staff pages (deployment spec §5.2): the deployed commit, from NEXT_PUBLIC_GIT_SHA.
export function BuildTag() {
  const sha = process.env.NEXT_PUBLIC_GIT_SHA;
  if (!sha) return null;
  return <footer className="px-4 py-2 text-[11px] text-c-muted tabular-nums">build {sha.slice(0, 7)}</footer>;
}
```

`web/app/agent/layout.tsx`, `web/app/trace/layout.tsx` and `web/app/demo/layout.tsx` (the same content in each). If a layout already exists at one of these paths, add `<BuildTag />` after `{children}` instead:
```tsx
import { BuildTag } from "@/components/staff/BuildTag";

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <BuildTag />
    </>
  );
}
```

In `amplify.yml`, add directly after the `env | grep -E …` line:
```yaml
            - echo "NEXT_PUBLIC_GIT_SHA=${AWS_COMMIT_ID:-unknown}" >> .env.production
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_web.py -v`
Expected: 3 passed.
Run: `cd ../web && npm test && npx tsc --noEmit; cd ../infra`
Expected: all Vitest suites pass (including the existing trace view-model tests, unchanged), and no type errors.

- [ ] **Step 6: Commit**

```bash
cd .. && git add infra/lb_infra/stacks/web.py infra/lb_infra/assembly.py infra/tests/test_web.py amplify.yml web/lib/trace/xray.ts web/lib/trace/viewModel.ts web/lib/server/records.ts web/components/trace/TraceTurn.tsx web/components/staff/BuildTag.tsx web/app/agent/layout.tsx web/app/trace/layout.tsx web/app/demo/layout.tsx web/tests/unit/xray.test.ts
git commit -m "feat(infra,web): LbDemo-Web Amplify stack; trace links to X-Ray and a build tag on staff pages

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: `LbDemo-Ops`: alarms and the dashboard

**Scope limits:** CloudWatch alarms, the composite alarm and one dashboard. No SNS topic and no alarm actions.

**Check when done:** `uv run pytest tests/test_ops.py -v` passes.

**Files:**
- Create: `infra/lb_infra/stacks/ops.py`
- Modify: `infra/lb_infra/assembly.py`
- Test: `infra/tests/test_ops.py`

**Interfaces:**
- Consumes:
  - the metrics from Task 3 (namespace `LatamBank`: `TurnLatencyMs`, `TurnCount{Route}`, `HandoffCount{Priority}`, `JevErrorCount`, `JevLatencyMs`, `LlmErrorCount{Role}`, `LlmLatencyMs{Role}`, `TemplateFallbackCount`, `InjectionBlockedCount`, each also with `Language`);
  - `DataStack.tables`, `IdentityStack.api` and `.fn`, `RealtimeStack.dlq`, `.publisher` and `.api`, `WebStack.app_id`.
- Produces:
  - `OpsStack.alarms: list[cw.Alarm]` (14);
  - `OpsStack.composite`;
  - `OpsStack.rows: tuple[str, ...]`;
  - the `build_all` key `ops`.

- [ ] **Step 1: Write the failing tests**

`infra/tests/test_ops.py`:
```python
import json

TABLES = ("checkpoints", "disputes", "handoffs", "decision_records", "sessions", "conversation_messages")
EXPECTED = {"lb-demo-turn-latency", "lb-demo-safe-fallback-rate", "lb-demo-jev-failing", "lb-demo-bedrock-failing",
            "lb-demo-realtime-dlq", "lb-demo-publisher-lag", "lb-demo-identity-errors", "lb-demo-web-5xx",
            *{f"lb-demo-ddb-throttle-{t}" for t in TABLES}}


def alarms(templates):
    return {a["Properties"]["AlarmName"]: a["Properties"]
            for a in templates["ops"].find_resources("AWS::CloudWatch::Alarm").values()}


def test_every_alarm_exists_quietly(templates):
    found = alarms(templates)
    assert set(found) == EXPECTED
    for props in found.values():
        assert props["TreatMissingData"] == "notBreaching"
        assert props.get("ActionsEnabled") is False and not props.get("AlarmActions")


def test_thresholds(templates):
    a = alarms(templates)
    lat = a["lb-demo-turn-latency"]
    assert (lat["ExtendedStatistic"], lat["Threshold"], lat["EvaluationPeriods"], lat["DatapointsToAlarm"]) == \
        ("p95", 15000, 5, 3)
    assert a["lb-demo-jev-failing"]["Threshold"] == 5
    assert a["lb-demo-jev-failing"]["ComparisonOperator"] == "GreaterThanOrEqualToThreshold"
    assert a["lb-demo-bedrock-failing"]["Threshold"] == 5
    assert a["lb-demo-safe-fallback-rate"]["Threshold"] == 20
    assert "IF(FILL(total,0) >= 5" in json.dumps(a["lb-demo-safe-fallback-rate"]["Metrics"])
    assert a["lb-demo-realtime-dlq"]["Threshold"] == 0
    assert a["lb-demo-publisher-lag"]["Threshold"] == 60000
    assert a["lb-demo-identity-errors"]["Threshold"] == 3 and a["lb-demo-web-5xx"]["Threshold"] == 5


def test_composite_covers_all_alarms_without_actions(templates):
    (c,) = templates["ops"].find_resources("AWS::CloudWatch::CompositeAlarm").values()
    p = c["Properties"]
    assert p["AlarmName"] == "lb-demo-DemoUnhealthy" and p.get("ActionsEnabled") is False
    assert json.dumps(p["AlarmRule"]).count("ALARM(") == len(EXPECTED)


def test_dashboard_has_five_rows_and_no_sns_anywhere(stacks, templates):
    templates["ops"].has_resource_properties("AWS::CloudWatch::Dashboard", {"DashboardName": "lb-demo-ops"})
    assert stacks["ops"].rows == ("Outcomes", "Latency", "Dependencies", "Realtime", "Platform")
    for t in templates.values():
        assert t.find_resources("AWS::SNS::Topic") == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ops.py -v`
Expected: FAIL (`KeyError: 'ops'`).

- [ ] **Step 3: Write the stack**

`infra/lb_infra/stacks/ops.py`:
```python
"""LbDemo-Ops (deployment spec §6.3–6.4): alarms sized for demo traffic and the lb-demo-ops dashboard.
No notifications: alarm state is read from the dashboard's status widget and the DemoUnhealthy composite."""
from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudwatch as cw

from lb_infra.config import PREFIX

NS = "LatamBank"
GT = cw.ComparisonOperator.GREATER_THAN_THRESHOLD
GTE = cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
ROUTES = ("act", "clarify", "abstain", "handoff", "safe_fallback")
LANGS = ("es", "pt")


def m(name: str, stat: str, dims: dict | None = None, minutes: int = 1, label: str | None = None) -> cw.Metric:
    return cw.Metric(namespace=NS, metric_name=name, dimensions_map=dims or {}, statistic=stat,
                     period=Duration.minutes(minutes), label=label)


class OpsStack(Stack):
    rows = ("Outcomes", "Latency", "Dependencies", "Realtime", "Platform")

    def __init__(self, scope, cid: str, *, data, identity, realtime, web, **kw):
        super().__init__(scope, cid, **kw)
        self.alarms: list[cw.Alarm] = []
        five = Duration.minutes(5)
        self._alarm("turn-latency", "Turn p95 latency > 15 s in 3 of 5 minutes", m("TurnLatencyMs", "p95"), 15000, GT,
                    periods=5, datapoints=3)
        self._alarm("safe-fallback-rate", "Safe-fallback share > 20% over 10 minutes (at least 5 turns)",
                    cw.MathExpression(expression="IF(FILL(total,0) >= 5, 100 * FILL(fb,0) / FILL(total,1), 0)",
                                      using_metrics={"fb": m("TurnCount", "Sum", {"Route": "safe_fallback"}, 10),
                                                     "total": m("TurnCount", "Sum", None, 10)},
                                      period=Duration.minutes(10)), 20, GT)
        self._alarm("jev-failing", "Jev errors >= 5 in 5 minutes", m("JevErrorCount", "Sum", None, 5), 5, GTE)
        self._alarm("bedrock-failing", "Bedrock errors >= 5 in 5 minutes", m("LlmErrorCount", "Sum", None, 5), 5, GTE)
        self._alarm("realtime-dlq", "Realtime publisher records in the DLQ",
                    realtime.dlq.metric_approximate_number_of_messages_visible(period=Duration.minutes(1),
                                                                               statistic="Maximum"), 0, GT)
        self._alarm("publisher-lag", "Publisher stream iterator age > 60 s",
                    realtime.publisher.metric("IteratorAge", statistic="Maximum", period=Duration.minutes(1)), 60000, GT)
        for name, table in data.tables.items():
            self._alarm(f"ddb-throttle-{name}", f"DynamoDB throttling on {table.node.id}",
                        cw.MathExpression(expression="FILL(r,0) + FILL(w,0)", period=Duration.minutes(1), using_metrics={
                            "r": table.metric("ReadThrottleEvents", statistic="Sum", period=Duration.minutes(1)),
                            "w": table.metric("WriteThrottleEvents", statistic="Sum", period=Duration.minutes(1))}),
                        0, GT)
        self._alarm("identity-errors", "Identity HTTP API 5xx + Lambda errors >= 3 in 5 minutes",
                    cw.MathExpression(expression="FILL(api,0) + FILL(fn,0)", period=five, using_metrics={
                        "api": identity.api.metric_server_error(period=five, statistic="Sum"),
                        "fn": identity.fn.metric_errors(period=five, statistic="Sum")}), 3, GTE)
        amplify_5xx = cw.Metric(namespace="AWS/AmplifyHosting", metric_name="5xxErrors",
                                dimensions_map={"App": web.app_id}, statistic="Sum", period=five)
        self._alarm("web-5xx", "Amplify 5xx >= 5 in 5 minutes", amplify_5xx, 5, GTE)
        self.composite = cw.CompositeAlarm(self, "DemoUnhealthy", composite_alarm_name=f"{PREFIX}-DemoUnhealthy",
                                           alarm_rule=cw.AlarmRule.any_of(*self.alarms), actions_enabled=False,
                                           alarm_description="Any lb-demo alarm is in ALARM. Check before a demo.")
        self._dashboard(data, identity, realtime, amplify_5xx)

    def _alarm(self, name, description, metric, threshold, op, periods=1, datapoints=1) -> cw.Alarm:
        alarm = cw.Alarm(self, f"Alarm-{name}", alarm_name=f"{PREFIX}-{name}", alarm_description=description,
                         metric=metric, threshold=threshold, comparison_operator=op, evaluation_periods=periods,
                         datapoints_to_alarm=datapoints, treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
                         actions_enabled=False)
        self.alarms.append(alarm)
        return alarm

    def _dashboard(self, data, identity, realtime, amplify_5xx) -> None:
        d = cw.Dashboard(self, "Dashboard", dashboard_name=f"{PREFIX}-ops", default_interval=Duration.hours(3))
        g = lambda title, left, right=None, stacked=False: cw.GraphWidget(  # noqa: E731
            title=title, left=left, right=right or [], stacked=stacked, width=8, height=6)
        by_lang = lambda name, stat: [m(name, stat, {"Language": l}, 5, l) for l in LANGS]  # noqa: E731
        tables = data.tables.values()
        widgets = {
            "Outcomes": [
                g("Turns by route", [m("TurnCount", "Sum", {"Route": r}, 5, r) for r in ROUTES], stacked=True),
                g("Handoffs by priority", [m("HandoffCount", "Sum", {"Priority": p}, 5, p)
                                           for p in ("critical", "high", "medium")], stacked=True),
                g("Turns (left) and injection blocks (right) by language", by_lang("TurnCount", "Sum"),
                  by_lang("InjectionBlockedCount", "Sum"))],
            "Latency": [
                g("Turn latency", [m("TurnLatencyMs", "p50", None, 5, "p50"), m("TurnLatencyMs", "p95", None, 5, "p95")]),
                g("Jev p95", [m("JevLatencyMs", "p95", None, 5, "p95")]),
                g("Bedrock p95 by role", [m("LlmLatencyMs", "p95", {"Role": r}, 5, r) for r in ("extract", "compose")])],
            "Dependencies": [
                g("Jev and Bedrock errors", [m("JevErrorCount", "Sum", None, 5, "Jev"),
                                             m("LlmErrorCount", "Sum", None, 5, "Bedrock")]),
                g("Template fallbacks by language", by_lang("TemplateFallbackCount", "Sum")),
                g("Safe fallbacks", [m("TurnCount", "Sum", {"Route": "safe_fallback"}, 5, "safe_fallback")])],
            "Realtime": [
                g("Publisher", [realtime.publisher.metric_invocations(), realtime.publisher.metric_errors()]),
                g("Iterator age and DLQ depth", [realtime.publisher.metric("IteratorAge", statistic="Maximum")],
                  [realtime.dlq.metric_approximate_number_of_messages_visible()]),
                g("AppSync connections", [cw.Metric(namespace="AWS/AppSync", metric_name="ConnectSuccess",
                                                    dimensions_map={"ApiId": realtime.api.api_id}, statistic="Sum")])],
            "Platform": [
                g("Identity 4xx / 5xx", [identity.api.metric_client_error(), identity.api.metric_server_error()]),
                g("DynamoDB throttles (left) and consumed RCU (right)",
                  [t.metric("ReadThrottleEvents", statistic="Sum", label=t.node.id) for t in tables],
                  [t.metric_consumed_read_capacity_units(label=t.node.id) for t in tables]),
                g("Amplify requests and 5xx", [cw.Metric(namespace="AWS/AmplifyHosting", metric_name="Requests",
                                                         dimensions_map=amplify_5xx.dimensions, statistic="Sum"),
                                               amplify_5xx]),
                cw.AlarmStatusWidget(title="Alarms", alarms=[*self.alarms, self.composite], width=24, height=6)],
        }
        for row in self.rows:
            d.add_widgets(cw.TextWidget(markdown=f"## {row}", width=24, height=1))
            d.add_widgets(*widgets[row])
```

In `infra/lb_infra/assembly.py`, add `from lb_infra.stacks.ops import OpsStack`, then:
```python
    ops = OpsStack(app, "LbDemo-Ops", data=data, identity=identity, realtime=realtime, web=web, env=env)
```
after the web line, and add `"ops": ops` to the returned dict.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ops.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd .. && git add infra/lb_infra/stacks/ops.py infra/lb_infra/assembly.py infra/tests/test_ops.py
git commit -m "feat(infra): LbDemo-Ops alarms, DemoUnhealthy composite and the lb-demo-ops dashboard

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Cross-stack checks: IAM wildcards, log retention, cdk-nag clean

**Scope limits:** tests over all stacks, plus the fixes or written suppressions they force. No new resources.

**Check when done:** `uv run pytest -q` passes (every infra test), and `npx aws-cdk@2 synth -q` prints no cdk-nag errors.

**Files:**
- Test: `infra/tests/test_iam.py`, `infra/tests/test_nag.py`
- Modify (only if the tests require): `infra/lb_infra/nag.py` (`REASONS`) and the stack files' `nag.suppress(...)` lists

**Interfaces:**
- Consumes: `build_all`, `nag.apply`, and the `stacks`/`templates` fixtures.
- Produces: `STAR_OK: dict[str, str]`, the allow-list with reasons that spec §4.2 refers to.

- [ ] **Step 1: Write the tests**

`infra/tests/test_iam.py`:
```python
STAR_OK = {
    "xray:PutTraceSegments": "X-Ray write APIs accept only '*'",
    "xray:PutTelemetryRecords": "X-Ray write APIs accept only '*'",
    "xray:GetSamplingRules": "X-Ray sampling APIs accept only '*'",
    "xray:GetSamplingTargets": "X-Ray sampling APIs accept only '*'",
    "cloudwatch:PutMetricData": "no resource ARNs; limited by the cloudwatch:namespace condition",
    "ecr:GetAuthorizationToken": "account-level registry token; no resource ARN",
    "logs:PutRetentionPolicy": "CDK LogRetention provider sets the 30-day retention",
    "logs:DeleteRetentionPolicy": "CDK LogRetention provider sets the 30-day retention",
    "dynamodb:ListStreams": "account-level API; CDK adds it for DynamoDB stream event sources",
}


def as_list(x):
    return x if isinstance(x, list) else [x]


def all_statements(templates):
    for key, t in templates.items():
        for res in t.find_resources("AWS::IAM::Policy").values():
            for s in res["Properties"]["PolicyDocument"]["Statement"]:
                yield key, s
        for res in t.find_resources("AWS::IAM::Role").values():
            for pol in res["Properties"].get("Policies", []):
                for s in pol["PolicyDocument"]["Statement"]:
                    yield key, s


def test_no_service_wide_actions(templates):
    for key, s in all_statements(templates):
        for action in as_list(s["Action"]):
            assert action != "*" and not action.endswith(":*"), f"{key}: {action}"


def test_star_resource_only_for_allow_listed_actions(templates):
    for key, s in all_statements(templates):
        if "*" in as_list(s.get("Resource", [])):
            extra = set(as_list(s["Action"])) - STAR_OK.keys()
            assert not extra, f"{key}: Resource '*' with {sorted(extra)}"


def test_every_log_group_keeps_30_days(templates):
    for key, t in templates.items():
        for res in t.find_resources("AWS::Logs::LogGroup").values():
            assert res["Properties"].get("RetentionInDays") == 30, key
        for res in t.find_resources("Custom::LogRetention").values():
            assert str(res["Properties"]["RetentionInDays"]) == "30", key
```

`infra/tests/test_nag.py`:
```python
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match

from lb_infra import nag
from lb_infra.assembly import build_all
from tests.conftest import CFG, ENV


@pytest.fixture(scope="module")
def nagged():
    app = cdk.App()
    stacks = build_all(app, CFG, ENV)
    nag.apply(app)
    app.synth()
    return stacks


def test_no_unsuppressed_cdk_nag_errors(nagged):
    problems = []
    for key, stack in nagged.items():
        for e in Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*")):
            problems.append(f"{key}: {e.entry.data}")
    assert not problems, "\n".join(problems)


def test_every_suppression_has_a_reason():
    assert all(len(reason) > 20 for reason in nag.REASONS.values())
```

- [ ] **Step 2: Run them and fix what they find**

Run: `uv run pytest tests/test_iam.py tests/test_nag.py -v`
For each failure, choose exactly one of these:
- **Fix the resource** when the finding is real: a missing `enforce_ssl`, an over-broad action, or a log group without retention. Edit the stack that owns it.
- **Suppress it with a reason** when it's by design. Add an entry to `nag.REASONS` (one sentence, saying why it's acceptable for this prototype, or which remaining-work item in spec §9 covers it), and add its id to that stack's `nag.suppress([...])` list.
- **For a `Resource: "*"` failure in `test_iam.py`:** add the action to `STAR_OK` **only** if AWS documents that action as resource-less. Otherwise scope the resource.

Run again: `uv run pytest -q`
Expected: every infra test passes.
Run: `npx aws-cdk@2 synth -q 2>&1 | grep -c "AwsSolutions-.*Error"`
Expected: `0`.

- [ ] **Step 3: Commit**

```bash
cd .. && git add infra/tests/test_iam.py infra/tests/test_nag.py infra/lb_infra
git commit -m "test(infra): IAM wildcard allow-list, 30-day log retention and a clean cdk-nag run

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Phase D: bootstrap and delivery

### Task 12: Bootstrap: GitHub OIDC stack, `bootstrap.sh` and `seed_demo.py`

**Scope limits:** the one-time account setup and the demo-identities upload. The scripts are written and tested here; they're **run** in Task 14.

**Check when done:** `uv run pytest tests/test_github.py -v` (in `infra/`) and `uv run pytest tests/test_seed_demo.py -v` (in `agent/`) pass, and `bash -n infra/bootstrap.sh` reports no syntax errors.

**Files:**
- Create: `infra/lb_infra/stacks/github.py`, `infra/bootstrap.sh`, `agent/scripts/seed_demo.py`
- Modify: `infra/app.py`
- Test: `infra/tests/test_github.py`, `agent/tests/test_seed_demo.py`

**Interfaces:**
- Consumes: `Config`; the CDK bootstrap qualifier `hnb659fds` (the default); `load_users` (agent-core Task 3); `ServingData(base_uri, region).pointer()` and `.query(run_id, table, where, params)` (agent-core Task 5); `TABLE_SPECS`, `table_name`.
- Produces:
  - `GitHubStack` with outputs `DeployRoleArn` and `DiffRoleArn`, synthesized only with `-c bootstrap=1`;
  - the repository variables `AWS_DEPLOY_ROLE_ARN` and `AWS_DIFF_ROLE_ARN`;
  - `seed_demo.check_label(text) -> None`;
  - `seed_demo.missing_customers(users, has_customer) -> list[str]`;
  - `seed_demo.main(argv) -> int`.

- [ ] **Step 1: Write the failing tests**

`infra/tests/test_github.py`:
```python
import json

import aws_cdk as cdk
from aws_cdk.assertions import Template

from lb_infra.stacks.github import GitHubStack
from tests.conftest import CFG, ENV


def template(provider_arn=None):
    return Template.from_stack(GitHubStack(cdk.App(), "LbDemo-GitHub", cfg=CFG, provider_arn=provider_arn, env=ENV))


def roles(t):
    return {r["Properties"]["RoleName"]: r["Properties"] for r in t.find_resources("AWS::IAM::Role").values()}


def test_deploy_role_trusts_only_main_of_this_repo():
    deploy = roles(template())["lb-demo-github-deploy"]
    cond = deploy["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]["StringEquals"]
    assert cond["token.actions.githubusercontent.com:sub"] == "repo:example-org/example-repo:ref:refs/heads/main"
    assert cond["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"


def test_diff_role_trusts_pull_requests_and_can_only_assume_the_lookup_role():
    t = template()
    diff = roles(t)["lb-demo-github-diff"]
    cond = diff["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]["StringEquals"]
    assert cond["token.actions.githubusercontent.com:sub"] == "repo:example-org/example-repo:pull_request"
    text = json.dumps(t.find_resources("AWS::IAM::Policy"))
    assert "cdk-hnb659fds-lookup-role-111111111111-us-east-2" in text


def test_deploy_role_assumes_cdk_roles_and_reads_release_status():
    text = json.dumps(template().find_resources("AWS::IAM::Policy"))
    assert "cdk-hnb659fds-*-111111111111-us-east-2" in text
    for action in ("amplify:StartJob", "amplify:GetJob", "bedrock-agentcore:GetAgentRuntime",
                   "bedrock-agentcore:GetAgentRuntimeEndpoint"):
        assert action in text


def test_existing_oidc_provider_is_reused():
    assert template("arn:aws:iam::111111111111:oidc-provider/token.actions.githubusercontent.com"
                    ).find_resources("Custom::AWSCDKOpenIdConnectProvider") == {}
    assert len(template().find_resources("Custom::AWSCDKOpenIdConnectProvider")) == 1
```

`agent/tests/test_seed_demo.py`:
```python
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("seed_demo", Path(__file__).parents[1] / "scripts" / "seed_demo.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


class U:
    def __init__(self, customer_id, role="customer"):
        self.customer_id, self.role = customer_id, role


def test_label_header_required():
    seed.check_label("# LABELED TEST identities for the mock identity service\nusers: []\n")
    with pytest.raises(SystemExit, match="LABELED TEST"):
        seed.check_label("users: []\n")


def test_missing_customers_skips_staff_and_reports_unknown_ids():
    users = {"a": U("CLI-1"), "b": U("CLI-2"), "staff": U(None, role="agent")}
    assert seed.missing_customers(users, lambda cid: cid == "CLI-1") == ["CLI-2"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd infra && uv run pytest tests/test_github.py -v; cd ../agent && uv run pytest tests/test_seed_demo.py -v; cd ..`
Expected: both FAIL (missing modules).

- [ ] **Step 3: Write the GitHub stack**

`infra/lb_infra/stacks/github.py`:
```python
"""LbDemo-GitHub (deployment spec §5.4 step 3): OIDC trust for GitHub Actions. No stored AWS keys anywhere.
- deploy role: push to main only. Assumes the CDK bootstrap roles, starts the Amplify release and reads the
  runtime status for `verify`.
- diff role: pull requests. Assumes only the CDK lookup role (read-only), for `cdk diff`.
Deployed only by infra/bootstrap.sh (`-c bootstrap=1`), never by deploy.yml."""
from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_iam as iam

from lb_infra.config import PREFIX, Config

TOKEN = "token.actions.githubusercontent.com"


class GitHubStack(Stack):
    def __init__(self, scope, cid: str, *, cfg: Config, provider_arn: str | None, **kw):
        super().__init__(scope, cid, **kw)
        acct, region = self.account, self.region
        provider = (iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(self, "Oidc", provider_arn)
                    if provider_arn else
                    iam.OpenIdConnectProvider(self, "Oidc", url=f"https://{TOKEN}", client_ids=["sts.amazonaws.com"]))

        def principal(sub: str) -> iam.OpenIdConnectPrincipal:
            return iam.OpenIdConnectPrincipal(provider, conditions={"StringEquals": {
                f"{TOKEN}:aud": "sts.amazonaws.com", f"{TOKEN}:sub": sub}})

        deploy = iam.Role(self, "Deploy", role_name=f"{PREFIX}-github-deploy", max_session_duration=Duration.hours(1),
                          assumed_by=principal(f"repo:{cfg.github_repo}:ref:refs/heads/main"))
        deploy.add_to_policy(iam.PolicyStatement(actions=["sts:AssumeRole"],
                                                 resources=[f"arn:aws:iam::{acct}:role/cdk-hnb659fds-*-{acct}-{region}"]))
        deploy.add_to_policy(iam.PolicyStatement(actions=["amplify:StartJob", "amplify:GetJob"],
                                                 resources=[f"arn:aws:amplify:{region}:{acct}:apps/*/branches/main/jobs/*",
                                                            f"arn:aws:amplify:{region}:{acct}:apps/*/branches/main"]))
        deploy.add_to_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:GetAgentRuntime", "bedrock-agentcore:GetAgentRuntimeEndpoint"],
            resources=[f"arn:aws:bedrock-agentcore:{region}:{acct}:runtime/*"]))

        diff = iam.Role(self, "Diff", role_name=f"{PREFIX}-github-diff", max_session_duration=Duration.hours(1),
                        assumed_by=principal(f"repo:{cfg.github_repo}:pull_request"))
        diff.add_to_policy(iam.PolicyStatement(
            actions=["sts:AssumeRole"], resources=[f"arn:aws:iam::{acct}:role/cdk-hnb659fds-lookup-role-{acct}-{region}"]))

        CfnOutput(self, "DeployRoleArn", value=deploy.role_arn)
        CfnOutput(self, "DiffRoleArn", value=diff.role_arn)
```

In `infra/app.py`, add `from lb_infra.stacks.github import GitHubStack`, and after `build_all(app, cfg, env)` add:
```python
if app.node.try_get_context("bootstrap") == "1":  # only infra/bootstrap.sh deploys this stack
    GitHubStack(app, "LbDemo-GitHub", cfg=cfg, provider_arn=app.node.try_get_context("githubOidcProviderArn"), env=env)
```

- [ ] **Step 4: Write `bootstrap.sh`**

`infra/bootstrap.sh`:
```bash
#!/usr/bin/env bash
# One-time setup of the demo account (deployment spec §5.4). Run from infra/ with admin credentials, after
# `npm ci` in infra/realtime and `uv sync` here:   AWS_PROFILE=<admin> ./bootstrap.sh
# Re-runnable: every step checks before it creates. Secret values are read silently, piped over stdin and never echoed.
set -euo pipefail
cd "$(dirname "$0")"
REGION=us-east-2
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REPO="$(python3 -c "import json; print(json.load(open('cdk.json'))['context']['githubRepo'])")"
BUCKET="$(python3 -c "import json; print(json.load(open('cdk.json'))['context']['servingBucket'])")"
say() { printf '\n== %s\n' "$*"; }
out() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]][sys.argv[3]])" "$@"; }

say "1/8 CDK bootstrap aws://$ACCOUNT/$REGION"
npx aws-cdk@2 bootstrap "aws://$ACCOUNT/$REGION"

say "2/8 CloudWatch Transaction Search (spans for AgentCore Observability)"
if [ "$(aws xray get-trace-segment-destination --region "$REGION" --query Destination --output text)" != "CloudWatchLogs" ]; then
  aws logs put-resource-policy --region "$REGION" --policy-name lb-demo-transaction-search --policy-document \
    "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"TransactionSearchXRayAccess\",\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"xray.amazonaws.com\"},\"Action\":\"logs:PutLogEvents\",\"Resource\":[\"arn:aws:logs:$REGION:$ACCOUNT:log-group:aws/spans:*\",\"arn:aws:logs:$REGION:$ACCOUNT:log-group:/aws/application-signals/data:*\"],\"Condition\":{\"ArnLike\":{\"aws:SourceArn\":\"arn:aws:xray:$REGION:$ACCOUNT:*\"},\"StringEquals\":{\"aws:SourceAccount\":\"$ACCOUNT\"}}}]}" >/dev/null
  aws xray update-trace-segment-destination --region "$REGION" --destination CloudWatchLogs >/dev/null
fi
echo "trace destination: $(aws xray get-trace-segment-destination --region "$REGION" --query Destination --output text)"

say "3/8 GitHub OIDC roles (LbDemo-GitHub) and repository variables"
PROVIDER="$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn | [0]" --output text)"
CTX=(-c bootstrap=1)
if [ "$PROVIDER" != "None" ]; then CTX+=(-c "githubOidcProviderArn=$PROVIDER"); fi
npx aws-cdk@2 deploy LbDemo-GitHub "${CTX[@]}" --require-approval never --outputs-file github-outputs.json
gh variable set AWS_DEPLOY_ROLE_ARN --repo "$REPO" --body "$(out github-outputs.json LbDemo-GitHub DeployRoleArn)"
gh variable set AWS_DIFF_ROLE_ARN --repo "$REPO" --body "$(out github-outputs.json LbDemo-GitHub DiffRoleArn)"

say "4/8 Secrets (existing secrets are kept, never overwritten)"
put_secret() {
  local name="$1" prompt="$2" value
  if aws secretsmanager describe-secret --region "$REGION" --secret-id "$name" >/dev/null 2>&1; then echo "$name: exists, kept"; return; fi
  if [ "$name" = "lb-demo/idp-signing-key" ]; then
    value="$(openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 2>/dev/null)"
  else
    read -r -s -p "$prompt: " value; echo
  fi
  printf '%s' "$value" | aws secretsmanager create-secret --region "$REGION" --name "$name" \
    --secret-string file:///dev/stdin --query Name --output text
  unset value
}
put_secret lb-demo/jev "TypeSafe (Jev) API key"
put_secret lb-demo/idp-signing-key "(generated)"
put_secret lb-demo/amplify-github-token "GitHub fine-grained token for $REPO only (Contents: read, Webhooks: read/write)"

say "5/8 First deploy of all stacks"
npx aws-cdk@2 deploy --all --require-approval never -c "gitSha=$(git rev-parse HEAD)" --outputs-file cdk-outputs.json

say "6/8 Demo identities → s3://$BUCKET/identity/demo_users.yaml"
(cd ../agent && uv run python scripts/seed_demo.py --bucket "$BUCKET")

say "7/8 Snowflake still reaches the serving bucket (pipeline plan Task 2)"
echo "In Snowsight run: LIST @LATAM_BANK.RAW.SERVING_STAGE;  (expect the run folders, no access error)"
read -r -p "Press Enter when checked... " _

say "8/8 Web build and health check"
./scripts/amplify_release.sh "$(out cdk-outputs.json LbDemo-Web AppId)"
uv run python scripts/verify.py --outputs cdk-outputs.json --sha "$(git rev-parse HEAD)"
echo "Bootstrap complete. From now on every push to main deploys through .github/workflows/deploy.yml."
```
Run: `chmod +x infra/bootstrap.sh && bash -n infra/bootstrap.sh && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

- [ ] **Step 5: Write `seed_demo.py`**

`agent/scripts/seed_demo.py`:
```python
"""Upload the LABELED TEST demo identities to the serving bucket and check the deployed tables
(deployment spec §5.4 step 7). The file names dataset customer ids, so it never enters git or an image.
uv run python scripts/seed_demo.py --bucket <serving bucket> [--users config/demo_users.yaml] [--prefix lb-demo]
Writes one S3 object: run only with the owner's approval."""
import argparse
import sys
from pathlib import Path

import boto3

from bankagent.data.serving import ServingData
from bankagent.identity.users import load_users
from bankagent.store.tables import TABLE_SPECS, table_name

KEY = "identity/demo_users.yaml"


def check_label(text: str) -> None:
    first = text.splitlines()[0] if text else ""
    if "LABELED TEST" not in first:
        raise SystemExit("demo_users.yaml must start with its '# LABELED TEST identities' header line")


def missing_customers(users: dict, has_customer) -> list[str]:
    ids = sorted({u.customer_id for u in users.values() if getattr(u, "role", "customer") != "agent" and u.customer_id})
    return [cid for cid in ids if not has_customer(cid)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--users", default="config/demo_users.yaml")
    ap.add_argument("--prefix", default="lb-demo")
    ap.add_argument("--region", default="us-east-2")
    a = ap.parse_args(argv)
    text = Path(a.users).read_text(encoding="utf-8")
    check_label(text)
    users = load_users(a.users)

    serving = ServingData(f"s3://{a.bucket}/serving", a.region)
    run_id = serving.pointer().run_id
    missing = missing_customers(users, lambda cid: bool(serving.query(run_id, "dim_product", "customer_id = ?", [cid])))
    if missing:
        print(f"FAIL: {len(missing)} demo customers are not in serving run {run_id}: {missing}")
        return 1

    ddb = boto3.client("dynamodb", region_name=a.region)
    for name in TABLE_SPECS:
        status = ddb.describe_table(TableName=table_name(a.prefix, name))["Table"]["TableStatus"]
        if status != "ACTIVE":
            print(f"FAIL: table {table_name(a.prefix, name)} is {status}")
            return 1
    for name in ("disputes", "handoffs"):
        n = ddb.scan(TableName=table_name(a.prefix, name), Select="COUNT")["Count"]
        print(f"{table_name(a.prefix, name)}: {n} items" + ("" if n == 0 else " (not empty: earlier demo runs)"))

    boto3.client("s3", region_name=a.region).put_object(Bucket=a.bucket, Key=KEY, Body=text.encode("utf-8"),
                                                        ServerSideEncryption="AES256")
    print(f"uploaded {len(users)} labeled identities to s3://{a.bucket}/{KEY} (serving run {run_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd infra && uv run pytest tests/test_github.py -v; cd ../agent && uv run pytest tests/test_seed_demo.py -v; cd ..`
Expected: 4 passed, then 2 passed.

- [ ] **Step 7: Commit**

```bash
git add infra/lb_infra/stacks/github.py infra/app.py infra/bootstrap.sh infra/tests/test_github.py agent/scripts/seed_demo.py agent/tests/test_seed_demo.py
git commit -m "feat(infra): GitHub OIDC roles, one-time bootstrap script and demo-identity seeding

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: CI/CD: reusable tests, PR diff with the stateful guard, deploy → web → verify

**Scope limits:** three workflow files, the guard, the release script and the verify script, with their tests. Nothing is pushed or run against AWS in this task.

**Check when done:** `uv run pytest tests/test_guard.py tests/test_verify.py tests/test_workflows.py -v` (in `infra/`) passes.

**Files:**
- Create: `.github/workflows/app-tests.yml`, `.github/workflows/app-ci.yml`, `.github/workflows/deploy.yml`, `infra/scripts/__init__.py`, `infra/scripts/stateful_guard.py`, `infra/scripts/verify.py`, `infra/scripts/amplify_release.sh`
- Test: `infra/tests/test_guard.py`, `infra/tests/test_verify.py`, `infra/tests/test_workflows.py`

**Interfaces:**
- Consumes: the stack names and outputs (`LbDemo-Identity.Issuer`, `LbDemo-Agent.RuntimeId`, `LbDemo-Web.AppId` and `.AppUrl`); the repository variables from Task 12.
- Produces:
  - `stateful_guard.findings(text, stack="LbDemo-Data") -> list[str]` and `main(argv) -> int`;
  - `verify.check_identity(issuer, fetch) -> list[str]`, `check_runtime(control, runtime_id, sha) -> list[str]`, `check_web(url, status) -> list[str]` and `main(argv, control=None, fetch=…, status=…) -> int`;
  - `amplify_release.sh <appId>`.

- [ ] **Step 1: Write the failing tests**

`infra/tests/test_guard.py`:
```python
from scripts.stateful_guard import findings, main

SAFE = """Stack LbDemo-Data
Resources
[~] AWS::DynamoDB::Table Table-handoffs TablehandoffsABC12345
 └─ [~] TimeToLiveSpecification
     └─ [+] Added: .Enabled

Stack LbDemo-Agent
Resources
[-] AWS::IAM::Policy Exec/DefaultPolicy ExecDefaultPolicyAB12 destroy
[~] AWS::BedrockAgentCore::Runtime Runtime Runtime replace
"""

REPLACE = """\x1b[1mStack LbDemo-Data\x1b[22m
\x1b[4mResources\x1b[24m
\x1b[33m[~]\x1b[39m AWS::DynamoDB::Table Table-disputes TabledisputesXYZ \x1b[31mreplace\x1b[39m
 └─ [~] KeySchema (requires replacement)
\x1b[31m[-]\x1b[39m AWS::DynamoDB::Table Table-sessions TablesessionsQRS destroy
Outputs
[-] Output ExportsOutputFoo: {"Value":"x"}
"""


def test_safe_diff_passes_even_when_other_stacks_replace_things():
    assert findings(SAFE) == []


def test_guard_flags_replacement_with_ansi_codes():
    found = findings(REPLACE)
    assert len(found) == 3
    assert any("Table-disputes" in f for f in found) and any("Table-sessions" in f for f in found)
    assert not any("Output" in f for f in found)


def test_main_exit_codes(tmp_path, capsys):
    (tmp_path / "safe.txt").write_text(SAFE)
    (tmp_path / "bad.txt").write_text(REPLACE)
    assert main([str(tmp_path / "safe.txt")]) == 0
    assert main([str(tmp_path / "bad.txt")]) == 1
    assert "Table-disputes" in capsys.readouterr().out
```

`infra/tests/test_verify.py`:
```python
import json

from scripts.verify import check_identity, check_runtime, check_web, main

ISS = "https://abc.execute-api.us-east-2.amazonaws.com"


def fetch_ok(url):
    if url.endswith("/openid-configuration"):
        return 200, {"issuer": ISS}
    return 200, {"keys": [{"kid": "lb-demo-1"}]}


class Control:
    def __init__(self, status="READY", sha="abc", live="3", version="3"):
        self.s, self.sha, self.live, self.version = status, sha, live, version

    def get_agent_runtime(self, agentRuntimeId):
        return {"status": self.s, "agentRuntimeVersion": self.version, "environmentVariables": {"GIT_SHA": self.sha}}

    def get_agent_runtime_endpoint(self, agentRuntimeId, endpointName):
        assert endpointName == "live"
        return {"liveVersion": self.live}


def test_identity_checks():
    assert check_identity(ISS, fetch_ok) == []
    assert check_identity(ISS, lambda u: (503, None))[0].startswith("discovery")
    two_keys = lambda u: (200, {"issuer": ISS}) if "openid" in u else (200, {"keys": [{}, {}]})  # noqa: E731
    assert check_identity(ISS, two_keys) == ["jwks: status 200, 2 keys (want 1)"]


def test_runtime_checks():
    assert check_runtime(Control(), "rt-1", "abc") == []
    errs = check_runtime(Control(status="UPDATING", sha="old", live="2"), "rt-1", "abc")
    assert len(errs) == 3


def test_web_check():
    assert check_web("https://main.d1.amplifyapp.com", lambda u: 200) == []
    assert check_web("https://main.d1.amplifyapp.com", lambda u: 500) == ["web /login: status 500"]


def test_main_reads_outputs_and_fails_on_any_problem(tmp_path, capsys):
    outputs = {"LbDemo-Identity": {"Issuer": ISS}, "LbDemo-Agent": {"RuntimeId": "rt-1"},
               "LbDemo-Web": {"AppUrl": "https://main.d1.amplifyapp.com", "AppId": "d1"}}
    f = tmp_path / "out.json"
    f.write_text(json.dumps(outputs))
    assert main(["--outputs", str(f), "--sha", "abc"], control=Control(), fetch=fetch_ok, status=lambda u: 200) == 0
    assert main(["--outputs", str(f), "--sha", "new"], control=Control(), fetch=fetch_ok, status=lambda u: 200) == 1
    assert "GIT_SHA" in capsys.readouterr().out
```

`infra/tests/test_workflows.py`:
```python
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def load(name):
    doc = yaml.safe_load((WF / name).read_text())
    doc["on"] = doc.get("on", doc.get(True))  # PyYAML reads the key `on` as True
    return doc


def test_deploy_jobs_are_chained_and_never_cancelled():
    d = load("deploy.yml")
    assert d["concurrency"] == {"group": "deploy-demo", "cancel-in-progress": False}
    jobs = d["jobs"]
    assert jobs["deploy"]["needs"] == "tests" and jobs["web"]["needs"] == "deploy" and jobs["verify"]["needs"] == "web"
    assert jobs["tests"]["uses"] == "./.github/workflows/app-tests.yml"
    assert d["on"]["push"]["branches"] == ["main"] and "docs/**" in d["on"]["push"]["paths-ignore"]


def test_deploy_runs_cdk_on_arm_with_the_commit_sha():
    deploy = load("deploy.yml")["jobs"]["deploy"]
    assert deploy["runs-on"] == "ubuntu-24.04-arm"
    run = " ".join(s.get("run", "") for s in deploy["steps"])
    assert "deploy --all --require-approval never" in run and "gitSha=${{ github.sha }}" in run


def test_every_aws_job_uses_oidc_and_no_stored_keys():
    for name in ("deploy.yml", "app-ci.yml"):
        text = (WF / name).read_text()
        assert "AWS_ACCESS_KEY_ID" not in text and "secrets." not in text
        for job in load(name)["jobs"].values():
            steps = job.get("steps", [])
            if any("configure-aws-credentials" in s.get("uses", "") for s in steps):
                assert job["permissions"]["id-token"] == "write"


def test_pr_workflow_diffs_with_the_read_only_role_then_guards():
    ci = load("app-ci.yml")
    assert "pull_request" in ci["on"]
    steps = ci["jobs"]["infra-diff"]["steps"]
    creds = [s for s in steps if "configure-aws-credentials" in s.get("uses", "")][0]
    assert creds["with"]["role-to-assume"] == "${{ vars.AWS_DIFF_ROLE_ARN }}"
    runs = [s.get("run", "") for s in steps]
    diff_i = next(i for i, r in enumerate(runs) if "diff --all --no-change-set" in r)
    guard_i = next(i for i, r in enumerate(runs) if "stateful_guard.py" in r)
    assert diff_i < guard_i


def test_tests_workflow_is_reusable_and_covers_all_four_suites():
    t = load("app-tests.yml")
    assert "workflow_call" in t["on"]
    assert set(t["jobs"]) == {"agent", "web", "realtime", "infra"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_guard.py tests/test_verify.py tests/test_workflows.py -v`
Expected: FAIL (missing modules and files).

- [ ] **Step 3: The guard, verify and release scripts**

`infra/scripts/__init__.py`: an empty file (so tests can `from scripts.… import …`).

`infra/scripts/stateful_guard.py`:
```python
"""Fail CI when `cdk diff` would replace or remove a resource in LbDemo-Data (deployment spec §7).
usage: python scripts/stateful_guard.py diff.txt [--stack LbDemo-Data]"""
import argparse
import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SECTIONS = {"Resources", "Outputs", "Parameters", "Conditions", "Other Changes", "IAM Statement Changes",
            "Security Group Changes"}


def findings(text: str, stack: str = "LbDemo-Data") -> list[str]:
    found, current, section = [], None, None
    for raw in text.splitlines():
        line = ANSI.sub("", raw).rstrip()
        s = line.strip()
        if s.startswith("Stack "):
            current, section = s.split()[1], None
            continue
        if s in SECTIONS:
            section = s
            continue
        if current != stack or section != "Resources":
            continue
        if (s.startswith("[-]") or "(requires replacement)" in s or "(may cause replacement)" in s
                or (s.startswith("[~]") and s.endswith(" replace"))):
            found.append(s)
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("diff")
    ap.add_argument("--stack", default="LbDemo-Data")
    a = ap.parse_args(argv)
    with open(a.diff, encoding="utf-8") as f:
        found = findings(f.read(), a.stack)
    for line in found:
        print(f"STATEFUL CHANGE in {a.stack}: {line}")
    print("stateful guard: OK" if not found else f"stateful guard: {len(found)} blocking change(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
```

`infra/scripts/verify.py`:
```python
"""Post-deploy health check (deployment spec §5.3). Not a functional smoke test: it calls no model.
usage: python scripts/verify.py --outputs cdk-outputs.json --sha <git sha>"""
import argparse
import json
import sys
import urllib.error
import urllib.request

import boto3


def fetch_json(url: str, timeout: int = 15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return 0, None


def fetch_status(url: str, timeout: int = 20) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, TimeoutError):
        return 0


def check_identity(issuer: str, fetch=fetch_json) -> list[str]:
    errs = []
    status, doc = fetch(f"{issuer}/.well-known/openid-configuration")
    if status != 200 or (doc or {}).get("issuer") != issuer:
        errs.append(f"discovery: status {status}, issuer {(doc or {}).get('issuer')!r}")
    status, jwks = fetch(f"{issuer}/jwks.json")
    n = len((jwks or {}).get("keys", []))
    if status != 200 or n != 1:
        errs.append(f"jwks: status {status}, {n} keys (want 1)")
    return errs


def check_runtime(control, runtime_id: str, sha: str, endpoint: str = "live") -> list[str]:
    errs = []
    rt = control.get_agent_runtime(agentRuntimeId=runtime_id)
    if rt.get("status") != "READY":
        errs.append(f"runtime status {rt.get('status')}")
    deployed = (rt.get("environmentVariables") or {}).get("GIT_SHA")
    if deployed != sha:
        errs.append(f"runtime GIT_SHA {deployed!r} != {sha!r}")
    ep = control.get_agent_runtime_endpoint(agentRuntimeId=runtime_id, endpointName=endpoint)
    if str(ep.get("liveVersion")) != str(rt.get("agentRuntimeVersion")):
        errs.append(f"endpoint {endpoint} serves version {ep.get('liveVersion')}, latest is {rt.get('agentRuntimeVersion')}")
    return errs


def check_web(url: str, status=fetch_status) -> list[str]:
    code = status(f"{url}/login")
    return [] if code == 200 else [f"web /login: status {code}"]


def main(argv=None, control=None, fetch=fetch_json, status=fetch_status) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--sha", required=True)
    a = ap.parse_args(argv)
    with open(a.outputs, encoding="utf-8") as f:
        out = json.load(f)
    control = control or boto3.client("bedrock-agentcore-control", region_name="us-east-2")
    errs = (check_identity(out["LbDemo-Identity"]["Issuer"], fetch)
            + check_runtime(control, out["LbDemo-Agent"]["RuntimeId"], a.sha)
            + check_web(out["LbDemo-Web"]["AppUrl"], status))
    for e in errs:
        print("FAIL", e)
    print("verify: OK" if not errs else f"verify: {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
```
Before relying on the field names, run: `aws bedrock-agentcore-control get-agent-runtime help | grep -n -E "status|agentRuntimeVersion|environmentVariables"` and `aws bedrock-agentcore-control get-agent-runtime-endpoint help | grep -n liveVersion`. If a name differs, change it in `check_runtime` and in the test's `Control` fake together.

`infra/scripts/amplify_release.sh`:
```bash
#!/usr/bin/env bash
# Start an Amplify RELEASE build of main and wait for it (deployment spec §5.1). usage: amplify_release.sh <appId>
set -euo pipefail
APP="$1"; REGION="${AWS_REGION:-us-east-2}"
JOB="$(aws amplify start-job --region "$REGION" --app-id "$APP" --branch-name main --job-type RELEASE \
  --query jobSummary.jobId --output text)"
echo "Amplify job $JOB started"
STATUS=PENDING
for _ in $(seq 1 90); do
  STATUS="$(aws amplify get-job --region "$REGION" --app-id "$APP" --branch-name main --job-id "$JOB" \
    --query job.summary.status --output text)"
  case "$STATUS" in
    SUCCEED) echo "Amplify job $JOB succeeded"; exit 0 ;;
    FAILED|CANCELLED) echo "Amplify job $JOB ended $STATUS"; exit 1 ;;
  esac
  sleep 20
done
echo "Amplify job $JOB still $STATUS after 30 minutes"; exit 1
```
Run: `chmod +x infra/scripts/amplify_release.sh && bash -n infra/scripts/amplify_release.sh && echo OK`
Expected: `OK`

- [ ] **Step 4: The workflows**

`.github/workflows/app-tests.yml`:
```yaml
# Offline test suites for the app (agent, web, realtime handlers, infra). Called by app-ci.yml and deploy.yml.
name: app-tests
on:
  workflow_call: {}
permissions:
  contents: read
jobs:
  agent:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: agent } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
      - run: uv run pytest -q
  web:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: web/package-lock.json }
      - run: npm ci
      - run: npm test
      - run: npx playwright install --with-deps chromium
      - run: npm run e2e
  realtime:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: infra/realtime } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: infra/realtime/package-lock.json }
      - run: npm ci
      - run: npm test
  infra:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: infra/realtime/package-lock.json }
      - uses: astral-sh/setup-uv@v6
      - run: npm ci
        working-directory: infra/realtime
      - run: uv sync --frozen
        working-directory: infra
      - run: uv run pytest -q
        working-directory: infra
      - run: npx aws-cdk@2 synth -q
        working-directory: infra
```

`.github/workflows/app-ci.yml`:
```yaml
# Pull requests: app tests, then `cdk diff` (read-only role) posted as a comment, then the stateful guard.
# The data pipeline keeps its own ci.yml.
name: app-ci
on:
  pull_request:
    paths-ignore: ["docs/**", "**/*.md"]
permissions:
  contents: read
concurrency:
  group: app-ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  tests:
    uses: ./.github/workflows/app-tests.yml
  infra-diff:
    needs: tests
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: infra/realtime/package-lock.json }
      - uses: astral-sh/setup-uv@v6
      - run: npm ci
        working-directory: infra/realtime
      - run: uv sync --frozen
        working-directory: infra
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_DIFF_ROLE_ARN }}
          aws-region: us-east-2
      - name: cdk diff
        working-directory: infra
        run: npx aws-cdk@2 diff --all --no-change-set -c gitSha=${{ github.sha }} 2>&1 | tee diff.txt
      - name: stateful guard
        working-directory: infra
        run: uv run python scripts/stateful_guard.py diff.txt
      - uses: marocchino/sticky-pull-request-comment@v2
        if: always()
        with:
          header: cdk-diff
          path: infra/diff.txt
```

`.github/workflows/deploy.yml`:
```yaml
# Push to main: tests → cdk deploy --all (ARM64 runner builds the ARM64 images natively) → Amplify release → verify.
# Deploys never overlap and are never cancelled half-way (deployment spec §5.1).
name: deploy
on:
  push:
    branches: [main]
    paths-ignore: ["docs/**", "**/*.md"]
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: deploy-demo
  cancel-in-progress: false
jobs:
  tests:
    uses: ./.github/workflows/app-tests.yml
  deploy:
    needs: tests
    runs-on: ubuntu-24.04-arm
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: infra/realtime/package-lock.json }
      - uses: astral-sh/setup-uv@v6
      - run: npm ci
        working-directory: infra/realtime
      - run: uv sync --frozen
        working-directory: infra
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: us-east-2
      - name: cdk deploy
        working-directory: infra
        run: npx aws-cdk@2 deploy --all --require-approval never -c gitSha=${{ github.sha }} --outputs-file cdk-outputs.json
      - uses: actions/upload-artifact@v4
        with: { name: cdk-outputs, path: infra/cdk-outputs.json }
  web:
    needs: deploy
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: { name: cdk-outputs, path: infra }
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: us-east-2
      - name: Amplify release
        run: ./infra/scripts/amplify_release.sh "$(jq -r '."LbDemo-Web".AppId' infra/cdk-outputs.json)"
  verify:
    needs: web
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - uses: actions/download-artifact@v4
        with: { name: cdk-outputs, path: infra }
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: us-east-2
      - name: verify
        working-directory: infra
        run: uv run python scripts/verify.py --outputs cdk-outputs.json --sha ${{ github.sha }}
```
**If Task 1 Step 5 found no ARM64 runners for this repo:** in `deploy.yml`, set the deploy job's `runs-on: ubuntu-latest`, and add these two steps before `cdk deploy`:
```yaml
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
```
Then change the `runs-on` assertion in `test_workflows.py` to `ubuntu-latest`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_guard.py tests/test_verify.py tests/test_workflows.py -v`
Expected: all pass.
Run: `uv run pytest -q`
Expected: the whole infra suite passes.

- [ ] **Step 6: Commit**

```bash
cd .. && git add .github/workflows/app-tests.yml .github/workflows/app-ci.yml .github/workflows/deploy.yml infra/scripts infra/tests/test_guard.py infra/tests/test_verify.py infra/tests/test_workflows.py
git commit -m "ci: app tests, PR cdk diff with stateful guard, and deploy → Amplify release → verify

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Phase E: first deploy and the operations record

### Task 14: Bootstrap the account, first deploy, live checks, README and spec fixes

**Scope limits:** running the bootstrap, live verification, the README Operations section, and two spec corrections. **Every step that touches AWS, Jev or Bedrock needs the owner's explicit approval for that step.**

**Check when done:** spec §11 (definition of done) is met and recorded in "Task 14 results" at the end of this file.

**Files:**
- Modify: `README.md` (Operations section), `docs/superpowers/specs/2026-09-26-data-pipeline-design.md` (§7), `docs/superpowers/specs/2026-10-01-deployment-design.md` (a changelog for the planning adjustments), this plan (append "Task 14 results")

**Interfaces:**
- Consumes: everything above; the UI plan's `infra/realtime/scripts/probe-subscribe.ts` and Task 24 Step 4 (the live smoke walk).
- Produces: the deployed URLs, the measured latencies and quotas, and the README record.

- [ ] **Step 1: Run the bootstrap (needs approval: creates IAM roles, secrets and every stack)**

Prerequisites: the agent-core, UI and resolver tasks are merged; `config/demo_users.yaml` exists locally (agent-core Task 12, UI Task 6); you're signed in with `gh` as an account with admin rights on the repo.

Run:
```bash
cd infra/realtime && npm ci && cd .. && uv sync
AWS_PROFILE=<admin profile> ./bootstrap.sh
```
Expected:
- each of the 8 steps prints its header;
- step 5 ends with all six stacks `✅`;
- step 6 prints `uploaded N labeled identities`;
- step 8 prints `Amplify job … succeeded` and `verify: OK`.

**If step 5 fails:** read the CloudFormation event the CDK CLI prints, fix the owning task's code with a test, commit, and re-run `./bootstrap.sh` (it's re-runnable).

- [ ] **Step 2: First deploy through GitHub (needs approval)**

Push the branch to `main` (or merge its PR). Watch it with `gh run watch`.
Expected:
- the PR shows a `cdk diff` comment and the guard passes;
- on `main`, `deploy.yml` runs `tests → deploy → web → verify`, all green;
- verify prints `verify: OK`.

Record the run URL.

**If the PR's `cdk diff` fails with "could not assume role"** (the CLI didn't fall back to the lookup role): add to the diff role in `github.py`:
- `cloudformation:GetTemplate` and `cloudformation:DescribeStacks` on `arn:aws:cloudformation:us-east-2:<acct>:stack/LbDemo-*/*`;
- `ssm:GetParameter` on `arn:aws:ssm:us-east-2:<acct>:parameter/cdk-bootstrap/hnb659fds/version`.

Then add a test asserting those actions in `test_github.py`, re-run `./bootstrap.sh` (step 3 updates the stack) and re-run the PR checks.

- [ ] **Step 3: Live checks (needs approval for each; these call Jev and Bedrock)**

Walk these on the deployed URL (the `AppUrl` output). Record each result and time in "Task 14 results":
1. **UI walk:** the UI plan's Task 24 Step 4 items 1–6 (demo acts 1–3, all 8 scenarios, the unauthorized → handoff takeover, the isolation probe, DLQ OK).
2. **Trace link:** open `/trace/<sid>` for a turn from item 1. The "CloudWatch trace ↗" link opens a trace in X-Ray with the `node.*` spans. If the console shows "trace not found" for a few minutes, wait for ingestion, then retry once.
3. **Metrics:** dashboard `lb-demo-ops` shows data in all five rows within 5 minutes. For any empty widget, run `aws cloudwatch list-metrics --namespace <ns>` and fix the metric name in `ops.py` (with its test) in a follow-up commit.
4. **Forced Jev failure:**
   1. With approval, push a throwaway commit that sets `JEV_SECRET_ID` to `lb-demo/does-not-exist` in `agent.py`.
   2. After it deploys, send 5 messages.
   3. Expected: replies are clarify or handoff; `lb-demo-jev-failing` and `lb-demo-DemoUnhealthy` turn `ALARM` on the dashboard.
   4. Revert the commit. Expected: both alarms return to `OK`.
5. **Latency:** record cold-start latency (first turn after 15+ idle minutes) and warm p50/p95 over 10 turns, from the `TurnLatencyMs` widget.
6. **Capacity:** copy the Task 1 Step 6 quota values next to the measured numbers.

- [ ] **Step 4: README Operations section**

Append to `README.md`:
````markdown
## Operations (demo environment)

One AWS account, environment `demo`, region us-east-2. Everything is defined in `infra/` (AWS CDK, Python) and deployed by `.github/workflows/deploy.yml` on every push to `main`. Design: `docs/superpowers/specs/2026-10-01-deployment-design.md`.

### Setup from a clean account
1. Install: Node 22, uv, Docker, AWS CLI v2, GitHub CLI. Fill `infra/cdk.json` (`githubRepo`, `servingBucket`).
2. Run the data pipeline once so `s3://<servingBucket>/serving/latest.json` exists.
3. Generate the labeled demo identities: `cd agent && uv run python scripts/pick_demo_users.py`, then `uv run python scripts/tag_scenarios.py`.
4. `cd infra/realtime && npm ci && cd .. && uv sync && AWS_PROFILE=<admin> ./bootstrap.sh`.

### Access controls
| From → To | How |
|---|---|
| Browser → web app | httpOnly Secure cookie with a 15-minute JWT from the mock IdP |
| Web app → agent | the customer's Bearer JWT, checked by AgentCore's JWT authorizer and re-verified by the agent |
| Browser → realtime | subscribe-only token, Lambda authorizer plus channel rules; only the publisher Lambda can publish (IAM) |
| GitHub → AWS | OIDC roles: deploy (main only) and diff (pull requests, read-only) |

Each AWS principal has its own role, and none has `*` actions. Secrets live in Secrets Manager (`lb-demo/*`) and never in git, GitHub or logs.

### Data retention
| Data | Kept for |
|---|---|
| Agent checkpoints | 30 days |
| Decision records, conversation transcripts, sessions | 90 days |
| Disputes and handoffs | no expiry in the prototype |
| Logs | 30 days |
| Serving data runs | the last 3 |
| DynamoDB point-in-time recovery | 35 days |

### Monitoring
CloudWatch dashboard `lb-demo-ops`: outcomes, latency, dependencies, realtime and platform. Alarm state shows on the dashboard; `lb-demo-DemoUnhealthy` combines every alarm. There are no notifications in the demo.

Every turn is traced in X-Ray: the staff trace page links each turn to its trace, and decision records carry `trace_id` and the deployed `git_sha`.

### Capacity (single-user measurements, not a load test)
| Component | Quota | Measured |
|---|---|---|
(one row per Task 14 Step 3 item 6 value)

### Rollback
1. `git revert <bad commit>` and push; `deploy.yml` redeploys the previous state.
2. Emergency, agent only: point the `live` endpoint at the previous version with `aws bedrock-agentcore-control update-agent-runtime-endpoint --agent-runtime-id <id> --endpoint-name live --agent-runtime-version <previous>`, then revert in git so the infrastructure code matches again.

### Rotating the IdP signing key
1. Create the new key under a new kid.
2. Serve both keys in the JWKS.
3. Switch signing to the new key.
4. Remove the old key after 15 minutes.

The prototype does this by hand.

### Remaining deployment work
(the 11 items of spec §9, verbatim, in order)
````
Fill the two parenthesised lines with the recorded values and the spec's §9 list. They're the only fill-ins.

- [ ] **Step 5: Spec corrections**

In `docs/superpowers/specs/2026-09-26-data-pipeline-design.md` §7, replace:
```
- Agent (Fargate) → our bucket: task role with `s3:GetObject/ListBucket` on `serving/*`.
```
with:
```
- Agent (AgentCore Runtime) → our bucket: the runtime execution role with `s3:GetObject/ListBucket` on `serving/*` (deployment spec §4.2).
```

Append to `docs/superpowers/specs/2026-10-01-deployment-design.md`:
```markdown
## 13. Changes found while planning (2026-10-01)

- The BFF calls AgentCore with the Bearer token only, so the Amplify compute role has no `InvokeAgentRuntime` (§4.1).
- There is no cookie-signing key: the cookie holds the IdP-signed JWT (§3, §4.3).
- The serving bucket and Snowflake role pre-exist (pipeline plan Task 2). `LbDemo-Data` references the bucket and adds a TLS-only policy; there is no lifecycle backstop (§3, §5.4 step 6).
- Demo identities are read by the identity Lambda from `s3://<serving bucket>/identity/demo_users.yaml` (gitignored locally).
- Names: tables `lb-demo-<name>`, runtime `lb_demo_agent`, stacks `LbDemo-<Part>`.
- DynamoDB throttling is six per-table alarms (the 10-metrics-per-alarm limit).
- Workflows are `app-tests.yml`, `app-ci.yml` and `deploy.yml`; the data pipeline keeps `ci.yml`.
- The GitHub deploy role can also start Amplify jobs and read the runtime's status, for the `web` and `verify` jobs (§4.2).
```

- [ ] **Step 6: Record and commit**

Append `## Task 14 results (YYYY-MM-DD)` to this file, containing:
- the app URL, issuer and runtime id;
- the `deploy.yml` run URL;
- each live check's outcome;
- latencies;
- the quota table.

```bash
git add README.md docs/superpowers/specs/2026-09-26-data-pipeline-design.md docs/superpowers/specs/2026-10-01-deployment-design.md docs/superpowers/plans/2026-10-01-deployment.md
git commit -m "docs: operations README, deployment results and spec corrections

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec section | Task(s) |
|---|---|
| §1 decisions (one account, IaC + CD, CDK Python, six stacks, identity on Lambda + HTTP API, Amplify auto-build off, alarms without notifications) | 5–10, 13 |
| §2 facts (`JEV_API_KEY` name, pipeline §7 correction) | 2 (Step 7), 14 (Step 5) |
| §3 stacks 1–6 | 5, 6, 7, 8, 9, 10 |
| §4.1 trust paths | 6, 7, 8, 9, 12 (adjustment 1: Bearer-only) |
| §4.2 roles, least privilege | 7, 8, 9, 11, 12 |
| §4.3 secrets | 2, 4, 6, 7, 9, 12 |
| §4.4 data protection (no message text in logs, TLS) | 5, 7 |
| §4.5 retention | 2 (sessions TTL), 5, 6, 7, 8, 11 |
| §5.1 workflows | 13 |
| §5.2 ordering and traceability (git SHA in records, image, footer) | 2, 3, 7, 9, 13 |
| §5.3 verify | 13 |
| §5.4 bootstrap | 12, 14 |
| §6.1 tracing (ADOT, node spans, trace_id link) | 3, 7, 9, 12 (Transaction Search) |
| §6.2 metrics | 3 |
| §6.3 alarms, §6.4 dashboard | 10 |
| §7 failure handling and rollback | 3, 4, 5 (RETAIN), 13 (guard, chained jobs), 14 (runbook) |
| §8 capacity | 1 (quotas), 14 (measured, README) |
| §9 remaining work | 14 (README) |
| §10 testing | every task's tests; 11 (cdk-nag, IAM); 13 (guard); 14 (live checks) |
| §11 definition of done | 14 |
| §12 open items | 1 (each check), with fallbacks in 7, 9, 13 |
