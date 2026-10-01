# 74 · `/demo` Stage: Three Acts

**Subsystem:** UI · **Depends on:** 70, 73, 58 · **Reference:** ui plan, Task 22

## Goal

Build the presenter stage: phone frame with the embedded chat, the stepper, the Act 1 claims panel, the Act 2 live trace, the Act 3 scenario rail and the handoff ticker.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → Demo stage · ui §9
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/app/demo/page.tsx`, `web/components/demo/DemoStage.tsx`, `web/components/demo/PhoneFrame.tsx`, `web/components/demo/SignInPanel.tsx`, `web/components/demo/ScenarioRail.tsx`, `web/components/demo/HandoffTicker.tsx`, `web/lib/demo/scenarios.ts`
- Test: `web/tests/unit/demo.test.tsx`

### Interfaces

- Consumes: `isDemoMessage`, `DemoMessage` (Task 17); `TraceList` (Task 21); `useChannel`, `QueueEvent` (Tasks 16 and 10); `/api/auth/debug-claims`, `/api/auth/demo-users`, `/api/auth/logout` (Task 11).
- Produces:
  - `SCENARIOS: Scenario[]`, where `Scenario = {key, label, lang, steps: string[], note?: string}` (8 entries matching `tag_scenarios.py`);
  - `SignInPanel({steps: {otp, token, realtime, firstTurn}, claims})`;
  - `ScenarioRail({users, onStart, activeKey, nextStep, onPrefill})`;
  - `HandoffTicker()`;
  - `DemoStage()`.

## Scope Limits

- the `/demo` page and its components: phone frame, stepper, Act 1 sign-in panel, Act 2 live trace, Act 3 scenario rail, and the handoff ticker.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes.
- Manually against the local stack: Act 1 ticks steps 1–3 on login and step 4 after the first reply.
- Act 2 shows "Analysing…" and then the trace block.
- Act 3 lists 8 chips, disabling any with no tagged identity. Starting "unauthorized → handoff" signs the phone in as that identity and pre-fills the first message.
- The reference task's tests exist and pass:
  `covers the eight definition-of-done cases with the tag names used by tag_scenarios.py`, `shows each step's state and the decoded claims as text`, `disables scenarios without a tagged identity and starts the others`, `offers the next scripted message as a chip`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 22 (`/demo` stage: three acts), lines 6635–6971
