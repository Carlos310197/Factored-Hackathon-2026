# 31 · Resolver Inference Model

**Subsystem:** Transaction resolver · **Depends on:** 26 · **Reference:** resolver plan, Task 6

## Goal

Load the JSON artifact and score candidates with a temperature-scaled softmax that includes a "none of these" option, plus `best_raw_fit` and per-feature contributions.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver
- Resolver plan #1, #2, #4 and #8 in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Training objective · resolver §4.2

- **Main model:** L2 logistic regression (scikit-learn), standardized features, trained pointwise (one row per candidate; label 1 = target).
- **Ranking probability:** a softmax of the logits within the case, divided by temperature T.
- **`best_raw_fit`:** the sigmoid of the top candidate's logit, i.e. its absolute probability of being the target. `not_in_list` training cases (all labels 0) teach this absolute fit.
- **Comparison model:** LightGBM `lambdarank`, grouped by case; `best_raw_fit` comes from a separate LightGBM binary model on the same features.

### Explainability · resolver §4.4

For logistic regression, a candidate's contribution for feature *j* is coef_j × standardized value_j. The top three contributions are stored in the decision record (§3.2), so a handoff or an audit can explain a choice ("amount within 1%, date inside range") from the execution record alone. For LightGBM, contributions come from `pred_contrib` (SHAP values).

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/model.py`, `agent/tests/test_resolver_model.py`
- Modify: `agent/tests/resolver_data.py` (append the hand-set artifact helper)

### Interfaces

- Consumes: `FEATURES`, `case_features` (Task 1).
- Produces:
  - `ARTIFACT_DIR`, `ResolverUnavailable`;
  - `Scores(probs, p_none, ranked, best_raw_fit, contributions, version)`;
  - `with_none(logits, temperature) -> np.ndarray` (length n+1; the last element is "none of these");
  - `Resolver(spec, root)` with `.load(path=ARTIFACT_DIR)`, `.raw(X) -> (logits, contributions)`, `.score(candidates, mentions) -> Scores`, and the attributes `.version`, `.kind`, `.temperature`, `.spec`, plus `.coef` for logistic regression;
  - artifact `model.json`: `{version, kind: "logreg"|"lightgbm", features, temperature, metadata, selfcheck: {X, logits}}` plus `mean/scale/coef/intercept` (logistic regression) or `model_file` (LightGBM);
  - test helper `write_logreg_artifact(path, temperature=1.0, selfcheck=True)`.

## Scope Limits

- `resolver/model.py` only, with numpy at runtime and no scikit-learn. JSON and text artifacts only; no pickle.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_scores_sum_to_one_and_rank_the_described_transaction_first`, `test_temperature_flattens_probabilities`, `test_no_mentions_gives_flat_ranking_and_low_fit`, `test_a_lone_candidate_that_does_not_fit_gets_a_low_match`, `test_missing_corrupt_or_tampered_artifact_is_unavailable`
- **A lone candidate that doesn't fit the description** (the customer has one transaction in the window, or a `not_in_list` case leaves one) must get a low match, not 1.00. Pinned in Task 6 (`test_a_lone_candidate_that_does_not_fit_gets_a_low_match`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 6 (Inference model), lines 2139–2368
