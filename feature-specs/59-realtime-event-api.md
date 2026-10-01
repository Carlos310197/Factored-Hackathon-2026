# 59 · Realtime: Event API, Lambda Authorizer and Channel Rules

**Subsystem:** UI · **Depends on:** 55 · **Reference:** ui plan, Task 7

## Goal

Write the AppSync Events channel rules (`onSubscribe`) and the Lambda authorizer for realtime tokens, with offline tests.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/architecture-context.md` → Real-Time UI (rules and channel events)
- UI plan #7 (`/queue/all`) in `progress-tracker.md` → Architecture Decisions

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `infra/realtime/package.json`, `tsconfig.json`, `cdk.json`, `vitest.config.ts`, `bin/app.ts`, `lib/realtime-stack.ts`, `handlers/namespace.js`, `authorizer/index.ts`, `authorizer/rules.ts`, `scripts/probe-subscribe.ts`, `scripts/stream-arns.sh`
- Test: `infra/realtime/test/rules.cases.ts`, `test/namespace.test.ts`, `test/authorizer.test.ts`, `test/stack.test.ts`

### Interfaces

- Consumes: realtime tokens from the IdP (Task 3): RS256, audience `realtime`, claims `sub, sid, role`.
- Produces:
  - `channelAllowed(segments: string[], c: {role: string; sid: string} | undefined) -> boolean`, in both `authorizer/rules.ts` and `handlers/namespace.js` (same rule, same test cases);
  - `verifyRealtime(token, getKey, issuer) -> Promise<{role, sid, sub} | null>`;
  - `RealtimeStack(scope, id, props: RealtimeProps)` with outputs `HttpDomain`, `RealtimeDomain`, `ApiArn`;
  - `RealtimeProps = {tablePrefix, idpIssuer, idpJwksUrl, streamArns: {handoffs, decision_records, conversation_messages}}`.

### Notes

- **Superseded steps:** deployment plan Task 8 replaces this task's TypeScript `RealtimeStack`, `bin/app.ts` and the synth/deploy/probe steps (Steps 6, 8, 9) with the Python stack in unit 84. Build the handler code, the authorizer and their Vitest tests here; skip the TypeScript CDK app and its deploy.

## Scope Limits

- the Event API, its authorizer and namespace handlers, the stack skeleton, and a probe script. No publisher (that's Task 8).
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes.
- `npx cdk synth` produces one `AWS::AppSync::Api` and 3 `AWS::AppSync::ChannelNamespace`.
- After an approved deploy, the probe script is **allowed** on the own-session channel and **refused** on another session.
- The reference task's tests exist and pass:
  `onSubscribe reads handlerContext or resolverContext and refuses others' channels`, `onPublish forwards events unchanged`, `accepts a realtime token`, `rejects an access token (wrong audience), an expired token and garbage`, `rejects tokens without role or sid`, `authorizes connect without a channel and passes role+sid as handlerContext, no caching`, `refuses a customer subscribing to another session when the channel is known`, `refuses an invalid token`, `has one Event API with three channel namespaces`, `subscribes with the Lambda authorizer and publishes with IAM only`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 7 (Event API, Lambda authorizer and channel rules), lines 1447–1903
