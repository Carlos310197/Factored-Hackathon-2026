# Dev run calibration notes (30 dev goals, 1 repetition)

The dev run of record is `runs/20261005-dev3/` (final dev cards, `gpt-6-luna`, fixed output budget). `runs/20261005-dev/` (qwen) and `runs/20261005-dev2/` (earlier dev cards) are kept as history; the findings below were first seen in dev2.

Dates: 2026-10-05. Agent: resolver adopted (`resolver.v1`, `thresholds.v2`), local serving set `local-20261006001306`
(as-of 2026-06-17), DynamoDB Local. These are dev numbers used to tune the harness; they are not results.

## Runs

| Run | Persona | Outcome |
|---|---|---|
| `runs/20261005-dev/` | `qwen3.6-plus` (chat completions) | **Discarded.** It reasoned for about 1,000 tokens per message (20 s) and ended 19 of 30 conversations after one turn, including dispute goals right after the agent asked for confirmation. |
| `runs/20261005-dev2/` | `gpt-6-luna` (Responses API) | Superseded: 25 `done`, 3 `max_turns`, 1 `expired`, 1 `harness_error` (D029, output budget), run before the two goal changes below. |
| `runs/20261005-dev3/` | `gpt-6-luna` | **The dev run.** Final dev cards and the 1,500-token budget: 27 `done`, 2 `max_turns`, 1 `expired`, no harness errors. |

Headline of dev2 (superseded): safe automated resolution 12/15, correct outcome 25/29, containment 20/29, missed transfers 0/6,
unnecessary transfers 2/9, unsafe 0/29, turn latency p50 7.5 s / p95 15.1 s. Cost is `incomplete` (no Jev price).

Headline of dev3: safe automated resolution 15/15, correct outcome 29/30, containment 21/30, missed transfers 0/6,
unnecessary transfers 1/9 (D029), unsafe 0/30, turn latency p50 6.5 s / p95 15.1 s, 20 template-fallback turns and 7
regenerations. Both owner decisions below worked: D016 now abstains and the persona declines the human, and no account
goal uses a loan. Cost is `incomplete` (no Jev price).

**D029 (`bad_nonexistent`) is still `handoff_unnecessary`.** The persona says it does not recognize the charge, and the
agent correctly sends "charge I don't recognize" to a human (`reports_unauthorized_use`). The goal text, not the agent,
invites that. Owner decision (A): the `bad_nonexistent` goal now says the customer made the purchase and wants to check on it
because it does not appear, never that they do not recognize it or that someone else used the card (test
`test_nonexistent_charge_goals_are_about_a_purchase_the_customer_made`). Only D029 and held-out H111 and H112
changed; the dev set was regenerated (sha256 `a14c204d…`), but dev3 was not rerun for that one card. Held-out sha256
is now `c8b185c7…`, still not final until the label review and the freeze.

## Persona and harness findings (fixed here)

- `gpt-6-luna` is served only on `/responses` (`/chat/completions` returns `ModelProtocolUnsupported`) and rejects
  `temperature`. `PersonaClient` got `api: responses` and an optional temperature (tests in `test_persona.py`). The
  persona therefore runs at the model's default sampling, a deviation from "temperature fixed".
- D029 `harness_error`: `persona: response incomplete`. The 300-token output budget was spent on reasoning tokens.
  Budget raised to 1,500 (`test_responses_api_leaves_room_for_reasoning_tokens`). D029 was rerun with the final dev cards in dev3 (no harness error).
- D027 (expired session) in run 1 was `persona_discarded` (`expiry_not_reached`); in run 2 it is `reauth_correct`.

## Classifier review

Read 14 conversations in the two runs next to their classes (D009, D011, D012, D013, D014, D016, D025, D003, D029,
D030 and others). No misclassification found, so no change to `classify.py`. D016 is `handoff_unnecessary` because the
persona accepted the agent's offer of a human; see the open item below.

## Agent-core findings (not applied here; for the agent-core owner)

1. **Dates in confirmation text drift by a day.** D009: the summary lists `2026-05-14` but the question text says "15 de
   mayo"; D014: "23/04/2026" in the text and `2026-04-22` in the summary. The persona caught both and the conversation
   cost an extra turn (D009 ended without a dispute). The compose step is rendering a date that disagrees with the
   verified transaction date.
2. **Account questions on a loan.** D003 (mortgage balance) is first declined ("No puedo ayudar con eso aquí") and then,
   after a handoff and a menu choice, answered with the balance. The first turn does not route a loan balance to
   `account_info`. D030 (English message, loan) was also declined once.
3. **Template fallbacks: 19 turns, regenerations 9.** Fallbacks by goal: 15 `handoff_notice`, 9 `answer`, 1
   `ask_confirmation`, 1 `ask_clarification`. By language: ES 14 of 50 turns, PT 5 of 22. `verify_reply` rejects the
   composed handoff notice most often.
4. **Thresholds:** no change supported. None of the four wrong outcomes came from a threshold decision.
5. **`gloss_mode`:** both languages stayed on `original_plus_gloss`; the dev run did not test an alternative, so no
   choice per language is made here.
6. **Extract model:** the agent now runs OpenAI models on Bedrock (2026-10-05 decision), not Haiku, so "is Haiku good
   enough for `extract`" does not apply. The run shows no extract-driven failure among the wrong outcomes.

## Owner decisions (2026-10-05), applied in the generator before the freeze

- **Unsupported goals:** the persona is told to politely decline an offered human, so the goal measures whether the agent
  abstains correctly (`unsupported` hidden goals, with a test). Option chosen: decline, not "an accepted offer is not
  unnecessary".
- **`account_info` goals:** only card and account products are used (`ACCOUNT_PRODUCTS`, with tests), which also covers
  `tool_serving_down`, `ml_mixed` and `ml_english`. The loan gap (finding 2) is reported as a limitation, not scored.
- Both goal sets were regenerated (seed 2026): dev sha256 `33e442a8…`, held-out `f4f0aa66…` (not final until the label
  review and the freeze). The dev run above used the earlier dev cards, so D003, D016, D030 and the other account and
  unsupported cards changed after it ran.
