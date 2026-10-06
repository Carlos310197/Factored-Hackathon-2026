# Limitations and before production

**Known limitations**
- **Orphan foreign keys:** a row whose product or customer doesn't exist fails the daily build, so the export is skipped and
  the agent keeps reading the last good serving run; but the Snowflake curated mart does get the row (live fixture proof,
  `tests/test_fixture_drop.py` phase 3b). Before production: quarantine orphans in `typed_transactions`.
- **Portuguese:** the bank has no Portuguese-speaking customers (customers are in México, Colombia and Argentina). PT
  support is conversational; PT test cases are written by the team, with no native-speaker review.
- **Human-review disputes** (over 500 USD, fraud score over 30, unauthorized) are recorded as `pending_review` **without**
  asking the customer to confirm. This is deliberate: the record is a draft for a specialist, not a filed dispute; no
  money moves, the customer is told a specialist will review it, and the specialist resolves the case from the
  console. The cost is a draft the customer never approved.
- **Confirmation** from the card's button is a deterministic token (`confirm:<card_hash>`, checked by equality in code);
  a typed "sí, confirmo" is still Jev's reading of free text, bound to the same card hash.
- **Timeouts:** each LLM call uses its role's timeout from `llm/models.yaml` (extract 10 s, compose 20 s) with no hidden SDK
  retry; a compose call is capped at what is left of the 15 s turn budget, and no regeneration starts once it is spent.
  Jev calls time out at 3 s with one retry, so the closing verification can add up to 6 s: a turn ends within about 21 s,
  under the BFF's 25 s (`test_worst_case_turn_fits_inside_the_bff_wait`).
- **Data freshness:** the organizer drop ends on 2026-06-17; freshness is recorded but doesn't gate the build. Customers see
  the "data as of" date.
- **Synthetic data:** escalation and SLA rates, wait times, CSAT and agent load are generator artifacts and are not used to
  argue for this system.
- **Hosting:** one Fargate Spot task behind CloudFront (HTTPS with the default CloudFront certificate, no custom domain);
  a Spot interruption means 1–2 minutes of downtime.
- **Spend cap is per session only:** the demo identities and the mock IdP are public, so anyone can drive Bedrock and
  Jev calls (Bedrock bills to the account that owns the Bedrock role). A session stops after 30 turns with a fixed reply
  and no model call, and an alarm fires when sessions keep hitting the cap; but a new login starts a new session, so the
  real brakes are the IdP throttle (10 req/s), the Lambda concurrency limit and the AWS Budget alert.
- **Audit records** (`decision_records`) are written best-effort: a failed write is logged, not retried, and does not stop
  the turn.
- **Staff login** is a password only (no second factor, no lockout beyond the IdP's 10 req/s throttle); staff
  credentials are not published.
- **Mock identity:** demo passwords are stored as unsalted SHA-256 hashes; staff reads of a conversation are not audited.
- **Pipeline:** the daily run re-exports even when nothing new loaded, and RAW is never purged (details in
  [`docs/data-pipeline.md`](data-pipeline.md)).

**Before production**
- A real identity provider (HTTPS and `Secure` cookies are in place), with a second factor and lockout for staff sign-in.
- Notifications wired to an on-call channel (today: one email address), and alarms on DynamoDB throttling and AgentCore errors.
- A load test that finds the saturation point (today: 10 concurrent customers measured).
- A native Portuguese speaker's review of the PT replies and test cases.
- A per-customer turn cap (today it is per session), and a budget alert in the account that pays for Bedrock and on Jev.
- A calibrated threshold set. The current Jev thresholds were set by hand; [`reports/threshold-check-2026-10-05.md`](../reports/threshold-check-2026-10-05.md)
  measures them on the held-out run: unauthorized use, legal threat and asks-for-human catch every real case, with a clean
  gap between real cases and the rest; injection scores overlap (one soft phrasing scored 0.39–0.47 and was still refused
  by the tool layer). Choosing new values needs a separate calibration set, not the held-out run.
- Least-privilege CI roles (the deploy role is an administrator today) and branch protection on `main`.
- Retention rules for disputes and handoffs; an audit record of staff reads.
- A pilot that measures intake time and handoff completeness against the 37-hour baseline.
