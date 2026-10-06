# Problem and targets

From the as-is diagnosis of the organizer data ([`reports/asis-2026-10-05.md`](../reports/asis-2026-10-05.md), window
2025-06-17 → 2026-06-17). Every figure there is tagged **evidence** or **synthetic artifact**, and artifacts are never used
as an argument.

![Dispute handling today: 37 h to first response, 15.5 days to resolve, 70 % still open](../reports/figures/asis-dispute-handling.png)

| Finding | Value | Tag |
|---|---|---|
| Dispute complaints (Cargo no reconocido, Cobro indebido) | 8,199 | evidence |
| Median time to first response on a dispute | **37.0 h** (n=5,022) | evidence |
| Median time to resolve a dispute | **15.5 days** (n=1,886) | evidence |
| Disputes still Open or In Process | **69.8 %** (n=8,199) | evidence |
| Disputes arriving by call center | 50.7 % | evidence |
| Non-first-contact-resolution contacts per 100 contacts: Queja vs Transaccional | **9.6 vs 2.9** (17.1 % × (1 − 0.436) vs 34.9 % × (1 − 0.916)) | evidence |
| In-scope contacts per month (Transaccional + disputes) | 7,372 | evidence |
| Phone share of all contacts | 85.0 % | evidence |

**Where the pain is.** Transaction inquiries are already resolved at first contact 92 % of the time; automating them alone
would not move much. The pain is dispute intake: 37 hours before anyone answers and 70 % of cases still open. This system
takes a dispute from the first message to a filed, read-back-verified record in one conversation, or to a complete,
structured handoff packet when a human must decide. Transaction inquiries are in scope because a dispute needs them: you
can't dispute a charge you can't find.

**What success looks like.** Measurable targets, each tied to a metric the evaluation reports with its denominator:

| Target | Today | Measured by |
|---|---|---|
| Dispute intake: median ≤ 5 min from the customer's first message to a filed, read-back-verified record, in one conversation | 37 h median to a *first response* (a different endpoint: today nothing is filed by then) | `decision_records`: time from the first turn to `verify:tool` |
| Unsafe outcomes: 0 observed, reported as k/N with the upper confidence bound, never as "zero risk" | — | eval classifier, unsafe outcomes over all in-scope cases |
| 100 % of human handoffs arrive as a complete `handoff.v1` packet (request, verified facts, actions, evidence, open questions) | free-text complaints | packet schema validation + eval judge |
| Safe automated resolution of in-scope inquiries and eligible disputes: target set after a pilot; we report the rate with its CI | — | eval, safe automated resolution over all in-scope cases |
| Wrong-transaction disputes ≤ 2 % at the resolver's threshold (**measured: 1 of 150 = 0.7 %, exact 95 % CI 0.02–3.7 %, so ≤ 2 % is not yet shown; P equals B2 on this**) | — | resolver evaluation on the frozen human-written test set |

**What we don't claim.** That customers want chat (85 % of contacts are phone today), any savings figure, or improvement
over the legacy process. Those need a pilot.

## Measured evaluation

| Part | Status |
|---|---|
| Evaluation (`eval/`) | Held-out run on 2026-10-05 ([`reports/eval-2026-10-05.md`](../reports/eval-2026-10-05.md)): a frozen set of 120 goals × 3 repetitions = 360 conversations with simulated ES/PT customers, against the live agent. Correct outcome **354/358** (98.9 %), safe automated resolution **182/185** (98.4 %), missed transfers **0/65**, unnecessary transfers **1/78**, unsafe outcomes **2/358** (both disclosed with their cause), turn latency p50 3.7 s / p95 7.8 s. The LLM judge is not validated yet (no human labels, no κ), so no headline number uses it; cost is incomplete until Jev has a published price |

We report what we measured. We don't report numbers we haven't run.
