# 34 · Finalist Choice, Calibration, Promotion and Model Card

**Subsystem:** Transaction resolver · **Depends on:** 32 · **Reference:** resolver plan, Task 9

## Goal

Choose between the two finalists on the dev set, fit the temperature, promote the artifact and write the model card.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core, Transaction Resolver
- `context/architecture-context.md` → Transaction Resolver

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

*From resolver §4.3:*

2. **The two finalists are compared on the 300-message real-text dev set**, by hard-slice top-1 accuracy. Ties within 2 points go to logistic regression (simpler and exactly explainable). The small dev set is only used for this final choice, for calibration and for thresholds.
3. **Temperature T** is fitted on dev by minimizing negative log-likelihood.
4. **Reported calibration:**
   - expected calibration error (10 equal-width bins);
   - a reliability diagram before and after calibration;
   - the ROC AUC of `best_raw_fit` for detecting `not_in_list`.

## Implementation

### Files

- Create: `agent/src/bankagent/resolver/finalize.py`, `agent/tests/test_resolver_finalize.py`

### Interfaces

- Consumes: `Resolver`, `with_none`, `ARTIFACT_DIR` (Task 6); `case_metrics`, `search` (Task 7).
- Produces:
  - `TIE_MARGIN = 0.02`;
  - `fit_temperature(resolver, rows) -> float` (NLL of the "none of these" softmax over every dev row);
  - `choose_finalist(finalists: {family: {"path", ...}}, rows) -> (family, {family: metrics})`;
  - `promote(src, temperature, extra, dst=ARTIFACT_DIR) -> Resolver`;
  - `write_model_card(dst, resolver, family_metrics, dev_after) -> Path`.

## Scope Limits

- `finalize.py` and its tests. The real promotion happens in unit 38.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_choose_finalist_prefers_logreg_on_near_ties`, `test_temperature_lowers_dev_nll`, `test_promote_writes_a_loadable_artifact_and_card`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-transaction-resolver.md`: Task 9 (Finalist choice, calibration, promotion and the model card), lines 2822–3022
