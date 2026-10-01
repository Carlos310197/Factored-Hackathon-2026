# Transaction resolver design: the learned component

Date: 2026-09-29 · Status: draft for review · Owner: Carlos (test set: Andrés)
Related: `docs/superpowers/specs/2026-09-29-agent-core-design.md` (§4.1 `target_transaction`, §6.1 `extract`, §7.4 decision records), `docs/superpowers/specs/2026-09-26-data-pipeline-design.md` (serving contract §5.3–5.4)

## 1. Purpose and scope

The brief requires at least one learned component, evaluated against an appropriate baseline, with valid labels, leakage prevention and justified representations, metrics, thresholds and splits. This spec defines that component: a **transaction resolver**. It is a classic ML ranker that scores which of a customer's transactions they are describing. Jev reads those scores as evidence when it answers `target_transaction`.

**In scope:**
- the resolver's features, model, training data (simulated), dev and test sets;
- the evaluation of four systems on the same held-out cases;
- the resolver's integration into the agent core.

**Out of scope:** the system-wide evaluation (safe automated resolution, containment, escalation quality, unsafe outcomes, cost per case). That gets a separate spec, which reuses this spec's test-set conventions (§5).

**Decisions already taken (2026-09-29):**

| Topic | Decision |
|---|---|
| Learned component | Transaction resolver (ranker) over the customer's 60-day candidates |
| Who decides | **Jev decides `target_transaction`**; ranker scores are added to its state as evidence. Code applies the thresholds. |
| Training data | Simulated structured mentions over real histories. No text and no LLM in training. |
| Dev set | 300 Claude-written ES/PT messages passed through the real `extract` |
| Test set | 150 messages written blind by Andrés (75 ES / 75 PT) |
| Model | L2 logistic regression (main) vs LightGBM `lambdarank` (comparison) |
| Tracking | MLflow, local file store; the promoted run is copied into committed metadata |

## 2. Facts this design rests on

Profiled from the local drop on 2026-09-29.

**No organizer label supports a learned model.** Each candidate was checked:

| Candidate label | Finding |
|---|---|
| Transcript intent | 26,552 transcripts in 2026 but only 42 distinct `customer_text` values, all balance inquiries. `detected_intents` is `consulta_general` (95%) or empty. |
| `is_fraud` | 0.09% positive (407 / 448,641, Mar–Jun 2026). The rate is flat (0.06–0.24%) across status, type, channel, response code, domestic vs abroad, and amount. Every row with `fraud_score` > 30 is fraud, which catches 78% of fraud. A model would only reproduce `fraud_score`. |
| `was_escalated` | 9.8–10.5% in every reason, sentiment, channel and wait-time bucket (686k interactions) |
| `sla_breached` | 19–22.5% in every priority, category and channel (67k complaints). `compensation_granted` is 0% everywhere. |

The generator appears to assign these outcomes at fixed rates, independent of every other field. This goes in the report as evidence for the component choice.

**Resolving the target transaction is easy for most customers and hard in a tail.** In the 60-day window ending 2026-06-17 (104,082 customers):
- transactions per customer: median 2, p90 5, max 16; no customer exceeds the 40-candidate limit;
- `merchant_name` appears only on purchases (95% of them), with 24 distinct merchants. Withdrawals, transfers, payments, deposits and adjustments (about 70% of rows) have none;
- 2% of customer–merchant pairs repeat within the window.

Consequence: the component's value is **calibrated abstention on the hard tail**, not headline accuracy. The report shows the easy and hard slices separately (§5.2).

## 3. Architecture

```
customer message ──▶ extract (Claude, agent core §6.1)
                        mentions: merchant, amount, currency, date_from/to, type_hint, channel_hint, city
                                  │
60-day candidates ──▶ resolver.score()  (features.py → model.json)
                        {transaction_id: prob}, best_raw_fit, per-feature contributions
                                  │
                   Jev understand.v2: target_transaction reads the message + candidates annotated "· match 0.93"
                                  │
                   code thresholds (decisions/thresholds/v2.yaml) → act | ask customer (top 3) | not_in_list
```

### 3.1 Components (`bankagent/resolver/`)

| Unit | Responsibility | Used by |
|---|---|---|
| `features.py` | Pure function `(mentions, candidate, context) → feature vector` (§4.1). The single source of features for both training and serving. | train, serve |
| `model.py` | Loads the artifact; `score(candidates, mentions, as_of) → {probs, best_raw_fit, contributions}`. Logistic-regression inference is a dot product and a softmax, with no scikit-learn at runtime. | agent |
| `simulate.py` | Generates training and simulated-validation cases (§5.1). Rates live in `resolver/simulate.yaml`. | offline |
| `splits.py` | Customer-hash and anchor-date split rules, plus the hard-slice rule (§5.2) | offline, tests |
| `train.py` | Hyperparameter search, model selection, calibration, MLflow logging, promotion | offline |
| `make_dev_set.py` | Builds the dev set: simulator picks → Claude writes the message → real `extract` | offline |
| `make_test_sheet.py` | Builds the CSV Andrés writes the test set from | offline |
| `evaluate.py` | Runs B0/B1/B2/P on a set and writes the report (§6) | offline |

`train.py`, `simulate.py`, `make_*` and `evaluate.py` are never imported by the agent.

**Artifact:** `resolver/artifacts/v1/model.json` contains:
- feature list, scaler, coefficients, intercept, temperature;
- metadata: serving `run_id`, seed, `simulate.yaml` hash, git SHA, MLflow run id, dev metrics.

If LightGBM wins (§4.3), its native text model file goes alongside `model.json`, and `lightgbm` becomes a runtime dependency. JSON and text only; no pickle. `resolver/MODEL_CARD.md` is committed next to it.

### 3.2 Changes to the agent core (all additive)

1. **`extract` schema:** `mentions` gains three nullable fields: `type_hint` (`purchase|withdrawal|transfer|payment|deposit`), `channel_hint` (`atm|pos|app|web|branch`), and `city`. This must land in agent-core Task 9 before the dev set is built.
2. **`understand` node:** calls `resolver.score()` after `extract` and before building the Jev request.
3. **Jev question set `understand.v2`:**
   - `describe_txn` appends `· match <p>` (two decimals);
   - `target_transaction` gets one added instruction line: "The match score comes from structured matching of amount, date, merchant, type, channel and city; it ignores the wording. Use it as evidence, not as the answer."
   - Every other question is unchanged.
4. **Decision records:** a new `kind: model` entry holding the resolver version, the per-candidate probabilities, `best_raw_fit`, and the top three feature contributions per candidate.
5. **Failure:** any resolver exception → no scores for this turn, one `kind: error` record, and the Jev-alone path (`understand.v1` formatting). The turn is never blocked.
6. **`select_candidates`** is unchanged and serves as baseline B0.

**Training data source:** `fct_transaction` from one pinned serving `run_id` (the curated export), so every model version traces to the pipeline's `RUN_MANIFEST`.

## 4. Model

### 4.1 Features

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

### 4.2 Training objective

- **Main model:** L2 logistic regression (scikit-learn), standardized features, trained pointwise (one row per candidate; label 1 = target).
- **Ranking probability:** a softmax of the logits within the case, divided by temperature T.
- **`best_raw_fit`:** the sigmoid of the top candidate's logit, i.e. its absolute probability of being the target. `not_in_list` training cases (all labels 0) teach this absolute fit.
- **Comparison model:** LightGBM `lambdarank`, grouped by case; `best_raw_fit` comes from a separate LightGBM binary model on the same features.

### 4.3 Selection and calibration

1. **Hyperparameter search runs on simulated validation cases** from dev customers and dev anchors:
   - logistic regression: C ∈ {0.01, 0.1, 1, 10, 100};
   - LightGBM: `num_leaves` ∈ {7, 15, 31}, `learning_rate` ∈ {0.05, 0.1}, `n_estimators` ∈ {200, 500};
   - selected by hard-slice top-1 accuracy.
2. **The two finalists are compared on the 300-message real-text dev set**, by hard-slice top-1 accuracy. Ties within 2 points go to logistic regression (simpler and exactly explainable). The small dev set is only used for this final choice, for calibration and for thresholds.
3. **Temperature T** is fitted on dev by minimizing negative log-likelihood.
4. **Reported calibration:**
   - expected calibration error (10 equal-width bins);
   - a reliability diagram before and after calibration;
   - the ROC AUC of `best_raw_fit` for detecting `not_in_list`.

### 4.4 Explainability

For logistic regression, a candidate's contribution for feature *j* is coef_j × standardized value_j. The top three contributions are stored in the decision record (§3.2), so a handoff or an audit can explain a choice ("amount within 1%, date inside range") from the execution record alone. For LightGBM, contributions come from `pred_contrib` (SHAP values).

### 4.5 Tracking

- MLflow with a local file store (`mlruns/`, gitignored). Every `train.py` run logs:
  - params: seed, `simulate.yaml` hash, serving `run_id`, feature list, hyperparameters;
  - dev metrics;
  - the artifact.
- `train.py --promote <run_id>` writes `resolver/artifacts/v1/` and refreshes the metrics in `MODEL_CARD.md`. Those files are committed.

## 5. Data

### 5.1 Simulator (`simulate.py`, `simulate.yaml`)

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

### 5.2 Splits and slices (`splits.py`)

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

### 5.3 Dev set (300 cases: 150 ES, 150 PT)

1. `make_dev_set.py` draws dev-split cases through the simulator: history, target, style.
2. Claude (the `compose` model) writes a customer message in ES or PT from the target transaction's fields and the style instructions. It is never shown the other candidates.
3. The real `extract` processes the message, and its output is cached.
4. The label (target `transaction_id` or `not_in_list`) is known by construction.
5. Carlos reviews 30 messages for realism, and any that are unusable are regenerated. The regeneration count is reported.
6. Stored in `resolver/data/dev_v1.jsonl`, committed. Transaction fields only, no customer PII (the curated marts contain none).

Sending curated transaction fields to Bedrock falls under the same open data-use approval as the agent itself (agent-core §12).

### 5.4 Test set (150 cases: 75 ES, 75 PT)

1. `make_test_sheet.py` writes `resolver/data/test_sheet_v1.csv` from test-split cases. Each row contains:
   - the candidates;
   - a marked target, or, for 15 rows, the note "describe a transaction that is NOT in this list";
   - a language;
   - a style hint (e.g. "vague about the amount", "only the date and the channel").

   75 rows are hard, 60 easy and 15 `not_in_list`.
2. Andrés writes each message as a customer would, without seeing the model, the simulator rates or the dev set.
3. The completed file `resolver/data/test_v1.jsonl` is committed, and its SHA-256 is recorded in this spec's changelog (§9) before any evaluation.
4. It is evaluated **once**, after every dev decision is frozen (§6.4). A rerun is allowed only to fix a bug, and is disclosed in the report together with both results.
5. **Human ceiling:** after the test run, Carlos resolves 40 test messages blind, with candidates shown and no target marked. His accuracy is reported as the human ceiling.

## 6. Evaluation (`evaluate.py`)

### 6.1 Systems

| ID | System | Acts when | Otherwise |
|---|---|---|---|
| B0 | Heuristic: `select_candidates` filter | mentions present and exactly one candidate passes the filter | ask the customer, showing up to 3 candidates that pass, newest first (newest overall if none pass) |
| B1 | Ranker alone | top prob ≥ τ **and** `best_raw_fit` ≥ φ | `best_raw_fit` < φ → `not_in_list`; else ask with the top 3 |
| B2 | Jev alone (`understand.v1`) | the agent-core §4.3 form: top ≥ t and margin ≥ m | ask with Jev's top 3; Jev's `not_in_list` / `ambiguous` as answered |
| **P** | Jev + ranker (`understand.v2`) | same form as B2, with its own t and m | same as B2 |

All systems read the same cached `extract` output per message, so only the resolution step differs. Jev runs 3 times per case for B2 and P, and results are reported as the mean and the min–max range.

### 6.2 Outcomes and metrics

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

### 6.3 Thresholds

For each system, on dev: choose the thresholds with the highest coverage subject to a dev wrong-action rate ≤ 2%.
- B1 searches τ and φ over [0.3, 0.99] in steps of 0.01.
- B2 and P search t over [0.5, 0.99] and m over [0, 0.5], in steps of 0.01.

The dev coverage-vs-accuracy curve is published, with the chosen point marked. P's values are written to `decisions/thresholds/v2.yaml`.

### 6.4 Adoption rule (fixed before the test run)

- **P replaces B2 in the agent** if both hold on test:
  1. its wrong-action rate is not higher than B2's (point estimate);
  2. its hard-slice resolved-within-one-step is higher than B2's.
- **Otherwise** the report states that the ranker did not help, and the agent keeps `understand.v1` with the agent-core thresholds.
- The decision is recorded in the report and in this spec's changelog.

### 6.5 Error analysis

Every act-wrong or failed case on test gets one cause:
- `extract` missed or mangled a field;
- a description style the simulator does not model;
- the ranker ranked the target below another candidate;
- Jev overrode a correct top-ranked candidate;
- the message is genuinely ambiguous (also failed in the human-ceiling pass).

The report includes counts per cause and five worked examples.

### 6.6 Report

`resolver/reports/eval-<date>.md` contains:
- the system table;
- slice tables with confidence intervals;
- the reliability diagram and coverage curve (PNG);
- the error analysis;
- the human ceiling;
- versions: artifact, question sets, thresholds, prompts, models;
- the adoption decision.

The slides quote this report only.

## 7. Testing

**Unit tests (pytest, offline):**
- **`features.py`:**
  - an accent-insensitive merchant matches;
  - the local vs USD amount path;
  - inside vs outside the date range;
  - a hint mismatch gives −1;
  - an absent mention gives 0.
- **`simulate.py`:**
  - the same seed produces identical output;
  - style rates in 10k draws fall within ±2 points of `simulate.yaml`;
  - `not_in_list` cases exclude the target.
- **`splits.py`:**
  - no customer and no anchor date overlaps between splits;
  - the hard-slice rule on crafted histories.
- **`model.py`:**
  - probabilities sum to 1 within a case;
  - temperature is applied;
  - a loaded artifact reproduces its recorded scores on 20 fixed rows;
  - a missing or corrupt artifact raises `ResolverUnavailable`.

**Graph scenarios (stubbed Jev and Claude, agent-core harness):**
- `understand.v2` state contains the match scores;
- a `kind: model` decision record is written;
- a `ResolverUnavailable` turn continues on the `understand.v1` path with a `kind: error` record.

## 8. Definition of done

- `train.py` reproduces the promoted artifact from its seed and serving `run_id`; the run is in MLflow.
- `resolver/artifacts/v1/` and `MODEL_CARD.md` are committed. The model card covers data, features, splits, dev metrics, calibration and limitations.
- `dev_v1.jsonl` and `test_v1.jsonl` are committed, the test hash is recorded before evaluation, and the test set was evaluated once.
- `resolver/reports/eval-<date>.md` is complete (§6.6).
- The adoption decision is recorded; `thresholds/v2.yaml` and `understand.v2` are active only if P won.
- Unit and scenario tests pass in CI.

## 9. Schedule, risks and changelog

**Schedule** (submission 2026-10-05):

| Day | Work | Depends on |
|---|---|---|
| 09-30 | `features.py`, `splits.py`, `simulate.py`; `make_test_sheet.py` → **sheet sent to Andrés** | local drop |
| 10-01 | training, MLflow, `model.py` | — |
| 10-02 | dev set, calibration, thresholds | agent-core Task 9 with the hints; data-use approval |
| 10-03 | agent integration (`understand.v2`); **test set due from Andrés**; freeze | agent-core Tasks 8 and 10 |
| 10-04 | single test run, report, error analysis, human ceiling | Jev live |

**Risks:**
- **Andrés's time** (about 3–4 hours for 150 messages). Fallback: 100 messages, with the n disclosed.
- **Jev unavailable on 10-04.** B0 vs B1 is still a valid learned-vs-baseline result; B2 and P are reported as not run.
- **The `extract` hints miss Task 9.** The dev set cannot be built until they land.
- **Simulator mismatch.** The dev and test sets are real text, so a mismatch shows up as a gap between the simulated-validation and dev metrics. It is reported, not hidden.
- **Portuguese.** PT messages describe the histories of Spanish-speaking customers. This is reported as a data limitation.

**Changelog:**
- 2026-09-29: draft.
- Test-set SHA-256: to be filled at freeze (§5.4).
- Adoption decision: to be filled after the test run (§6.4).
