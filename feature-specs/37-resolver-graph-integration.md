# 37 · Agent-Core Changes II: Resolver in the Graph

**Subsystem:** Transaction resolver · **Depends on:** 36, 21, 22, 24 · **Reference:** resolver plan, Task 12

## Goal

Call the resolver in the `understand` node, add `kind: model` records, fall back to `understand.v1` on any failure, and ship the runtime deps in the image.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver
- Resolver plan #12 and #13 in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From resolver §3.2 (items 1 and 3 are unit 29):*

2. **`understand` node:** calls `resolver.score()` after `extract` and before building the Jev request.

4. **Decision records:** a new `kind: model` entry holding the resolver version, the per-candidate probabilities, `best_raw_fit`, and the top three feature contributions per candidate.
5. **Failure:** any resolver exception → no scores for this turn, one `kind: error` record, and the Jev-alone path (`understand.v1` formatting). The turn is never blocked.
6. **`select_candidates`** is unchanged and serves as baseline B0.

## Implementation

### Files

- Modify: `agent/src/bankagent/graph/deps.py`, `agent/src/bankagent/graph/nodes.py`, `agent/src/bankagent/settings.py`, `agent/src/bankagent/runtime.py`, `agent/Dockerfile`, `agent/tests/harness.py`, `agent/tests/test_scaffold.py`
- Create: `agent/tests/test_graph_resolver.py`, `agent/tests/test_resolver_runtime.py`

### Interfaces

- Consumes: agent-core Tasks 10, 11, 13; `Resolver`, `ResolverUnavailable` (Task 6); `understand.v2` (Task 4); `write_logreg_artifact` (Task 6).
- Produces:
  - `Deps.resolver` (default `None`) and `Deps.understand_qs_scored` (default `None`);
  - `Settings.resolver_artifact` (`RESOLVER_ARTIFACT`) and `Settings.thresholds_file` (`THRESHOLDS_FILE`), both default `None`;
  - `runtime.load_resolver(path) -> Resolver | None` (never raises);
  - `make_harness(..., resolver=None)`;
  - a decision record of `kind: "model"`, with payload `{probs, p_none, best_raw_fit, contributions}` and versions `{"resolver": version}`.

## Scope Limits

- Additive changes to `graph/deps.py`, `graph/nodes.py`, `settings.py`, `runtime.py` and the Dockerfile. The resolver is off by default in settings.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_scores_reach_jev_with_understand_v2`, `test_resolver_failure_falls_back_to_v1`, `test_no_extraction_means_no_scores`, `test_load_resolver_is_optional_and_never_raises`, `test_resolver_settings_default_off`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 12 (Agent-core changes II: the resolver in the graph, settings, runtime and image), lines 3858–4198
