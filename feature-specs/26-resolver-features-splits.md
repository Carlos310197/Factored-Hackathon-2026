# 26 · Resolver Features and Splits

**Subsystem:** Transaction resolver · **Depends on:** 12, 16 · **Reference:** resolver plan, Task 1

## Goal

Add the resolver dependencies and write the shared pure feature function and the deterministic split and hard-slice rules.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver
- Resolver plan #3 (13 features) in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Features · resolver §4.1

There is one row per candidate. A feature is 0 when the customer did not mention the field it needs, so an absent mention is neutral.

| Feature | Definition |
|---|---|
| `merchant_sim` | `rapidfuzz` token-set ratio / 100, after lower-casing and removing accents |
| `merchant_missing_on_cand` | 1 if the customer named a merchant and this candidate has none |
| `amount_log_err` | min(abs(ln(m / amount)), abs(ln(m / amount_usd))), capped at 3 |
| `amount_rank` | the candidate's rank by `amount_log_err` within the case, divided by the number of candidates |
| `days_outside` | log1p of the days between `process_date` and the mentioned range (0 inside it) |
| `type_match`, `channel_match`, `city_match` | +1 match, −1 mismatch, 0 no hint (city by fuzzy ratio ≥ 0.85) |
| `recency_pct` | the candidate's recency rank / number of candidates |
| `is_purchase` | 1 for `Purchase` |

Values that are constant within a case, such as the number of candidates or which fields were mentioned, cannot change a within-case ranking, so they are not model features.

### Splits and slices (`splits.py`) · resolver §5.2

- **Customer split:** first byte of `sha256(customer_id)`, mod 10 → 0–7 train, 8 dev, 9 test.
- **Anchor dates:**
  - train: 2023-09-01 … 2025-09-30;
  - dev: 2025-10-01 … 2026-01-31;
  - test: 2026-02-01 … 2026-06-17.
- **Leakage:** no customer and no time period appears in more than one split. Any history with fewer than 2 candidates is skipped, because there is nothing to resolve.
- **Hard slice** (a deterministic rule on history and target, computed before any model runs). A case is hard if any of these hold:
  - the target has another candidate of the same `transaction_type`, and neither has a merchant;
  - the target has another candidate with the same merchant;
  - another candidate's amount is within 10% of the target's.

  All other cases are easy. `not_in_list` cases are reported as their own slice.

## Implementation

### Files

- Modify: `agent/pyproject.toml`, `agent/uv.lock`
- Create: `agent/src/bankagent/resolver/__init__.py`, `agent/src/bankagent/resolver/features.py`, `agent/src/bankagent/resolver/splits.py`, `agent/tests/resolver_data.py`, `agent/tests/test_resolver_features.py`

### Interfaces

- Consumes: nothing from this plan.
- Produces:
  - `FEATURES: tuple[str, ...]` (13 names), `TYPE_HINTS`, `CHANNEL_HINTS`;
  - `fold(s) -> str`;
  - `mentions_present(m) -> bool`;
  - `case_features(mentions: dict | None, candidates: list[dict]) -> np.ndarray` with shape (n, 13). Candidates are newest first.
  - `customer_split(customer_id) -> "train" | "dev" | "test"`, `ANCHORS: dict[str, (date, date)]`, `WINDOW_DAYS = 60`;
  - `case_slice(candidates, target_id | None) -> "easy" | "hard" | "nil"`;
  - test helpers `tests/resolver_data.py::txn(i, day=..., merchant=..., amount=..., ttype=..., channel=..., city=..., currency=..., amount_usd=...)` and `mentions(**kw)`.

## Scope Limits

- `resolver/features.py`, `resolver/splits.py` and their tests. The feature function is the single source for training and serving.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_fold_strips_accents_case_and_spaces`, `test_accent_insensitive_merchant_match`, `test_merchant_named_but_candidate_has_none`, `test_amount_uses_the_closer_of_local_and_usd`, `test_amount_error_is_capped_and_ranked`, `test_days_outside_the_range`, `test_hints_are_signed`, `test_absent_mentions_are_zero_except_structure`, `test_customer_split_is_deterministic_and_covers_three_splits`, `test_anchor_ranges_do_not_overlap`, `test_hard_slice_rule`, `test_hints_tolerate_case_and_whitespace`, `test_reversed_date_range_is_the_same_range`, `test_degenerate_amounts_are_neutral_not_errors`
- **Hints from `extract` with odd case or whitespace** (`" ATM "`, `"Withdrawal"`) must still match. Pinned in Task 1 (`test_hints_tolerate_case_and_whitespace`).
- **A reversed or malformed date range from `extract`** must be read as the same range, or ignored, never crash. Pinned in Task 1 (`test_reversed_date_range_is_the_same_range`; malformed dates in `test_days_outside_the_range`).
- **Degenerate amounts:** a mentioned amount of 0, a negative number, a boolean or a string; a candidate amount of 0 or `None`; a non-USD row without `amount_usd`. All must be neutral (not mentioned, or maximum error), never an exception. Pinned in Task 1 (`test_degenerate_amounts_are_neutral_not_errors`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 1 (Dependencies, features and splits), lines 149–516
