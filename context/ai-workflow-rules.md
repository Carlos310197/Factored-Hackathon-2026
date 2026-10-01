# Development Workflow

## Approach

Build the system incrementally, one numbered feature unit at a time, against written specs. The context files say what the system is and what rules hold everywhere. A feature spec says what one unit must deliver. Don't infer or invent behavior beyond them.

## Sources of Truth (in priority order)

1. `progress-tracker.md` → **Architecture Decisions**: planning-time changes to the specs. These override copied spec text.
2. `context/*.md`: system-wide requirements, contracts and rules (copied verbatim from the design specs).
3. `feature-specs/NN-*.md`: the unit's own requirements (also verbatim spec text), scope limits and done-checks.
4. `docs/reference/plans/*.md`: reference implementations. **They are not requirements.** Where a plan disagrees with 1–3, 1–3 win.
5. `docs/design/*.md`: the original specs, frozen. Open them only to look up rationale; their content already lives in 2 and 3.

## Using the Reference Plans

The plans are large (about 1,100–7,500 lines each). Never read a whole plan.

- A feature spec names its reference as `docs/reference/plans/<file>`: Task N, lines A–B. Read **only that line range** (Read with `offset`/`limit`).
- Open it only when you need something the feature spec doesn't give:
  - the exact code or test bodies;
  - an exact command or config value;
  - the step order for a live run.
- Plan code is a starting point. The agent-core and resolver plans were run offline during planning (168 and 238 tests passing). The pipeline, UI, deployment and evaluation plans were not executed. A failing step means fixing the code, not the test's intent.
- When plan text says "spec §X", search for `<spec> §X` in `context/` and `feature-specs/`, or look it up in `docs/design/README.md`.
- When a plan step says to append results to a plan or to edit `docs/superpowers/specs/…`, record that content in `progress-tracker.md` instead (Session Notes, Spec Changelog or Architecture Decisions). Never edit the files in `docs/design/` or `docs/reference/`.

## Path Mapping

The specs and plans were written before the reorganization. Read their paths as:

| Written as | Now |
| --- | --- |
| `docs/superpowers/specs/<name>-design.md` | `docs/design/<name>-design.md` |
| `docs/superpowers/plans/<name>.md` | `docs/reference/plans/<name>.md` |
| "this spec's changelog", "the plan's Task N results" | `progress-tracker.md` |

## Scoping Rules

- Work on one feature unit at a time, in numeric order unless the tracker says otherwise. A unit's **Depends on** line must be satisfied first.
- Prefer small, verifiable increments. A unit is sized to finish with its tests in one session.
- Don't combine system boundaries in one step. Each of these is a separate unit: `pipeline/` + `dbt/`, `agent/`, `infra/realtime/`, `web/`, `infra/`, `analysis/`, `eval/`.
- Stay inside the unit's **Scope Limits**, even when the reference task does more.

## When To Split Work

Split a step if it combines:

- agent graph behavior and infrastructure;
- web UI and BFF/server code across unrelated routes;
- offline code and a live run (live runs are always their own unit);
- behavior that isn't defined in the context files or the feature spec.

If a change can't be verified quickly with offline tests, the scope is too broad.

## Live Runs and External Services

- Units marked **[live]** call Jev, Bedrock, the persona model, Snowflake or real AWS. Before each live command, stop and ask the owner for approval. Approval for one run doesn't cover the next.
- Record what a live run measured (latency, quotas, IDs, hashes) in `progress-tracker.md` → Session Notes, or in the place the unit names.
- Platform-check units (`53`, `77`) can change later units. Record their findings as Architecture Decisions before continuing.

## Handling Missing Requirements

- Don't invent product behavior that isn't defined in the context files or the feature spec.
- If a requirement is ambiguous, resolve it with the owner and record the decision under Architecture Decisions.
- If a requirement is missing, add it to Open Questions in `progress-tracker.md` before continuing.

## Protected Files

Don't modify these unless a unit explicitly says so:

- `docs/design/*` and `docs/reference/plans/*` (frozen sources);
- frozen evaluation artifacts after their freeze step:
  - the resolver test set `test_v1.jsonl` and its completed CSV;
  - the held-out goal cards `heldout_v1.jsonl` and their `.sha256`;
- `.env` and any secret material;
- generated third-party code and library internals (for example `create-next-app` output beyond the unit's edits, and assistant-ui internals).

## Keeping Docs In Sync

- After every unit, update `progress-tracker.md`: what was completed, decisions, and notes for the next session. Record what is actually implemented, not what was intended.
- If implementation changes an interface, contract, table, threshold or rule described in `context/`, update the context file in the same commit and record the change under Architecture Decisions. Copied spec text is edited only this way, never silently.

## Before Moving To The Next Unit

1. The unit's **Check When Done** list passes, including its pinned review-focus tests.
2. No invariant in `architecture-context.md` was violated.
3. The unit's files are committed (one commit, only those files).
4. `progress-tracker.md` reflects the completed work and names the next unit.
