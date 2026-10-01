# 28 · Resolver Simulator

**Subsystem:** Transaction resolver · **Depends on:** 27 · **Reference:** resolver plan, Task 3

## Goal

Generate training and simulated-validation cases with structured mentions drawn from documented style rates.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Simulator (`simulate.py`, `simulate.yaml`) · resolver §5.1

For each case:
1. Draw a customer and anchor date for the split (§5.2). The candidates are that customer's transactions in the 60 days before the anchor, which serves as the case's as-of date.
2. Pick a target. The draw is stratified so that about 50% of training cases fall in the hard slice.
3. Draw a description style field by field and produce `mentions`.

Starting rates are assumptions, documented as such; real-text dev and test results reveal a mismatch:

| Field | Styles |
|---|---|
| merchant (purchases only) | exact 40% · accents dropped or one-character typo 20% · absent 40% |
| amount | exact 30% · rounded to 10 or 100 30% · ±10% 15% · the USD amount for a non-USD transaction 5% · absent 20% |
| date | exact day 20% · relative range (this week, last week, this month, last month) 35% · one day off 10% · absent 35% |
| `type_hint`, `channel_hint`, `city` | present 60%, 40%, 40% respectively; 3% of present hints are wrong |
| `extract` error | 5% of cases: one mentioned field replaced with a value from another candidate |
| `not_in_list` | 10%: the target is removed from the candidates; every label is 0 |
| no detail | 5%: all mentions empty |

- **Size:** 30,000 training cases and 3,000 simulated-validation cases.
- **Reproducibility:** fully deterministic from `seed` and the serving `run_id`.

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/simulate.yaml`, `agent/src/bankagent/resolver/simulate.py`, `agent/tests/test_resolver_simulate.py`

### Interfaces

- Consumes: `fold`, `TYPE_HINTS`, `CHANNEL_HINTS` (Task 1); `History` (Task 2); `case_slice` (Task 1).
- Produces:
  - `load_sim_config(path=DEFAULT_CONFIG) -> dict` (adds `sha256`; `ValueError` when a distribution doesn't sum to 1);
  - `simulate(histories, cfg, seed) -> list[dict]`. Each case is `{case_id, split, anchor, slice, target_id | None, target, candidates, mentions, style}`.
    - `mentions` has exactly `MENTION_KEYS` (merchant, amount, currency, date_from, date_to, type_hint, channel_hint, city).
    - `style` holds the style of each field, plus `no_detail`, `extract_error`, `nil`, and `date_label` for relative dates.
  - `relative_ranges(anchor)`, `relative_range(d, anchor) -> (label, lo, hi) | None`, `round_significant(a)`.

## Scope Limits

- `simulate.py` and `simulate.yaml`. The rates are assumptions and the YAML says so.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_config_loads_with_hash_and_validates`, `test_same_seed_same_cases`, `test_nil_cases_exclude_the_target_and_others_include_it`, `test_style_rates_match_config_within_two_points`, `test_hard_targets_are_oversampled_when_available`, `test_rounding_and_relative_ranges`, `test_relative_date_styles_carry_their_label`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 3 (Simulator), lines 741–1044
