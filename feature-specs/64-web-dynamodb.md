# 64 · Web DynamoDB Access: Sessions, Messages, Handoff Lifecycle, Records

**Subsystem:** UI · **Depends on:** 63, 54 · **Reference:** ui plan, Task 12

## Goal

Implement the BFF's data access, including the atomic claim and the transactional takeover/return.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → Summary

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Data access · ui §5

| Access pattern | Table and operation |
|---|---|
| Customer history after cursor | `conversation_messages` Query PK=`sid`, SK > cursor, **after** checking `sessions.customer_id == JWT.sub` |
| Agent reads a transcript | same Query; role `agent` required |
| Queue list | `handoffs` GSI `status + created_at`, one Query per status in the filter. The BFF sorts by priority (critical › high › medium), then age. The volume is small, so no new index. |
| Claim | `UpdateItem` with `ConditionExpression status = open` (single-item atomic; a failure means someone else has it) |
| Take over / return | `TransactWriteItems`: `sessions.control` + `handoffs.status` (+ a system message row). The two items must never disagree. |
| Resolve | `UpdateItem` with the condition `claimed_by = me` |
| Trace for a turn | `decision_records` Query PK=`sid`, SK begins_with `turn_id#` |
| Trace for a session | the same, without the turn prefix |

*From ui §4, item 5:*

5. **Handoff status lifecycle:** `open → claimed → in_takeover → returned | resolved`.
   - New fields: `claimed_by`, `claimed_at`, `resolution {code, note, by, at}`.
   - Resolution codes: `resolved_by_agent`, `dispute_filed_manually`, `no_action_needed`, `referred_to_phone`.

## Implementation

### Files

- Create: `web/lib/server/ddb.ts`, `web/lib/server/sessions.ts`, `web/lib/server/messages.ts`, `web/lib/server/handoffs.ts`, `web/lib/server/records.ts`
- Test: `web/tests/unit/ddb.test.ts`, `web/tests/helpers/tables.ts`

### Interfaces

- Consumes: the table schemas from Task 2 and agent-core Task 6 (`<prefix>-sessions`, `-conversation_messages`, `-handoffs` with GSI `by_status (status, created_at)`, `-decision_records`).
- Produces:
  - `doc()`: a `DynamoDBDocumentClient` (with `removeUndefinedValues`); `tableName(name)`;
  - `ConflictError`;
  - `getSession(sid) -> Promise<SessionItem | null>`, where `SessionItem = {session_id, customer_id, language, control}`;
  - `listMessages(sid, after?) -> Promise<ChatMessage[]>`, `appendMessage(sid, m: {role, text, author?, meta?, id?}) -> Promise<ChatMessage>`, `claimMessageId(sid, id) -> Promise<boolean>` (true when new);
  - `listHandoffs(statuses: HandoffStatus[]) -> Promise<HandoffRow[]>` (sorted by priority, then oldest first); `getHandoff(id) -> Promise<HandoffPacket | null>`;
  - `claim(id, agent)`, `takeover(id, agent, agentName)`, `returnToAssistant(id, agent)` and `resolve(id, agent, code, note)`, each `-> Promise<HandoffPacket>` and each throwing `ConflictError` when the precondition fails;
  - `listRecords(sid, turnId?) -> Promise<DecisionRecord[]>`, where `DecisionRecord = {session_id, sk, turn_id, seq, node, kind, ts, payload, versions, latency_ms?}`.

## Scope Limits

- `lib/server/{ddb,sessions,messages,handoffs,records}.ts` and their integration tests. No routes.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- with DynamoDB Local running, `DYNAMODB_ENDPOINT=http://localhost:8000 npm test -- ddb` passes, including the lifecycle race tests. Without the endpoint those tests are skipped and say so.
- The reference task's tests exist and pass:
  `appends and lists messages in order, after a cursor, skipping idempotency markers`, `lists the queue by priority then age`, `claim is atomic: the second agent gets a conflict`, `takeover sets control and writes a system message; return by a non-holder is 409 and control is unchanged`, `resolve needs the holder, records the resolution and hands control back`, `lists decision records for a turn`
- **An agent resolving or returning a case they don't hold** (a second tab, or a colleague's case). Expected: a conflict (`409` from the route), and the other agent's takeover is unchanged. Pinned in Task 12 (`takeover sets control and writes a system message; return by a non-holder is 409 and control is unchanged`) and Task 14 (`maps ConflictError to 409…`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 12 (DynamoDB access: sessions, messages, handoff lifecycle, decision records), lines 3339–3741
