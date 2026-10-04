# 20 · Claude on Bedrock: Model Config, Extract, Compose, Templates

**Subsystem:** Agent core · **Depends on:** 12 · **Reference:** agent-core plan, Task 9 · **[live]**

## Goal

Configure Claude per role, implement `extract` and `compose` as tool-free structured-output calls, and write the fixed ES/PT templates.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Agent Core
- `context/architecture-context.md` → Agent Core
- Agent-core plan #1 (refusals handled in code) in `progress-tracker.md` → Architecture Decisions

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Claude · agent-core §6

Models are configured per role in `llm/models.yaml` (overridable by environment variable). The model id and prompt version are recorded for every call. Defaults:

- **`extract`:** Claude Haiku 4.5, thinking off.
- **`compose`:** Claude Sonnet 5.5, effort `low`.

Both use structured outputs (`output_config.format`), a prompt-cached stable prefix, and the SDK's Bedrock client (region `us-east-1`; exact model IDs and availability confirmed in the first implementation task). Refusals are handled with the SDK's client-side refusal-fallback middleware; if a refusal survives it, the turn uses a template or hands off. Whether "Haiku for both" is good enough is measured in spec 2.

**Claude has no tools.** Both calls are pure input-to-JSON; only graph nodes call tools.

#### `extract` · agent-core §6.1

```json
{ "language_detected": "es|pt|other",
  "english_gloss": "…",
  "multi_intent": true, "secondary_request_en": "…|null",
  "mentions": { "merchant": "…|null", "amount": 123.45, "currency": "…|null",
                "date_from": "YYYY-MM-DD|null", "date_to": "YYYY-MM-DD|null" },
  "customer_statement": { "original": "…", "en": "…" } }
```

- Relative dates are resolved against the as-of date given in the prompt; code clamps them to the 60-day window.
- Mentions only pre-filter candidate transactions; they never choose one.
- `extract` does not classify intent. That's Jev's job.

#### `compose` · agent-core §6.2

- **Input:** receipts, a node-set `reply_goal` (`answer`, `ask_clarification{options}`, `ask_confirmation`, `handoff_notice{ref}`, `abstain`), and the language.
- **Output:** `{reply_text, claims[]}`.
- **Fixed ES/PT template blocks, inserted verbatim:**
  - the dispute confirmation summary (what the customer confirms is exactly what gets filed);
  - the handoff notice with its reference;
  - authentication and session-expired messages;
  - the safe fallback reply.
- **Decline explanations** use `seed_decline_reason.customer_text_es/pt`.

#### Language · agent-core §6.3

- **Session language:** `lang` in the JWT (`es` or `pt`, chosen at login).
- **Reply language:** the language of the latest message when it's ES or PT; otherwise the session language, with a note that only ES and PT are supported. Mixed ES/PT falls back to the session language.
- **Money** is formatted by currency code (COP without decimals).
- **`english_gloss`** is always generated and logged. Whether Jev's state includes it is a per-language setting (`original_only` | `original_plus_gloss`) chosen in spec 2 by measurement. Default: `original_plus_gloss`. The original text is always included, and `injection_attempt` always judges the original.

## Implementation

### Files

- Create: `agent/src/bankagent/llm/__init__.py`, `agent/src/bankagent/llm/models.yaml`, `agent/src/bankagent/llm/config.py`, `agent/src/bankagent/llm/client.py`, `agent/src/bankagent/llm/extract.py`, `agent/src/bankagent/llm/compose.py`, `agent/src/bankagent/llm/templates.py`, `agent/tests/fakes.py`, `agent/tests/test_llm.py`, `agent/tests/test_templates.py`, `agent/scripts/smoke_bedrock.py`

### Interfaces

- Consumes: nothing from earlier tasks.
- Produces:
  - `RoleConfig(model, max_tokens, prompt_version, timeout_s, effort)` and `load_models(path=..., env=None) -> {"extract": RoleConfig, "compose": RoleConfig}`;
  - `LLMError`, `LLMRefusal(LLMError)`;
  - `LLMCall(data, model, prompt_version, usage, latency_ms)`;
  - `make_bedrock_client(region)`;
  - `call_json(client, cfg, system, user, schema) -> LLMCall`;
  - `Extraction(language_detected, english_gloss, multi_intent, secondary_request_en, mentions, customer_statement)` and `extract(client, cfg, message, as_of, recent) -> (Extraction, LLMCall)`;
  - `Composed(reply_text, claims)`, `compose(client, cfg, goal, receipts, language, feedback=None) -> (Composed, LLMCall)`, and `open_questions(client, cfg, request_en, reason_codes, receipts) -> (list[str], LLMCall)`;
  - templates: `fmt_money`, `confirmation_summary(txn, reason, lang)`, `handoff_notice(ref, lang)`, `dispute_filed(dispute_id, lang)`, `handoff_failed(lang)`, `auth_message(kind, lang)` (`kind` ∈ `auth_required | session_expired | invalid_message`), `fallback_reply(goal, receipts, lang)`, `INTENT_LABELS`, `REASON_LABELS`.
  - Test double `tests/fakes.py::FakeLLM(language="es", multi_intent=False, secondary=None, mentions=None, fail=(), refuse=(), reply_text=None)` exposing `.messages.create(**kw)`, `.calls`, `.roles`.

## Scope Limits

- `llm/` and its tests. Claude gets no tools.
- The Bedrock smoke test uses synthetic data and runs once the owner approves.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- The reference task's tests exist and pass:
  `test_model_defaults_and_env_override`, `test_extract_request_shape_and_untrusted_wrapping`, `test_compose_uses_low_effort_and_hides_fixed_block`, `test_compose_passes_feedback`, `test_open_questions_capped_at_three`, `test_refusal_raises`, `test_connection_error_raises_llm_error`, `test_invalid_json_and_truncation_raise`, `test_fmt_money`, `test_confirmation_summary_es_and_pt`, `test_fixed_blocks`, `test_fallback_answer_renders_receipts`, `test_fallback_offers_human_and_lists_options`, `test_fallback_unknown_language_defaults_to_es`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-29-agent-core.md`: Task 9 (Claude on Bedrock: model config, extract, compose, templates), lines 3296–3949
