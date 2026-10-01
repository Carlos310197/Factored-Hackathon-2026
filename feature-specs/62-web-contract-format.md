# 62 · Web Wire Contract, Formatting and ES/PT Copy

**Subsystem:** UI · **Depends on:** 61 · **Reference:** ui plan, Task 10

## Goal

Write the Zod schemas for every boundary, money and date formatting per locale, and the customer dictionaries.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/architecture-context.md` → Invocation contract; Agent state → Handoff packet
- `context/ui-context.md` → Accessibility and language
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/lib/contract.ts`, `web/lib/format.ts`, `web/lib/i18n.ts`
- Test: `web/tests/unit/contract.test.ts`, `web/tests/unit/format.test.ts`, `web/tests/unit/i18n.test.ts`

### Interfaces

- Consumes: the agent response (Task 4), message items (Task 2), channel events (Task 8), `handoff.v1` (agent-core Task 7).
- Produces:
  - `lib/contract.ts`: schemas and types `Lang`, `Awaiting`, `Summary`, `ChatReply`, `MessageMeta`, `ChatMessage`, `SessionEvent`, `QueueEvent`, `TraceEvent`, `HandoffRow`, `HandoffPacket`, `HandoffStatus`, `Priority`, `ResolutionCode`, `RESOLUTION_CODES`, `ApiError`.
  - `lib/format.ts`: `fmtMoney(amount: number, currency: string, lang: Lang): string`, `fmtDate(isoDate: string, lang: Lang): string`, `fmtAge(fromIso: string, now?: Date): string`.
  - `lib/i18n.ts`: `t(lang: Lang): Dict` (typed dictionary) and `REASON_KEYS`.

## Scope Limits

- pure modules with no I/O: Zod schemas for every boundary, money and date formatting, and the customer dictionaries.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes, including the Review Focus #5 test.
- The reference task's tests exist and pass:
  `formats COP without decimals in es-CO and pt-BR`, `formats USD with cents in the locale's style`, `never prints a raw float`, `formats an ISO date in the locale without timezone drift`, `shows minutes, hours and days`, `parses an agent reply with defaults and summary`, `accepts awaiting human and rejects unknown awaiting values`, `parses session, queue and trace channel events`, `parses a handoff.v1 packet with lifecycle fields`, `has the same keys in es and pt`, `interpolates names and dates`
- **Money in COP with thousands separators, or USD with cents, in the confirmation card, for ES and PT.** Expected: `COP 184.900` / `USD 420,00` style per locale, never `184900.0`. Pinned in Task 10 (`formats COP without decimals in es-CO and pt-BR`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 10 (Wire contract, formatting and ES/PT copy), lines 2466–2819
