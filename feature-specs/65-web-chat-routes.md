# 65 · AgentCore Client, `/api/chat` and Session History

**Subsystem:** UI · **Depends on:** 64 · **Reference:** ui plan, Task 13

## Goal

Call AgentCore with the customer's Bearer JWT and message-id header, gate on human control, and serve owner-checked history.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → BFF route handlers · ui §6
- Deployment plan #1 (Bearer-only invocation) in `progress-tracker.md` → Architecture Decisions
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/lib/server/agentcore.ts`, `web/app/api/chat/route.ts`, `web/app/api/sessions/[sid]/messages/route.ts`
- Test: `web/tests/unit/agentcore.test.ts`, `web/tests/unit/chat-route.test.ts`, `web/tests/unit/messages-route.test.ts`

### Interfaces

- Consumes: `customerFrom`/`staffFrom` (Task 11), `getSession`, `listMessages`, `appendMessage`, `claimMessageId` (Task 12), `ChatReply` (Task 10).
- Produces:
  - `runtimeSessionId(sid) -> string` (at least 33 characters, deterministic);
  - `invokeAgent({token, sid, message, clientMessageId, lang}) -> Promise<ChatReply>`, throwing `AgentError("timeout" | "upstream")`;
  - `POST /api/chat {message, client_message_id}` → `200 {data: ChatReply}`; or `202 {data: {pending: true}}` in `CHAT_ASYNC` mode; or `401 {error: {code: "session_expired"}}`; or `504`/`502`;
  - `GET /api/sessions/[sid]/messages?after=` → `{data: ChatMessage[]}`: the owner customer or any agent, otherwise `404 not_found`;
  - `POST /api/sessions/[sid]/messages {text}` (the agent holding the takeover) → `201 {data: ChatMessage}`, otherwise `409`.

## Scope Limits

- `lib/server/agentcore.ts`, `app/api/chat/route.ts` and `app/api/sessions/[sid]/messages/route.ts`.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes, including Review Focus #2.
- The reference task's tests exist and pass:
  `is deterministic and at least 33 characters`, `sends the bearer token, runtime session id and message-id header, and parses the reply`, `maps timeouts and upstream errors`, `is 401 session_expired without a valid customer cookie`, `rejects an empty message and a bad client id with 400`, `skips the runtime while a human holds the session, and stores the message once`, `invokes the agent with the cookie's token otherwise`, `turns an agent session_expired reply into 401 and a timeout into 504`, `returns the owner's history`, `history for a session owned by someone else is not_found`, `a customer asking for another sid than their token's is not_found`, `any agent can read`, `needs the takeover held by this agent`
- **A customer's cookie `sid` naming another customer's session in a history request** (for example a hand-edited URL). Expected: `404 not_found`, the same as a missing session, and no query result leaks. Pinned in Task 13 (`history for a session owned by someone else is not_found`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 13 (AgentCore client, `/api/chat` and session history), lines 3745–4075
