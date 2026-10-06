# Before and after: what the next person receives

**Today a disputed charge reaches a person as a category, a priority and a one-line label that is the same for every
case; from the agent it arrives as the customer's words, the signals that routed it, the checks that ran and the
question still open.**

The "before" is a real row from the organizer's complaint table. The "after" is a real `handoff.v1` packet the deployed
agent wrote on 2026-10-06 (UTC) for the `/demo` scenario *unauthorized → handoff*. Ids are redacted (`CLI-…`, `S-…`).
The data is the organizers' synthetic dataset.

## Side by side

**Today: one "Cargo no reconocido" complaint** (`data/complaints.parquet`, window 2025-06-17 → 2026-06-17; picked as a
typical row: the most common channel, the most common priority and status, first response near the median)

| Field | Value |
|---|---|
| `complaint_id` / `customer_id` | `CMP-…` / `CLI-…` |
| `case_type` | Claim |
| `category` / `subcategory` | Transactions / Cargo no reconocido |
| `reception_channel` | Call Center |
| `description` | "Queja relacionada con transactions" |
| `affected_product_id` | `PRD-…` (which card, not which charge) |
| `origin_interaction_id` | empty |
| `claimed_amount` / `currency` | 4032.91 / USD |
| `priority` | Medium |
| `status` | In Process |
| `assigned_agent_id` | `AGT-…` |
| `creation_date` → `first_response_date` | 2025-07-04 00:41 → 2025-07-05 09:41 (33 h) |
| `resolution_date`, `resolution_days`, `resolution` | empty |
| `sla_breached` | False |

**From the agent: one `handoff.v1` packet** (live, customer message "No reconozco un cargo en mi tarjeta, yo no hice
esa compra")

```json
{
  "schema_version": "handoff.v1",
  "handoff_id": "HND-…",
  "created_at": "2026-10-06T01:24:28Z",
  "status": "open",
  "session_id": "S-…",
  "customer_id": "CLI-…",
  "language": "es",
  "data_as_of": "2026-06-17",
  "priority": "critical",
  "reason_codes": ["reports_unauthorized_use"],
  "customer_request": {
    "original": "No reconozco un cargo en mi tarjeta, yo no hice esa compra",
    "en": "Unrecognized card charge: I don't recognize this charge on my card—I didn't make this purchase."
  },
  "verified_facts": [],
  "actions_taken": [],
  "decisions": [
    {"question": "intent", "value": "dispute_charge", "p": 1, "question_set": "understand.v2", "thresholds": "thresholds.v2"},
    {"question": "reports_unauthorized_use", "value": 0.97, "question_set": "understand.v2", "thresholds": "thresholds.v2"}
  ],
  "policy_checks": [],
  "open_questions": ["Could you provide the date and amount of the unrecognized charge?"],
  "transcript_ref": "session:S-…"
}
```

The `en` gloss is shown with markdown removed. As stored, the extract model wrapped it in `**…**` and `*…*`; that is
an output artefact being fixed separately, not part of the contract.

## Why each part matters

| Question the next person has | Today's row | The packet |
|---|---|---|
| What did the customer actually say? | Nothing. `description` is one of 5 fixed strings across all 67,095 complaints; every one of the 12,297 "Cargo no reconocido" rows reads "Queja relacionada con transactions" | `customer_request.original`, verbatim, plus an English gloss for staff who don't read Spanish |
| Where is the conversation? | Nowhere. `origin_interaction_id` is empty in 67,095 of 67,095 rows | `transcript_ref` points to the session; the console's Conversation tab shows it and a person can take over the chat |
| Why is it with me, and how sure is that? | A priority label with no reason attached | `reason_codes` plus `decisions`: Jev read intent `dispute_charge` (p = 1) and `reports_unauthorized_use` at 0.97, against a handoff threshold of 0.50 (`decisions/thresholds.v2.yaml`). Each decision names its question set and threshold version |
| How urgent is it? | `priority`, set by a process the data doesn't show | `priority` is computed in code from the reason codes: an unauthorized-use report is `critical` (`handoff/packet.py`, `priority_for`) |
| What is already known for certain? | A claimed amount, when present (1,393 of 4,193 rows in the window) | `verified_facts`: each fact is a tool receipt with its `receipt_id`. Empty here, see below |
| What was already done? | Nothing recorded until resolution | `actions_taken`, each with the receipt of the write |
| Which rules were checked? | None recorded | `policy_checks`: each rule of the dispute policy by name, pass or fail, with the detail |
| What is still missing? | Not recorded | `open_questions` (at most 3): here, the date and amount of the charge |
| How fresh is the data behind it? | Not recorded | `data_as_of` |

### Why this packet has no facts or checks

An unauthorized-use report goes to a person at `critical` priority by policy (`human_review_reasons: [unauthorized]`
in `policy/dispute_policy.yaml`). The routing does not hold the customer back to pin down a transaction first: if the
message names one, the agent resolves it and drafts the dispute for review; if not, it hands off straight away
(`decisions/routing.py`, the escalation loop). This message named no merchant, date or amount, so no transaction was
bound, no policy rule ran, and nothing was written. The packet says so honestly: empty lists, and an open question
asking for exactly what is missing.

When a transaction *is* identified, the same schema carries the evidence. Two examples:

- **Live, 2026-10-05** (`agent/docs/smoke-results.md`, scenario 6): "No reconozco el cargo de Tienda Don José del 4 de
  junio, alguien usó mi tarjeta" produced a `critical` packet with 3 verified facts (the transaction, the drafted
  dispute, its read-back receipt), 1 action (`dispute_drafted`), 2 decision refs, 5 policy checks and 3 open questions.
- **Offline, deterministic** (`agent/tests/test_graph_paths.py::test_over_limit_dispute_goes_to_human_review_without_confirmation`):
  "Me cobraron de más en Electrónica Max" on an 800 USD purchase in the test fixture goes to `human_review` with reason
  `amount_over_limit`, `medium` priority, 3 verified facts with receipt ids, the action `dispute_drafted → pending_review`,
  and these policy checks:

  | Rule | Result | Detail |
  |---|---|---|
  | `status_disputable` | pass | Approved |
  | `type_disputable` | pass | Purchase |
  | `within_window` | pass | 5 days |
  | `not_already_disputed` | pass | |
  | `automated_eligible` | **fail** | `amount_over_limit` |

  The failed rule is the reason a person sees it. The row in "Today" above claims 4032.91 USD, which would take this
  path too.

## Where a judge clicks

- Staff console: `/login?staff=1`, then `/agent` (the handoff queue). Open a case: the **Packet** tab shows the fields
  above (customer request, verified facts with receipt ids, actions, "why it came to you" with the crossed Jev
  signals, policy checks failed first, open questions); the **Conversation** tab shows the chat.
- Decision trace: `/trace/<session>` lists every step of every turn (`understand:jev`, `understand:route`,
  `check_eligibility:policy`, `handoff:tool`, …) with Jev probabilities against their thresholds and the policy rules
  that ran (failed first). The full record, including the policy version, is in `decision_records`. The case's
  **Trace** tab in the console shows the same.
- Demo stage: `/demo`, act 3, scenario *ES · unauthorized → handoff* reproduces the packet above.

## The numbers behind "today"

All from the organizer complaint table (`data/complaints.parquet`, the local cache of the drop), queried with DuckDB.
The window figures match the published as-is report ([`reports/asis-2026-10-05.md`](../reports/asis-2026-10-05.md),
section 4) exactly.

| Fact | Value | n | Window |
|---|---|---|---|
| Distinct `description` values | 5 | 67,095 complaints | all (2023-06-17 → 2026-06-17) |
| `origin_interaction_id` empty | 100 % | 67,095 | all |
| "Cargo no reconocido" complaints | 4,193 (18.6 % of complaints) | 22,552 | 2025-06-17 → 2026-06-17 |
| "Cargo no reconocido": median time to first response | 37.0 h | 2,588 with a first response | same |
| "Cargo no reconocido": median resolution time | 15.0 days | 974 with `resolution_days` | same |
| "Cargo no reconocido": still Open or In Process | 69.6 % | 4,193 | same |
| "Cargo no reconocido": `claimed_amount` filled | 33.2 % (1,393) | 4,193 | same |
| Both dispute subcategories (adds "Cobro indebido"): count, first response, resolution, backlog | 8,199; 37.0 h (n=5,022); 15.5 days (n=1,886); 69.8 % | 8,199 | same, as published |

Not used as an argument: `sla_breached` (20.6 % for "Cargo no reconocido", n=4,193) and `priority`. The as-is report
tags SLA breach as a synthetic artifact: it is flat across all 15 category × priority buckets (range 0.043).

## Limits

- **Synthetic data.** The complaint row comes from a generated dataset; the fixed descriptions and empty interaction
  link may be generator choices rather than how a real bank records complaints. The comparison is about what the
  record can carry, not a measured improvement.
- **One live packet.** The "after" is a single packet from one scenario. That 100 % of handoffs arrive as a valid
  `handoff.v1` packet is a stated target (README); it is enforced by the schema (`HandoffPacket`, pydantic) on every
  write, but no live evaluation has measured completeness yet.
- **The unauthorized path skips transaction binding by design.** This packet has no verified facts or policy checks
  because the customer named no charge, and the agent hands off rather than questioning someone reporting fraud. A
  person still has to find the transaction; the packet tells them what to ask.
- **Time to first response is not compared.** The packet exists the moment the turn ends, but nothing here measures
  when a person picks it up. That needs a pilot against the 37-hour baseline.
