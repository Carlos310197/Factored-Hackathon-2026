# 41 · As-Is Capacity, Disputes, Digital, Fairness and Artifact Detectors

**Subsystem:** Evaluation · **Depends on:** 40 · **Reference:** evaluation plan, Task 2

## Goal

Add the remaining as-is metric groups and the detectors that flag the dataset's synthetic artifacts.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation
- `feature-specs/40-asis-core-metrics.md` → Facts this design rests on · evaluation §2 (the artifact list)

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From evaluation §3.2:*

3. **Capacity.** Agents by type, specialty, shift and language; monthly load per agent; hourly demand against agents per shift; Portuguese coverage.
4. **Dispute handling.** For the two dispute subcategories: time to first response, time to resolution, SLA breach, reception channel, open backlog.
5. **Digital channel.** Login, transaction and error volumes from `digital_events`. Descriptive only.
6. **Unusable sources.** Why transcripts are not used.
7. **Data limits and synthetic artifacts.** The list in §2, with the query that shows each one.
8. **Fairness reference.** FCR, CSAT and handle time by country, accent and segment.

## Implementation

### Files

- Modify: `analysis/asis/metrics.py` (append)
- Create: `analysis/asis/artifacts.py`, `analysis/asis/tests/test_more_metrics.py`

### Interfaces

- Consumes: `connect`, `m`, `_rows`, `_b`, `DUR`, constants (Task 1).
- Produces:
  - `asis.metrics`: `SHIFT_HOURS`, `capacity(c)`, `disputes(c)` (also emits `complaints.total`), `digital(c)`, `transcripts(c)`, `fairness(c)`, `collect(c) -> dict` (all metric groups merged);
  - `asis.artifacts`: `escalation_flat(c, min_n=1000, max_range=0.02)`, `sla_flat(c, min_n=500, max_range=0.06)`, `wait_constant(c, max_spread_s=30)`, `csat_by_resolution(c, min_n=1000, max_range=0.05)`, `transactional_sentiment_constant(c)`, `no_pt_customers(c)`, `transcripts_templated(c, max_ratio=0.01)`, `detect_all(c) -> list[dict]`; each detector returns `{"name", "holds", "evidence", "query"}`.

## Scope Limits

- Append to `metrics.py`; add `artifacts.py`. No report yet.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_capacity_and_portuguese_coverage`, `test_disputes_cover_only_the_two_subcategories`, `test_digital_and_transcripts`, `test_fairness_reference_uses_the_in_scope_slice`, `test_collect_merges_every_group`, `test_artifact_detectors_on_the_fixture`, `test_detect_all_names`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 2 (Capacity, disputes, digital, transcripts, fairness and artifact detectors), lines 473–746
