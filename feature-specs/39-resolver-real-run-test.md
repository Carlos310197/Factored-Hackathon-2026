# 39 · Resolver Real Run II: Freeze, Evaluate Once, Decide Adoption

**Subsystem:** Transaction resolver · **Depends on:** 38 · **Reference:** resolver plan, Task 14 · **[live]**

## Goal

Freeze Andrés's test set, evaluate it exactly once, run the human ceiling, and record the adoption decision.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From resolver §5.4:*

3. The completed file `resolver/data/test_v1.jsonl` is committed, and its SHA-256 is recorded in this spec's changelog (§9) before any evaluation.
4. It is evaluated **once**, after every dev decision is frozen (§6.4). A rerun is allowed only to fix a bug, and is disclosed in the report together with both results.
5. **Human ceiling:** after the test run, Carlos resolves 40 test messages blind, with candidates shown and no target marked. His accuracy is reported as the human ceiling.

## Implementation

### Files

- Create (generated): `agent/resolver/data/test_sheet_v1_completed.csv`, `agent/resolver/data/test_v1.jsonl`, `agent/resolver/runs/jev/test/*.jsonl`, `agent/resolver/data/ceiling_v1.csv`, `agent/resolver/reports/errors.csv`, `agent/resolver/reports/eval-<date>.md`
- Modify: `docs/superpowers/specs/2026-09-29-transaction-resolver-design.md` (§9 changelog), `agent/README.md`, and `agent/docker-compose.yml` if P is adopted

### Interfaces

None: this is a documentation or run task.

### Notes

- The Files list says to edit the spec's changelog under `docs/superpowers/specs/`. Record it in `context/progress-tracker.md` → Spec Changelog instead (the design specs are frozen).

## Scope Limits

- One evaluation of the test set. A rerun is allowed only to fix a bug, and both results are disclosed.
- Record the test-set SHA-256 and the adoption decision in `progress-tracker.md` → Spec Changelog → Resolver.
- Every live step (Bedrock 150, Jev 900 calls) needs the owner's approval.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  (no automated tests in this task)
- The resolver definition of done (`context/project-overview.md` → Success Criteria · resolver §8) is met.
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 14 (Real run II: freeze the test set, evaluate once, decide adoption), lines 4265–4375
