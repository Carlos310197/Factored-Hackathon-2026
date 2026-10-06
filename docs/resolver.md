# Learned component: the transaction resolver

**The job.** When a customer says "me cobraron dos veces en Tienda Don José", which of *their own* transactions do they mean?
Picking the wrong one files a dispute on the wrong charge, so the system must either pick right or ask.

**Why this and not the organizer's labels.** The dataset's own targets are generator artifacts: `was_escalated` and
`sla_breached` are flat across every slice, and `is_fraud` just reproduces `fraud_score` (see the as-is report). A ranker
over the customer's own candidates is a real, bounded ML task whose labels are known by construction.

**The model.** Logistic regression over 13 features (merchant similarity, amount error, date fit, type, channel, city,
recency, …), temperature-calibrated (T = 1.34), with a "none of these" option. It never acts alone: it is evidence for
Jev's `target_transaction` decision, and code applies the thresholds. Model card:
[`agent/src/bankagent/resolver/artifacts/v1/MODEL_CARD.md`](../agent/src/bankagent/resolver/artifacts/v1/MODEL_CARD.md).

**Data and leakage.** 30,000 simulated training cases over real transaction histories; customers split by hash
(train / dev / test never share a customer) and anchor dates split by period. Dev: 300 LLM-written ES/PT messages. **Test:
150 messages written blind by a teammate**, frozen by SHA-256 (`1ab86775…9bdd`) before any evaluation.

**Systems compared, adoption rule fixed before the test run:** B0 = the production filter (no model), B1 = the resolver
alone, B2 = Jev without the resolver, P = Jev with the resolver's evidence.

| Test run (150 messages) | Wrong action, P / B2 | All cases, resolved in one step, P / B2 | Hard slice, resolved in one step, P / B2 | Paired P − B2, hard slice, repeat 1 (95 % CI) |
|---|---|---|---|---|
| **Run 1, pre-registered** (extract = gpt-oss-20b) | 0.7 % / 0.7 % | **93.8 % / 95.1 %** | 96.0 % / 95.6 % | +4.0 points (−1.3 to +10.7, not established) |
| Run 2, post-hoc (extract = Ministral 3 14B) | 0.7 % / 0.7 % | 96.0 % / 94.4 % | 98.7 % / 94.2 % | +5.3 points (+1.3 to +10.7) |

Rates are means over 3 Jev repeats; the paired difference and its CI use repeat 1 only, so the two columns are not
on the same basis. **B1 vs B0** (the learned model alone vs the production filter, run 1): B1 picks a transaction
on its own in 43 % of cases vs 28 %, with 0 wrong actions for both, but resolves fewer cases in one step (64.7 % vs
84.0 %), because it asks instead of guessing more often. That coverage gain is what the learned component proves on
its own: more cases resolved without a Jev call.

Decision under the fixed rule: **adopt P** in both runs. That means P met the rule written before the test (a wrong-action
rate no higher than B2's, and a higher hard-slice point estimate); it is **not** evidence that P is better. In the
pre-registered run, P is slightly *worse* than B2 on one-step resolution over all cases (93.8 % vs 95.1 %) and on the
nil slice, and the hard-slice difference is not established. Reports:
[`agent/resolver/reports/eval-2026-10-05.md`](../agent/resolver/reports/eval-2026-10-05.md) (run 1) and
[`agent/resolver/ministral/reports/eval-2026-10-05.md`](../agent/resolver/ministral/reports/eval-2026-10-05.md) (run 2).

**How to read run 2.** In run 1, gpt-oss-20b failed to extract mentions from 41 of the 150 test messages (27 %: truncated
or broken JSON). We compared extract models *on those same test messages*, switched to Ministral (0–1 failures, equal
extraction quality), and re-ran the test. So run 2 is **not** independent held-out evidence: the test set informed the
model choice, the two runs share their messages, and the dev set and thresholds still reflect gpt-oss extractions. Run 1
is the pre-registered result; run 2 shows what the reliability fix does. Neither run claims a production effect.

**Limits.** Training mentions are simulated, and the test writer followed style hints from the same simulator, so the test
measures text → extraction → ranking noise, not how often real customers mention each field. Portuguese messages describe
Spanish-speaking customers' histories. The nil slice (15 cases) is too small to read.

## Deployment

Trained, calibrated and evaluated on the frozen test set (two runs, both reported); switched on in the deployed agent
(`RESOLVER_ARTIFACT`, `THRESHOLDS_FILE=thresholds.v2.yaml`).
