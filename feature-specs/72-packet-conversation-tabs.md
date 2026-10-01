# 72 · Packet Tab, Conversation Tab and the Shared Gauge

**Subsystem:** UI · **Depends on:** 71, 67 · **Reference:** ui plan, Task 20

## Goal

Render the handoff packet with "why it came to you" gauges, and the transcript with a takeover-only composer.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → Agent console · ui §8.2
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/components/trace/Gauge.tsx`, `web/components/staff/PacketTab.tsx`, `web/components/staff/ConversationTab.tsx`
- Modify: `web/components/staff/ConsoleWithTabs.tsx`
- Test: `web/tests/unit/packet-conversation.test.tsx`

### Interfaces

- Consumes: `HandoffPacket` (Task 10), `TraceBar`/`TraceTurn` (Task 15), `createChatStore`/`api` (Task 16), `useChannel` (Task 16).
- Produces:
  - `Gauge({bar, compact?, reveal?, index?})`;
  - `PacketTab({packet, why: TraceBar[]})`;
  - `ConversationTab({sid, lang, control, me})`;
  - `whyBars(turns: TraceTurn[]) -> TraceBar[]` (the crossed bars from the turn that routed to handoff).

## Scope Limits

- the Packet and Conversation tab contents, plus `components/trace/Gauge.tsx`, which Task 21 reuses.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes.
- Manually: after *Take over chat*, the agent's message appears in the customer's `/chat` within about 1 s with push, or within 3 s with polling. The customer's reply appears in the Conversation tab.
- The reference task's tests exist and pass:
  `shows request, facts with receipts, failed policy first, open questions and why`, `whyBars takes the crossed bars of the handoff turn`, `disables the composer unless this agent holds the takeover`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 20 (Packet tab, Conversation tab (takeover composer) and the shared gauge), lines 6067–6341
