# 67 · Trace View Model, Signal Colours, Stage Mapping, `/api/trace/[sid]`

**Subsystem:** UI · **Depends on:** 64 · **Reference:** ui plan, Task 15

## Goal

Map decision records to the trace view model on the server, with the fixed signal colours and the demo stage-light mapping.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/ui-context.md` → Trace signal colours · ui §7.3; Trace component · ui §8.3; Act 2 · ui §9.2
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/lib/trace/signals.ts`, `web/lib/trace/viewModel.ts`, `web/lib/trace/stages.ts`, `web/app/api/trace/[sid]/route.ts`
- Test: `web/tests/unit/trace-viewmodel.test.ts`, `web/tests/unit/stages.test.ts`

### Interfaces

- Consumes: `DecisionRecord` (Task 12), `ChatMessage` (Task 10), `listRecords`/`listMessages` (Task 12), and the record payloads from agent-core plus Task 5:
  - understand `jev`: `{answers: {q: {label, probabilities} | {p}}, thresholds, aliases}`;
  - understand `route`: `{next, reasons}`;
  - understand `llm` extract: `{role: "extract", output: {english_gloss}}`;
  - understand `model`: `{probs: {txn_id: p}, contributions: {txn_id: [[feature, value], …]}}`;
  - `check_eligibility` `policy`: `{outcome, rules: [{name, passed, detail}]}`;
  - `handoff` `tool`: `{handoff_id, priority}`;
  - reply `llm`: `{role: "compose", claims}`;
  - reply `jev`: `{verify: {ok, failed_claims, promises_unverified}}`;
  - reply `template`;
  - `error`: `{role, error}`;
  - turn `turn_end`: `{duration_ms}`.
- Produces:
  - `SIGNALS` (the order and colour of the 9 questions), `signalColor(signal) -> string`, `BELOW_COLOR`;
  - `buildTurn(records, customer?: ChatMessage) -> TraceTurn` and `buildTrace(records, messages) -> TraceTurn[]` (newest first);
  - `stageOf(node, kind) -> Stage | null`, where `Stage = "understand" | "decide" | "act" | "verify"`;
  - `GET /api/trace/[sid]?turn=` (staff) → `{data: TraceTurn[]}`;
  - types:
```ts
interface TraceBar { signal: string; label: string; value: number; threshold: number | null; crossed: boolean;
  color: string; verdict: { icon: "✓" | "?" | "⚑" | "⛔" | "·"; text: string }; detail?: string;
  candidates?: { alias: string; label: string; score: number; why: string[] }[] }
interface TraceTurn { turnId: string; quote: string; quoteEn: string | null; durationMs: number | null;
  bars: TraceBar[]; folded: { count: number; highest: { label: string; value: number } | null; bars: TraceBar[] };
  replyCheck: { text: string; failed: boolean; regenerated: number; template: boolean } | null;
  errors: string[]; route: { next: string; priority: string | null; policy: { name: string; passed: boolean }[] };
  versions: { questionSet?: string; thresholds?: string } }
```

## Scope Limits

- pure view-model code plus one route. No rendering.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `npm test` passes, including Review Focus #4.
- The reference task's tests exist and pass:
  `opens crossed flags first, then path choices, capped at 4, and folds the rest`, `colours by signal above the threshold and grey below`, `explains choice bars with runner-up, margin and the resolver's candidates`, `puts failed policy rules first and reads priority from the handoff`, `summarises the reply check`, `marks an intent below threshold as clarify and colours it grey`, `turn with only error records renders error rows and route`, `counts regenerations and failed claims`, `groups by turn, newest first, and ignores turns without records`
- **A turn with no Jev answers at all** (Jev down, so only error records). Expected: the trace block still renders, with the error row and the route strip, and doesn't crash. Pinned in Task 15 (`turn with only error records renders error rows and route`).
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 15 (Trace view model, signal colours, stage mapping and `/api/trace/[sid]`), lines 4272–4687
