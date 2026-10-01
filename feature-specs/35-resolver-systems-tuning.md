# 35 · The Four Systems, Metrics and Threshold Tuning

**Subsystem:** Transaction resolver · **Depends on:** 34 · **Reference:** resolver plan, Task 10

## Goal

Implement B0/B1/B2/P decisions and outcomes, the metrics with bootstrap intervals, and the threshold search that writes `thresholds.v2.yaml`.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver
- Resolver plan #9 (B0 and `ask_nil`) and #10 (country slice) in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Systems · resolver §6.1

| ID | System | Acts when | Otherwise |
|---|---|---|---|
| B0 | Heuristic: `select_candidates` filter | mentions present and exactly one candidate passes the filter | ask the customer, showing up to 3 candidates that pass, newest first (newest overall if none pass) |
| B1 | Ranker alone | top prob ≥ τ **and** `best_raw_fit` ≥ φ | `best_raw_fit` < φ → `not_in_list`; else ask with the top 3 |
| B2 | Jev alone (`understand.v1`) | the agent-core §4.3 form: top ≥ t and margin ≥ m | ask with Jev's top 3; Jev's `not_in_list` / `ambiguous` as answered |
| **P** | Jev + ranker (`understand.v2`) | same form as B2, with its own t and m | same as B2 |

All systems read the same cached `extract` output per message, so only the resolution step differs. Jev runs 3 times per case for B2 and P, and results are reported as the mean and the min–max range.

### Outcomes and metrics · resolver §6.2

Each case ends in one of four outcomes:
- **act-correct**;
- **act-wrong**, the unsafe outcome. Any action on a `not_in_list` case counts as act-wrong;
- **ask**;
- **`not_in_list`-correct**.

Metrics, each reported with count and denominator:
- **coverage:** acted / all;
- **selective accuracy:** act-correct / acted;
- **wrong-action rate:** act-wrong / all. This is the headline safety number;
- **top-3 recall when asking:** target in the options shown / asks, excluding `not_in_list` cases;
- **resolved within one step:** (act-correct + `not_in_list`-correct + asks with the target in the top 3) / all;
- **added latency** per turn (p50/p95), and the **change in Jev tokens and cost** between P and B2.

Slices: easy / hard / `not_in_list`, ES / PT, and country (MX / CO / AR). A slice with n < 30 is labeled "small sample, not conclusive".

**Statistics:**
- 95% bootstrap confidence intervals (1,000 resamples of cases);
- a paired bootstrap for P − B2 on wrong-action rate and on hard-slice resolved-within-one-step;
- the report states that with n = 150, differences inside about ±7 points are not established.

No LLM judge is used: every label is known by construction.

### Thresholds · resolver §6.3

For each system, on dev: choose the thresholds with the highest coverage subject to a dev wrong-action rate ≤ 2%.
- B1 searches τ and φ over [0.3, 0.99] in steps of 0.01.
- B2 and P search t over [0.5, 0.99] and m over [0, 0.5], in steps of 0.01.

The dev coverage-vs-accuracy curve is published, with the chosen point marked. P's values are written to `decisions/thresholds/v2.yaml`.

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/systems.py`, `agent/src/bankagent/resolver/metrics.py`, `agent/src/bankagent/resolver/tune.py`, `agent/tests/test_resolver_eval.py`

### Interfaces

- Consumes: `matches_mentions`, `SPECIAL_TARGETS` (Task 4); `Scores` (Task 6); `load_thresholds` (agent-core) in tests.
- Produces:
  - `OUTCOMES` (`act_correct, act_wrong, ask_hit, ask_miss, ask_nil, nil_correct, nil_wrong`);
  - `Decision(action, pick=None, options=())`, `outcome(target_id, decision) -> str`;
  - `b0(candidates, mentions)`, `b1(scores, tau, phi)`, `jev_decision(answer | None, t, m)`;
  - `summarize(outcomes) -> dict` with the counts plus `coverage, selective_accuracy, wrong_action_rate, top3_recall_when_asking, resolved_one_step` (`None` when the denominator is 0);
  - `metric(name)`, `bootstrap_ci`, `paired_bootstrap`, `percentile`;
  - `grid(lo, hi, step=0.01)`, `choose(evaluate, points, max_wrong=0.02) -> (point, summary | {"feasible"}, curve)`;
  - `write_thresholds_v2(t, m, src=..., dst=...) -> Path`.

## Scope Limits

- `systems.py`, `metrics.py`, `tune.py`. No Jev calls (unit 36).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_outcomes`, `test_b0_acts_only_on_a_unique_filter_match`, `test_b1_thresholds`, `test_jev_decision`, `test_summary_rates_and_denominators`, `test_bootstrap_intervals`, `test_choose_prefers_coverage_within_the_wrong_action_limit`, `test_thresholds_v2_changes_only_the_target`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 10 (The four systems, metrics and threshold tuning), lines 3026–3328
