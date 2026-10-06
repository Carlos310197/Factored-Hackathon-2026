# Dev run calibration notes (30 dev goals, 1 repetition)

Dates: 2026-10-05. Agent: resolver adopted (`resolver.v1`, `thresholds.v2`), local serving set `local-20261006001306`
(as-of 2026-06-17), DynamoDB Local. These are dev numbers used to tune the harness; they are not results.

## Runs

| Run | Persona | Outcome |
|---|---|---|
| `runs/20261005-dev/` | `qwen3.6-plus` (chat completions) | **Discarded.** It reasoned for about 1,000 tokens per message (20 s) and ended 19 of 30 conversations after one turn, including dispute goals right after the agent asked for confirmation. |
| `runs/20261005-dev2/` | `gpt-6-luna` (Responses API) | The dev run. 25 `done`, 3 `max_turns`, 1 `expired`, 1 `harness_error`. |

Headline of dev2: safe automated resolution 12/15, correct outcome 25/29, containment 20/29, missed transfers 0/6,
unnecessary transfers 2/9, unsafe 0/29, turn latency p50 7.5 s / p95 15.1 s. Cost is `incomplete` (no Jev price).

## Persona and harness findings (fixed here)

- `gpt-6-luna` is served only on `/responses` (`/chat/completions` returns `ModelProtocolUnsupported`) and rejects
  `temperature`. `PersonaClient` got `api: responses` and an optional temperature (tests in `test_persona.py`). The
  persona therefore runs at the model's default sampling, a deviation from "temperature fixed".
- D029 `harness_error`: `persona: response incomplete`. The 300-token output budget was spent on reasoning tokens.
  Budget raised to 1,500 (`test_responses_api_leaves_room_for_reasoning_tokens`). D029 was not rerun.
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

## Open items for the owner

- **D016 and unsupported goals.** The spec expects "abstain and offer a human". The persona accepted the offer, which
  made a handoff, scored `handoff_unnecessary`. Either the persona is told to decline the offer for `unsupported`
  goals, or an accepted offer is not counted as unnecessary. This changes the goal text or the classifier, so it
  needs a decision before the held-out freeze.
- **`account_info` goals on loans and investments.** Held-out has 3 of 18 such goals; the agent declines them on the
  first turn (finding 2). Keep them as a measured gap, or restrict the generator to card and account products
  before the freeze.
