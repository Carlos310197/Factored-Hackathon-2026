# 68 · Realtime Client, Channel Hook, Chat Store and API Client

**Subsystem:** UI · **Depends on:** 62 · **Reference:** ui plan, Task 16

## Goal

Merge POST replies, pushed events and history into one de-duplicated chat store, with a realtime client that falls back to polling.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/architecture-context.md` → Real-Time UI (rule 2: load, then listen)
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/lib/realtime/client.ts`, `web/lib/realtime/useChannel.ts`, `web/lib/chat/store.ts`, `web/lib/chat/api.ts`
- Test: `web/tests/unit/chat-store.test.ts`, `web/tests/unit/realtime-client.test.ts`

### Interfaces

- Consumes: `ChatMessage`, `ChatReply`, `SessionEvent` (Task 10); `/api/chat`, `/api/sessions/[sid]/messages` and `/api/auth/realtime-token` (Tasks 11 and 13).
- Produces:
  - `connectChannel(channel, onEvent, opts: {as: "customer" | "staff"; onResync: () => void; pollMs?: number}) -> () => void`: uses Amplify Events when `NEXT_PUBLIC_EVENTS_HTTP_DOMAIN` is set, otherwise polls `onResync` every `pollMs` (default 3000); on error or disconnect it calls `onResync` and reconnects with backoff; it refreshes the token every 14 minutes;
  - `useChannel(channel | null, onEvent, opts)` (a React hook) that also reports `status: "live" | "polling" | "reconnecting"`;
  - `createChatStore()`, a Zustand store with:
    - state `{messages: ViewMessage[], cursor: string | null, running: boolean, awaiting: Awaiting, control: string, failed: {clientId, text} | null, expired: boolean}`;
    - actions `sendOptimistic(clientId, text)`, `applyReply(clientId, reply)`, `merge(messages)`, `applyEvent(ev: SessionEvent)`, `fail(clientId)`, `expire()`;
    - `ViewMessage = ChatMessage & {status?: "sending" | "provisional"}`;
  - `api.send(text, clientId) -> Promise<{kind: "reply", reply} | {kind: "pending"} | {kind: "expired"} | {kind: "error"}>`, `api.history(sid, after?) -> Promise<ChatMessage[]>`.

## Scope Limits

- client-side state and transport. No visual components.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes, including Review Focus #1 (store dedupe).
- The reference task's tests exist and pass:
  `dedupes a reply that arrives by POST and by push`, `tracks awaiting from the latest assistant message and control from control events`, `keeps the failed message for a retry with the same client id`, `orders by cursor even when history arrives out of order`, `polls onResync every pollMs and stops on dispose`
- **A double-tapped Send, or a retry after a network drop, with the same `client_message_id`.** Expected: one turn runs and both requests get the same reply, never a second turn or a duplicate bubble. Pinned in Task 4 (`test_same_message_id_returns_stored_reply_without_second_turn`) and Task 16 (`dedupes a reply that arrives by POST and by push`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 16 (Realtime client, channel hook, chat store and API client), lines 4691–5009
