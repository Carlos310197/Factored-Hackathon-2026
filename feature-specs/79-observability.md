# 79 · Agent Observability: Stamped Records, EMF Metrics, Node Spans, ADOT

**Subsystem:** Deployment · **Depends on:** 78 · **Reference:** deployment plan, Task 3

## Goal

Emit EMF metrics and per-node spans from the decision-record stream, best-effort, and run the container under ADOT.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- Deployment plan #7 and #10 in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Tracing · deployment §6.1

- The agent container runs under the ADOT Python distro (`opentelemetry-instrument`) and exports to AgentCore Observability, which shows in CloudWatch GenAI Observability and X-Ray.
- Each graph node is a span with the attributes `session_id`, `turn_id`, `node` and `kind`. Jev, Bedrock, DynamoDB and S3 calls are child spans (botocore and httpx are auto-instrumented).
- **Change request to the agent core (additive):** each decision record also stores `trace_id`. The staff trace page shows a "CloudWatch trace ↗" link, so the audit view (decision records) and the latency view (traces) point to each other.
- The identity, publisher and authorizer Lambdas have active X-Ray tracing.

### Metrics · deployment §6.2

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

## Implementation

### Files

- Create: `agent/src/bankagent/observability.py`
- Modify: `agent/src/bankagent/runtime.py`, `agent/src/bankagent/graph/build.py`, `agent/pyproject.toml`, `agent/Dockerfile`
- Test: `agent/tests/test_observability.py`

### Interfaces

- Consumes: `DecisionLog.append(..., trace_id=…)` and `Settings.git_sha` (Task 2); `build_graph`, `NODES`, `TRACER` (agent-core Task 10); `build_runtime` (agent-core Task 11, resolver Task 12).
- Produces:
  - `NAMESPACE = "LatamBank"`;
  - `current_trace_id() -> str | None`: X-Ray format `1-<8 hex>-<24 hex>`, or `None` when there's no valid span;
  - `emf(values: dict[str, float | list[float]], units: dict[str, str], dims: dict[str, str], dim_sets: list[list[str]], write=print) -> None`;
  - `classify_route(turn: TurnFacts) -> str`, returning one of `act | clarify | abstain | handoff | safe_fallback`;
  - `ObservedLog(inner, git_sha: str, write=print)`: same `append`/`list` as `DecisionLog`, other attributes delegated;
  - `traced_node(name: str, fn) -> fn`: a wrapper with the signature `(state, config)`.

## Scope Limits

- a new `observability.py`, the wiring in `runtime.py` and `graph/build.py`, plus `pyproject.toml` and `Dockerfile`. No change to node logic.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest tests/test_observability.py -v` passes, and `uv run pytest -q` passes.
- The reference task's tests exist and pass:
  `test_emf_document_shape`, `test_classify_route`, `test_stamps_git_sha_and_keeps_versions`, `test_turn_metrics_on_turn_end`, `test_error_counts_and_injection`, `test_observer_never_raises_on_odd_records`, `test_inner_failure_still_propagates_but_metrics_were_recorded`, `test_list_and_attributes_are_delegated`, `test_trace_id_in_xray_format_inside_a_span`, `test_traced_node_keeps_signature_and_result`
- **A malformed or unexpected decision record** (no `latency_ms`, a non-dict payload, a `turn_end` without a preceding route, OpenTelemetry not configured). Expected: the record is still written, no exception reaches the turn, and metrics are skipped or partial. Pinned in Task 3 (`test_observer_never_raises_on_odd_records`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 3 (Observability: stamped records, EMF metrics, node spans and the ADOT image), lines 511–921
