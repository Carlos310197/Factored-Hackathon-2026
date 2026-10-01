# 70 · Customer Chat (world B, assistant-ui)

**Subsystem:** UI · **Depends on:** 65, 68, 69 · **Reference:** ui plan, Task 18

## Goal

Build `/chat` with assistant-ui: chips, the confirmation card, receipts, system and agent lines, the as-of banner, retry, reconnecting, the expired sheet, and embed mode.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → World B · ui §7.1; Customer chat · ui §8.1
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/app/chat/page.tsx`, `web/components/customer/ChatScreen.tsx`, `MessageView.tsx`, `Chips.tsx`, `ConfirmCard.tsx`, `Receipt.tsx`, `AsOfBanner.tsx`, `ExpiredSheet.tsx`
- Test: `web/tests/unit/customer-parts.test.tsx`

### Interfaces

- Consumes: `createChatStore`, `api` (Task 16); `useChannel` (Task 16); `SessionEvent` (Task 10); `customerFromCookies` (Task 11); `notifyParent`/`isDemoMessage` (Task 17).
- Produces:
  - `ChatScreen({sid, lang, embed})`;
  - parts: `Chips({options, lang, disabled, onPick})`, `ConfirmCard({summary, lang, disabled, onConfirm, onChange})`, `Receipt({ref, lang})`, `AsOfBanner({date, lang})`, `ExpiredSheet({lang, embed})`.

## Scope Limits

- `/chat` and its parts: chips, confirmation card, receipts, system and agent lines, the as-of banner, typing, error with retry, reconnecting, the expired sheet, and embed messaging.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes. Manually against the local stack, the ES dispute scenario shows the card and then the green receipt, and an unauthorized-charge message shows the `HND-` reference.
- The reference task's tests exist and pass:
  `chips send the option text`, `the confirmation card shows the draft formatted in the locale and confirms`, `receipts distinguish a filed dispute from a handoff reference`, `the expired sheet is a labelled modal with a sign-in action`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 18 (Customer chat (world B, assistant-ui)), lines 5264–5626
