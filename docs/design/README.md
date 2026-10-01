# Design Specs (frozen)

These are the original design specs, kept unchanged as rationale. Their text has been copied word for word into `context/` and `feature-specs/`, which are the working specs; `context/progress-tracker.md` → Architecture Decisions records later changes. Don't edit these files.

Use this index to resolve a `§` reference in copied text: it lists where each section now lives.

## `pipeline`: [2026-09-26-data-pipeline-design.md](2026-09-26-data-pipeline-design.md)

| § | Section | Now in |
| --- | --- | --- |
| 1 | Purpose | `context/project-overview.md`, `context/architecture-context.md` |
| 2 | Verified facts the design rests on | `context/project-overview.md` |
| 3 | Scope | `context/project-overview.md` |
| 4 | Architecture | `context/architecture-context.md` |
| 4.1 | Ingestion modes (documented migration path, not built) | `context/architecture-context.md` |
| 5 | Layers and contracts | (heading only) |
| 5.1 | RAW (`LATAM_BANK.RAW`) | `feature-specs/02-snowflake-objects.md`, `feature-specs/03-loader-plan.md` |
| 5.2 | STAGING (`LATAM_BANK.STAGING`, dbt `stg_*` models, materialized as tables) | `feature-specs/06-staging-quarantine.md`, `feature-specs/05-dbt-sources.md` |
| 5.3 | CURATED (`LATAM_BANK.CURATED`, dbt models with `contract: enforced`) | `context/architecture-context.md` |
| 5.4 | Serving export (our bucket, `s3://<our-bucket>/serving/`) | `context/architecture-context.md` |
| 6 | Failure handling | `context/architecture-context.md` |
| 7 | Access and secrets | `context/architecture-context.md` |
| 8 | Fixture drop and tests | `feature-specs/09-fixture-drop.md` |
| 9 | Definition of done | `context/project-overview.md` |
| 10 | Open items | `context/progress-tracker.md` |
| 11 | Out of scope for this spec | `context/project-overview.md` |

## `agent-core`: [2026-09-29-agent-core-design.md](2026-09-29-agent-core-design.md)

| § | Section | Now in |
| --- | --- | --- |
| 1 | Purpose and scope | `context/project-overview.md`, `context/architecture-context.md` |
| 2 | Facts this design rests on | `context/project-overview.md` |
| 3 | Architecture | `context/architecture-context.md` |
| 3.1 | Components | `context/architecture-context.md` |
| 3.2 | One turn | `context/architecture-context.md` |
| 4 | Jev decisions | `feature-specs/19-jev-decisions-routing.md` |
| 4.1 | `understand` (every turn) | `feature-specs/19-jev-decisions-routing.md` |
| 4.2 | `verify_reply` (before sending) | `feature-specs/19-jev-decisions-routing.md` |
| 4.3 | Starting thresholds (illustrative, not calibrated; tuned in spec 2) | `feature-specs/19-jev-decisions-routing.md` |
| 4.4 | Jev failures | `feature-specs/19-jev-decisions-routing.md` |
| 5 | Dispute policy (`policy/dispute_policy.yaml`, labeled synthetic, versioned) | `feature-specs/15-dispute-policy.md` |
| 6 | Claude | `feature-specs/20-claude-llm.md` |
| 6.1 | `extract` | `feature-specs/20-claude-llm.md` |
| 6.2 | `compose` | `feature-specs/20-claude-llm.md` |
| 6.3 | Language | `feature-specs/20-claude-llm.md` |
| 6.4 | Prompt-injection defense, in layers | `context/architecture-context.md` |
| 7 | Tools and state | (heading only) |
| 7.1 | Tools (`tools/`) | `feature-specs/16-serving-read-tools.md` |
| 7.2 | DynamoDB tables | `context/architecture-context.md` |
| 7.3 | Handoff packet (`handoff.v1`) | `context/architecture-context.md` |
| 7.4 | Decision records | `context/architecture-context.md` |
| 8 | Failure handling | `context/architecture-context.md` |
| 9 | Interfaces for other components | `context/architecture-context.md` |
| 9.1 | To spec 2 (evaluation and learned component) | `context/architecture-context.md` |
| 9.2 | To spec 3 (UI and deployment) | `context/architecture-context.md` |
| 9.3 | To the data pipeline | `context/architecture-context.md` |
| 10 | Testing | `context/code-standards.md` |
| 11 | Definition of done | `context/project-overview.md` |
| 12 | Open items and risks | `context/progress-tracker.md` |
| 13 | Out of scope for this spec | `context/project-overview.md` |

## `resolver`: [2026-09-29-transaction-resolver-design.md](2026-09-29-transaction-resolver-design.md)

| § | Section | Now in |
| --- | --- | --- |
| 1 | Purpose and scope | `context/project-overview.md`, `context/architecture-context.md` |
| 2 | Facts this design rests on | `context/project-overview.md` |
| 3 | Architecture | `context/architecture-context.md` |
| 3.1 | Components (`bankagent/resolver/`) | `context/architecture-context.md` |
| 3.2 | Changes to the agent core (all additive) | `feature-specs/29-resolver-agent-hooks.md`, `feature-specs/37-resolver-graph-integration.md`, `feature-specs/27-resolver-histories.md` |
| 4 | Model | (heading only) |
| 4.1 | Features | `feature-specs/26-resolver-features-splits.md` |
| 4.2 | Training objective | `feature-specs/31-resolver-model.md` |
| 4.3 | Selection and calibration | `feature-specs/32-resolver-training.md`, `feature-specs/34-resolver-finalize.md` |
| 4.4 | Explainability | `feature-specs/31-resolver-model.md` |
| 4.5 | Tracking | `feature-specs/32-resolver-training.md` |
| 5 | Data | (heading only) |
| 5.1 | Simulator (`simulate.py`, `simulate.yaml`) | `feature-specs/28-resolver-simulator.md` |
| 5.2 | Splits and slices (`splits.py`) | `feature-specs/26-resolver-features-splits.md` |
| 5.3 | Dev set (300 cases: 150 ES, 150 PT) | `feature-specs/33-resolver-dev-set.md` |
| 5.4 | Test set (150 cases: 75 ES, 75 PT) | `feature-specs/30-resolver-test-sheet-cli.md`, `feature-specs/39-resolver-real-run-test.md` |
| 6 | Evaluation (`evaluate.py`) | (heading only) |
| 6.1 | Systems | `feature-specs/35-resolver-systems-tuning.md` |
| 6.2 | Outcomes and metrics | `feature-specs/35-resolver-systems-tuning.md` |
| 6.3 | Thresholds | `feature-specs/35-resolver-systems-tuning.md` |
| 6.4 | Adoption rule (fixed before the test run) | `feature-specs/36-resolver-jev-runs-report.md` |
| 6.5 | Error analysis | `feature-specs/36-resolver-jev-runs-report.md` |
| 6.6 | Report | `feature-specs/36-resolver-jev-runs-report.md` |
| 7 | Testing | `context/code-standards.md` |
| 8 | Definition of done | `context/project-overview.md` |
| 9 | Schedule, risks and changelog | `context/progress-tracker.md` |

## `ui`: [2026-09-30-ui-design.md](2026-09-30-ui-design.md)

| § | Section | Now in |
| --- | --- | --- |
| 1 | Purpose and scope | `context/project-overview.md`, `context/architecture-context.md` |
| 2 | Facts this design rests on | `context/architecture-context.md` |
| 3 | Architecture | `context/architecture-context.md` |
| 3.1 | Channel events | `context/architecture-context.md` |
| 4 | Change requests to the agent core | `feature-specs/54-agent-ui-tables.md`, `feature-specs/56-entrypoint-ui-gate.md`, `feature-specs/64-web-dynamodb.md`, `context/architecture-context.md`, `feature-specs/55-identity-staff-realtime.md`, `feature-specs/58-scenario-tags.md` |
| 5 | Data access | `feature-specs/64-web-dynamodb.md` |
| 6 | BFF route handlers (`web/app/api/…`) | `context/ui-context.md` |
| 7 | Visual design | `context/ui-context.md` |
| 7.1 | World B: customer (`/login`, `/chat`) | `context/ui-context.md` |
| 7.2 | World C: staff (`/agent`, `/trace`, `/demo` canvas) | `context/ui-context.md` |
| 7.3 | Trace signal colours | `context/ui-context.md` |
| 7.4 | Motion | `context/ui-context.md` |
| 8 | Surfaces | `context/ui-context.md` |
| 8.1 | Customer chat (`/login`, `/chat`; world B, phone-first, responsive) | `context/ui-context.md` |
| 8.2 | Agent console (`/agent`, `/agent/[handoffId]`; world C, desktop) | `context/ui-context.md` |
| 8.3 | Trace component (shared: console tab, `/trace/[sid]`, `/demo`) | `context/ui-context.md` |
| 9 | Demo stage (`/demo`; staff sign-in; world C canvas, projector width ≥ 1280px) | `context/ui-context.md` |
| 9.1 | Act 1: Sign in (once) | `context/ui-context.md` |
| 9.2 | Act 2: Live conversation | `context/ui-context.md` |
| 9.3 | Act 3: Scenarios | `context/ui-context.md` |
| 10 | Failure handling | `context/architecture-context.md` |
| 11 | Accessibility and language | `context/ui-context.md` |
| 12 | Testing | `context/code-standards.md` |
| 13 | Definition of done | `context/project-overview.md` |
| 14 | Open items and risks | `context/progress-tracker.md` |
| 15 | Code locations | `context/architecture-context.md` |

## `deployment`: [2026-10-01-deployment-design.md](2026-10-01-deployment-design.md)

| § | Section | Now in |
| --- | --- | --- |
| 1 | Purpose and scope | `context/project-overview.md`, `context/architecture-context.md` |
| 2 | Facts this design rests on | `context/architecture-context.md` |
| 3 | Stacks | `context/architecture-context.md` |
| 4 | Access controls | `context/architecture-context.md` |
| 4.1 | Trust paths | `context/architecture-context.md` |
| 4.2 | Roles | `context/architecture-context.md` |
| 4.3 | Secrets | `context/architecture-context.md` |
| 4.4 | Data protection | `context/architecture-context.md` |
| 4.5 | Retention | `context/architecture-context.md` |
| 5 | CI/CD | (heading only) |
| 5.1 | Workflows | `feature-specs/89-cicd.md` |
| 5.2 | Ordering and traceability | `feature-specs/89-cicd.md` |
| 5.3 | `verify` job | `feature-specs/89-cicd.md` |
| 5.4 | One-time bootstrap (`infra/bootstrap.sh` plus README) | `feature-specs/88-bootstrap.md` |
| 6 | Observability | (heading only) |
| 6.1 | Tracing | `feature-specs/79-observability.md` |
| 6.2 | Metrics | `feature-specs/79-observability.md` |
| 6.3 | Alarms | `feature-specs/86-ops-stack.md` |
| 6.4 | Dashboard `lb-demo-ops` | `feature-specs/86-ops-stack.md` |
| 7 | Failure handling | `context/architecture-context.md` |
| 8 | Capacity limits | `feature-specs/77-deploy-platform-checks.md` |
| 9 | Remaining deployment work | `context/project-overview.md` |
| 10 | Testing | `context/code-standards.md` |
| 11 | Definition of done | `context/project-overview.md` |
| 12 | Open items and risks | `context/progress-tracker.md` |

## `evaluation`: [2026-10-01-evaluation-design.md](2026-10-01-evaluation-design.md)

| § | Section | Now in |
| --- | --- | --- |
| 1 | Purpose and scope | `context/project-overview.md`, `context/architecture-context.md` |
| 2 | Facts this design rests on | `feature-specs/40-asis-core-metrics.md` |
| 3 | As-is diagnosis (`analysis/asis/`) | (heading only) |
| 3.1 | Inputs and rules | `feature-specs/40-asis-core-metrics.md` |
| 3.2 | Questions answered (in deck order) | `feature-specs/40-asis-core-metrics.md`, `feature-specs/41-asis-more-metrics.md` |
| 3.3 | Outputs | `feature-specs/42-asis-report-run.md` |
| 3.4 | Reconciliation | `feature-specs/42-asis-report-run.md` |
| 4 | Held-out workload and harness (`eval/`) | (heading only) |
| 4.1 | Goal mix (120 goals: 60 ES, 60 PT) | `feature-specs/43-eval-goals.md` |
| 4.2 | Goal card (`eval/goals/`) | `feature-specs/43-eval-goals.md` |
| 4.3 | Splits and leakage | `feature-specs/43-eval-goals.md` |
| 4.4 | Persona (`eval/persona.py`) | `feature-specs/44-eval-persona.md` |
| 4.5 | Harness (`eval/run.py`) | `feature-specs/45-eval-conversation.md` |
| 5 | Metrics | (heading only) |
| 5.1 | Legacy vs new (shared metrics only) | `feature-specs/48-eval-metrics-compare.md` |
| 5.2 | New-system-only metrics | `feature-specs/48-eval-metrics-compare.md` |
| 5.3 | Scoring (`eval/score.py`) | `feature-specs/47-eval-classifier.md`, `feature-specs/49-eval-judge.md`, `feature-specs/48-eval-metrics-compare.md` |
| 5.4 | Cost assumptions | `feature-specs/48-eval-metrics-compare.md` |
| 6 | Report (`reports/eval-<date>.md`) | `feature-specs/50-eval-report.md` |
| 7 | Failure handling | `context/architecture-context.md` |
| 8 | Testing (pytest, offline) | `context/code-standards.md` |
| 9 | Interfaces | `context/architecture-context.md` |
| 10 | Definition of done | `context/project-overview.md`, `context/progress-tracker.md` |
| 11 | Schedule and risks | `context/progress-tracker.md` |
