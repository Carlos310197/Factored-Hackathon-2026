# 60 · Realtime: Stream-Driven Publisher

**Subsystem:** UI · **Depends on:** 59, 54, 56, 57 · **Reference:** ui plan, Task 8

## Goal

Map DynamoDB Stream records to slim channel events and publish them to AppSync with SigV4, reporting per-item failures.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/architecture-context.md` → Real-Time UI → Channel events · ui §3.1
- UI plan #7 and #8 in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `infra/realtime/publisher/map.ts`, `publisher/publish.ts`, `publisher/index.ts`
- Modify: `infra/realtime/lib/realtime-stack.ts`
- Test: `infra/realtime/test/map.test.ts`, `test/publisher.test.ts`, `test/stack.test.ts` (extended)

### Interfaces

- Consumes: the item shapes from Tasks 2, 4 and 5; `RealtimeStack` (Task 7).
- Produces:
  - `tableKind(eventSourceArn: string): TableKind | null`, where `TableKind = "handoffs" | "decision_records" | "conversation_messages"` (matched on `table/<prefix>-<kind>/stream`);
  - `toEvents(kind, image, eventName): OutEvent[]`, where `OutEvent = {channel: string; payload: ChannelEvent}`;
  - `publish(channel, payloads, deps) -> Promise<void>` (5 events per request, SigV4 service `appsync`, `POST https://<httpDomain>/event`);
  - `handler(event: DynamoDBStreamEvent) -> Promise<{batchItemFailures}>`.
  - **Channel events (the wire contract the web app parses in Task 10):**
    - `/session/<sid>`: `{type:"message", id, cursor, role, text, turn_id?, author?, meta?, ts}` and `{type:"control", control, agent_name?}`;
    - `/queue/all`: `{type:"handoff", handoff_id, session_id, status, priority, reason_codes, language, created_at, claimed_by?}`;
    - `/trace/<sid>`: `{type:"record", turn_id, seq, node, kind}` and `{type:"turn_complete", turn_id}`.

### Notes

- **Superseded steps:** the stack wiring and deploy steps (Steps 5 and 7) move to the Terraform `realtime` root (unit 84). Build the mapping, the publisher and their tests here.

## Scope Limits

- the publisher Lambda (mapping, signing, batching, failure reporting), its Stream mappings, the DLQ and the alarm.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes.
- The synthesized template has 3 event-source mappings with bisect, retries 5, per-item failure reporting and an SQS on-failure destination.
- After an approved deploy, writing one `conversation_messages` item makes it arrive on a probe subscription.
- The reference task's tests exist and pass:
  `recognises the three tables and nothing else`, `maps a message insert to /session/<sid>`, `adds a control event for system rows that change control`, `ignores idempotency markers and modifications of messages`, `maps handoff inserts and modifications to /queue/all`, `maps decision records to slim trace events and turn_end to turn_complete`, `ignores removals (TTL expiry)`, `posts at most 5 events per request with stringified payloads`, `throws on HTTP errors and on per-event failures`, `reports only the failing record and still publishes the others`, `maps the three streams with bisect, per-item failures, 5 retries and a DLQ`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 8 (Stream-driven publisher), lines 1907–2232
