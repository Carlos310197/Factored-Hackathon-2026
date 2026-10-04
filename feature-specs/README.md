# Feature Specs

Numbered work units in build order. Each one maps to a single task of a reference plan and owns the spec text that belongs only to it. Pick the next unit from `context/progress-tracker.md`, check that its dependencies are done, and read only what its **Read First** list names.

`[live]` units call external services or change cloud resources, and need the owner's approval for each such step.

## Data pipeline

| # | Unit | Depends on | Plan task |
| --- | --- | --- | --- |
| 01 | [Pipeline Scaffold and Snowflake Connection](01-pipeline-scaffold.md) | none | pipeline 1 |
| 02 | [Snowflake Account Objects, Stages and RAW Tables](02-snowflake-objects.md) `[live]` | 01 | pipeline 2 |
| 03 | [Loader Plan Logic](03-loader-plan.md) | 02 | pipeline 3 |
| 04 | [Loader Snowflake Calls and First Full Load](04-loader-first-load.md) `[live]` | 03 | pipeline 4 |
| 05 | [dbt Project, Sources with Freshness, Unexpected-Column Test](05-dbt-sources.md) | 04 | pipeline 5 |
| 06 | [Staging Models: Typing, Dedup, Quarantine and Tests](06-staging-quarantine.md) | 05 | pipeline 6 |
| 07 | [Curated Marts, Decline-Reason Seed and DQ Results](07-curated-marts.md) | 06 | pipeline 7 |
| 08 | [Serving Export with Atomic Pointer (sorted by customer)](08-serving-export.md) `[live]` | 07 | pipeline 8 |
| 09 | [Fixture Drop and the End-to-End Proof Test](09-fixture-drop.md) `[live]` | 08 | pipeline 9 |
| 10 | [GitHub Actions: CI and the Scheduled Pipeline](10-pipeline-workflows.md) `[live]` | 09 | pipeline 10 |
| 11 | [Data Pipeline README](11-pipeline-readme.md) | 10 | pipeline 11 |

## Agent core

| # | Unit | Depends on | Plan task |
| --- | --- | --- | --- |
| 12 | [Agent Project Scaffold, Settings and Session Context](12-agent-scaffold.md) | none | agent-core 1 |
| 13 | [Jev Client with Strict Validation](13-jev-client.md) `[live]` | 12 | agent-core 2 |
| 14 | [Session Tokens and the Mock OIDC Identity Service](14-identity-tokens.md) | 12 | agent-core 3 |
| 15 | [Dispute Policy (labeled synthetic)](15-dispute-policy.md) | 12 | agent-core 4 |
| 16 | [Serving Reader and Read Tools](16-serving-read-tools.md) | 12 | agent-core 5 |
| 17 | [DynamoDB Tables and Repositories](17-dynamodb-store.md) | 12 | agent-core 6 |
| 18 | [Write Tools, Handoff Packet and the Reply Id Guard](18-write-tools-handoff.md) | 15, 16, 17 | agent-core 7 |
| 19 | [Jev Question Sets, Thresholds and Routing](19-jev-decisions-routing.md) | 13 | agent-core 8 |
| 20 | [Claude on Bedrock: Model Config, Extract, Compose, Templates](20-claude-llm.md) `[live]` | 12 | agent-core 9 |
| 21 | [LangGraph Workflow and the Agent Service](21-graph-service.md) | 14–20 | agent-core 10 |
| 22 | [Runtime Wiring and the AgentCore Entrypoint](22-agentcore-entrypoint.md) | 21 | agent-core 11 |
| 23 | [Local Serving Set and Demo Identities](23-local-serving-demo-users.md) | 16, 14 | agent-core 12 |
| 24 | [Container Image, Local Stack and Terminal Chat](24-container-local-stack.md) | 22, 23 | agent-core 13 |
| 25 | [Agent Live Checks, Definition-of-Done Run and README](25-agent-live-checks.md) `[live]` | 24 | agent-core 14 |

## Transaction resolver

| # | Unit | Depends on | Plan task |
| --- | --- | --- | --- |
| 26 | [Resolver Features and Splits](26-resolver-features-splits.md) | 12, 16 | resolver 1 |
| 27 | [Resolver History Sampler](27-resolver-histories.md) | 26 | resolver 2 |
| 28 | [Resolver Simulator](28-resolver-simulator.md) | 27 | resolver 3 |
| 29 | [Agent-Core Changes I: Extract Hints, Dev Writer, understand.v2](29-resolver-agent-hooks.md) | 28, 19, 20 | resolver 4 |
| 30 | [Records, the Blind Test Sheet and the Resolver CLI](30-resolver-test-sheet-cli.md) | 29 | resolver 5 |
| 31 | [Resolver Inference Model](31-resolver-model.md) | 26 | resolver 6 |
| 32 | [Resolver Training, Selection and MLflow Tracking](32-resolver-training.md) | 28, 31 | resolver 7 |
| 33 | [Resolver Dev-Set Builder](33-resolver-dev-set.md) | 29, 30 | resolver 8 |
| 34 | [Finalist Choice, Calibration, Promotion and Model Card](34-resolver-finalize.md) | 32 | resolver 9 |
| 35 | [The Four Systems, Metrics and Threshold Tuning](35-resolver-systems-tuning.md) | 34 | resolver 10 |
| 36 | [Resolver Jev Runs and Evaluation Report](36-resolver-jev-runs-report.md) | 35 | resolver 11 |
| 37 | [Agent-Core Changes II: Resolver in the Graph](37-resolver-graph-integration.md) | 36, 21, 22, 24 | resolver 12 |
| 38 | [Resolver Real Run I: Train, Dev Set, Finalize, Tune](38-resolver-real-run-dev.md) `[live]` | 37 | resolver 13 |
| 39 | [Resolver Real Run II: Freeze, Evaluate Once, Decide Adoption](39-resolver-real-run-test.md) `[live]` | 38 | resolver 14 |

## Evaluation

| # | Unit | Depends on | Plan task |
| --- | --- | --- | --- |
| 40 | [As-Is Project, Loader and Core Metrics](40-asis-core-metrics.md) | none | evaluation 1 |
| 41 | [As-Is Capacity, Disputes, Digital, Fairness and Artifact Detectors](41-asis-more-metrics.md) | 40 | evaluation 2 |
| 42 | [As-Is Reconciliation, Charts, Report and the Real Run](42-asis-report-run.md) | 41 | evaluation 3 |
| 43 | [Eval Project, Splits, Universe and the Goal Generator](43-eval-goals.md) | 15, 23 | evaluation 4 |
| 44 | [Persona Client and Rule Checks](44-eval-persona.md) | 43 | evaluation 5 |
| 45 | [Fault Injection, Test Tokens and the Conversation Runner](45-eval-conversation.md) | 44, 21 | evaluation 6 |
| 46 | [Eval Runtime Wiring and the Resumable Run CLI](46-eval-run-cli.md) | 45 | evaluation 7 |
| 47 | [Deterministic Outcome Classifier](47-eval-classifier.md) | 46 | evaluation 8 |
| 48 | [Eval Metrics, Clustered Bootstrap, Cost and Legacy Comparison](48-eval-metrics-compare.md) | 47, 42 | evaluation 9 |
| 49 | [Judge for Soft Criteria and Its Human Validation](49-eval-judge.md) | 47 | evaluation 10 |
| 50 | [Evaluation Report and Charts](50-eval-report.md) | 48, 49 | evaluation 11 |
| 51 | [Eval Live Run I: Smoke, Goal Sets, Review, Dev Run, Freeze](51-eval-live-dev.md) `[live]` | 50, 24 | evaluation 12 |
| 52 | [Eval Live Run II: Held-Out Run, Judge Validation, Report](52-eval-live-heldout.md) `[live]` | 51 | evaluation 13 |

## UI

| # | Unit | Depends on | Plan task |
| --- | --- | --- | --- |
| 53 | [UI Platform Checks (AppSync Events)](53-ui-platform-checks.md) `[live]` | none | ui 1 |
| 54 | [Agent: `sessions` and `conversation_messages` Tables and Streams](54-agent-ui-tables.md) | 17 | ui 2 |
| 55 | [Identity: Staff Login, Realtime Token, Demo List, Short-TTL Tokens](55-identity-staff-realtime.md) | 14 | ui 3 |
| 56 | [Entrypoint: Control Gate, Idempotent Turns, Message Log, `turn_end`](56-entrypoint-ui-gate.md) | 54, 22 | ui 4 |
| 57 | [Trace Payloads: Thresholds, Aliases and the Confirmation Summary](57-trace-payloads.md) | 56 | ui 5 |
| 58 | [Tag Demo Identities with Their Scenarios](58-scenario-tags.md) | 23, 55 | ui 6 |
| 59 | [Realtime: Event API, Lambda Authorizer and Channel Rules](59-realtime-event-api.md) | 55 | ui 7 |
| 60 | [Realtime: Stream-Driven Publisher](60-realtime-publisher.md) | 59, 54, 56, 57 | ui 8 |
| 61 | [Web Scaffold, Design Tokens, Fonts and Test Harness](61-web-scaffold.md) | none | ui 9 |
| 62 | [Web Wire Contract, Formatting and ES/PT Copy](62-web-contract-format.md) | 61 | ui 10 |
| 63 | [Web Server Auth: JWT, Cookies, IdP Client, Auth Routes, `proxy.ts`](63-web-server-auth.md) | 62, 55 | ui 11 |
| 64 | [Web DynamoDB Access: Sessions, Messages, Handoff Lifecycle, Records](64-web-dynamodb.md) | 63, 54 | ui 12 |
| 65 | [AgentCore Client, `/api/chat` and Session History](65-web-chat-routes.md) | 64 | ui 13 |
| 66 | [Handoff Routes for the Console](66-web-handoff-routes.md) | 64 | ui 14 |
| 67 | [Trace View Model, Signal Colours, Stage Mapping, `/api/trace/[sid]`](67-trace-view-model.md) | 64 | ui 15 |
| 68 | [Realtime Client, Channel Hook, Chat Store and API Client](68-web-realtime-store.md) | 62 | ui 16 |
| 69 | [Customer Login (world B)](69-customer-login.md) | 63 | ui 17 |
| 70 | [Customer Chat (world B, assistant-ui)](70-customer-chat.md) | 65, 68, 69 | ui 18 |
| 71 | [Staff Sign-In, Console Shell, Queue and Case Header (world C)](71-staff-console.md) | 66, 68 | ui 19 |
| 72 | [Packet Tab, Conversation Tab and the Shared Gauge](72-packet-conversation-tabs.md) | 71, 67 | ui 20 |
| 73 | [Trace Components, the Reveal, `/trace/[sid]` and the Trace Tab](73-trace-components.md) | 72 | ui 21 |
| 74 | [`/demo` Stage: Three Acts](74-demo-stage.md) | 70, 73, 58 | ui 22 |
| 75 | [Web End-to-End Tests and Accessibility Scans](75-web-e2e-a11y.md) | 74 | ui 23 |
| 76 | [UI Live Smoke Run and the Design Pass](76-ui-live-smoke.md) `[live]` | 75, 90 | ui 24 |

## Deployment

| # | Unit | Depends on | Plan task |
| --- | --- | --- | --- |
| 77 | [Deployment Platform Checks](77-deploy-platform-checks.md) `[live]` | none | deployment 1 |
| 78 | [Agent: Deployed Settings, Git SHA, Sessions TTL, Trace Id](78-deployed-settings.md) | 56 | deployment 2 |
| 79 | [Agent Observability: Stamped Records, EMF Metrics, Node Spans, ADOT](79-observability.md) | 78 | deployment 3 |
| 80 | [Identity Service as a Lambda](80-identity-lambda.md) | 55 | deployment 4 |
| 81 | [Terraform `data` Root: Tables, Image Repositories, Shared Conventions](81-terraform-data-root.md) | 77, 78 | deployment 5 |
| 82 | [Terraform `identity` Root: IdP Lambda Behind an HTTP API](82-identity-stack.md) | 81, 80 | deployment 6 |
| 83 | [Terraform `agent` Root: the AgentCore Runtime](83-agent-stack.md) | 82, 79 | deployment 7 |
| 84 | [Terraform `realtime` Root: AppSync Events, Authorizer, Publisher](84-realtime-stack.md) | 81, 82, 59, 60 | deployment 8 |
| 85 | [Web on ECS Fargate Spot, Build Tag and Trace Link](85-web-stack.md) | 81, 82, 83, 84, 75 | deployment 9 |
| 86 | [Terraform `ops` Root: Alarms and the Dashboard](86-ops-stack.md) | 85 | deployment 10 |
| 87 | [Cross-Root Checks: IAM Wildcards, Log Retention, Security Scan](87-cross-stack-checks.md) | 86 | deployment 11 |
| 88 | [Bootstrap: Secrets, Plan Role, Transaction Search, `seed_demo.py`](88-bootstrap.md) | 87 | deployment 12 |
| 89 | [CI/CD: Reusable Tests, PR Plans with Stateful Guard, Deploy → Verify](89-cicd.md) | 88 | deployment 13 |
| 90 | [First Deploy, Live Checks, Operations README and Spec Fixes](90-first-deploy-ops.md) `[live]` | 89, 24 | deployment 14 |
