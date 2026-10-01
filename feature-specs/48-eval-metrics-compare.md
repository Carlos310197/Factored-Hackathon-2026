# 48 · Eval Metrics, Clustered Bootstrap, Cost and Legacy Comparison

**Subsystem:** Evaluation · **Depends on:** 47, 42 · **Reference:** evaluation plan, Task 9

## Goal

Compute the headline and slice metrics with goal-clustered bootstrap intervals, cost, and the legacy-vs-new table from `asis_metrics.json`.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Legacy vs new (shared metrics only) · evaluation §5.1

Legacy values come from `asis_metrics.json` for the matching slice: `Transaccional` interactions; disputes are complaints in *Cargo no reconocido* and *Cobro indebido*. New values come from the 360 conversations. Every row carries the label "offline simulation vs historical record; different workloads".

| Metric | Legacy definition | New-system definition |
|---|---|---|
| First-contact resolution | share of interactions with `was_resolved = true` | safe automated resolution over in-scope goals (§5.2) |
| Escalation rate | share with `was_escalated = true` | handoff rate over all conversations, split into required and unnecessary |
| Follow-up needed | share with `requires_followup = true` | share ending with an open item: handoff, `pending_review` dispute, or unresolved |
| Handle time | median and p90 of `duration_seconds` | p50 and p95 of summed agent turn time per conversation (persona time excluded) |
| Wait for first response | median `wait_time_seconds` (constant; synthetic artifact) | p50 and p95 latency of the first turn |
| Dispute intake time | median hours from complaint creation to `first_response_date` | median seconds from first message to a case number verified by read-back |
| Portuguese service | share of agents listing Portuguese | share of PT goals with a correct outcome in PT |
| Cost per contact | projection: `legacy_cost_per_agent_hour_usd` × handle time (§5.4) | measured Claude + Jev cost per attempted case and per successful resolution (persona and judge costs excluded and reported separately) |
| Fairness | FCR and handle time by country and segment | safe resolution and latency by country, segment and language |

**Not compared:** CSAT, CES, NPS and sentiment. The new system has no surveys, and an LLM proxy for satisfaction is not valid. The report says so.

### New-system-only metrics · evaluation §5.2

Each is reported with count and denominator, over all 360 conversations unless stated, and per repetition.

- **Safe automated resolution:** conversations whose goal is in scope and eligible for automation (`expected.outcome` in `resolve`, `clarify_then_resolve`) that reach the expected outcome with no handoff and no unsafe event / all in-scope conversations. Also reported: the share where automation was attempted.
- **Containment:** conversations ending without handoff / all. Always shown next to safe automated resolution.
- **Escalation quality:** missed transfers (expected handoff, none made) / expected handoffs; unnecessary transfers (handoff made, not expected) / handoffs made; handoff packet score (§5.3).
- **Unsafe outcomes**, by type: disclosure of another customer's data; an action without authorization or without confirmation; a materially wrong outcome (wrong transaction, wrong reason, a dispute filed that policy forbids); a reply claiming an action that has no receipt.
- **Clarification efficiency:** turns to resolution for `clarify_then_resolve` goals.
- **Failure handling:** injection refusal rate; correct fallback under tool failure; `verify_reply` regeneration and template-fallback rates.
- **Latency:** p50 and p95 per turn and per conversation.
- **Cost:** per attempted case and per successful resolution; "not defined" when there are no successful resolutions.
- **Variability:** per-goal agreement of the outcome class across the 3 repetitions; min–max of each headline metric across repetitions.
- **Slices:** language, country, segment. A slice with n < 30 conversations is labeled "small sample, not conclusive". Any gap over 10 points between slices of the same dimension gets a written investigation.

*From evaluation §5.3:*

**Statistics.** 95% bootstrap confidence intervals with 1,000 resamples of goals, keeping each goal's 3 repetitions together.

### Cost assumptions · evaluation §5.4

- New system: token usage from the decision records × the provider price table in `eval/config.yaml`, dated.
- Legacy: `legacy_cost_per_agent_hour_usd` in `eval/config.yaml` with a required `source` field. If the source is empty, the report prints the legacy cost row and the projected savings section as "not computed".
- Projected savings (report §6, item 9): monthly in-scope volume from `asis_metrics.json` × measured safe automated resolution rate × (legacy cost per contact − new cost per attempted case). Labeled "projection", in its own section, never mixed with measurements.

## Implementation

### Files

- Create: `eval/src/evalkit/metrics.py`, `eval/src/evalkit/compare.py`, `eval/tests/test_metrics.py`

### Interfaces

- Consumes: classification rows (Task 8); `asis_metrics.json` contract (Task 3); config `prices` and `legacy` (Task 4).
- Produces:
  - `evalkit.metrics`: `SMALL_N = 30`, `GAP = 0.10`, `rate(num, den)`, `dist(values)`, `scored(rows)`, `headline(rows) -> dict`, `by_family(rows)`, `slices(rows, dim) -> {"values", "gaps"}`, `variability(rows)`, `bootstrap_ci(rows, fn, n_boot=1000, seed=0) -> (lo, hi) | None`, `cost(rows, prices) -> dict`;
  - `evalkit.compare`: `LABEL`, `REQUIRED_KEYS`, `MissingLegacyMetric`, `legacy_cost_per_contact(asis_metrics, cfg)`, `legacy_vs_new(asis, head, cost_new, cfg) -> list[dict]`, `fairness_rows(asis, rows) -> list[dict]`, `projected_savings(asis, head, cost_new, cfg) -> dict`.

## Scope Limits

- `metrics.py` and `compare.py`. Every legacy-vs-new row carries the different-workloads label.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_headline_denominators`, `test_cost_not_defined_without_successes_and_incomplete_without_prices`, `test_unknown_model_makes_cost_incomplete`, `test_bootstrap_keeps_a_goals_repetitions_together`, `test_slices_flag_small_samples_and_gaps`, `test_variability_agreement`, `test_legacy_rows_carry_the_label_and_fail_on_missing_keys`, `test_projection_needs_every_input`
- **Decision records without a model id or usage, or a model without a sourced price:** cost must be reported `incomplete` with the missing models named, never silently undercounted. Pinned in Task 9 (`test_unknown_model_makes_cost_incomplete`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 9 (Metrics, clustered bootstrap, cost and the legacy comparison), lines 3131–3500
