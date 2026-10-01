# 90 · First Deploy, Live Checks, Operations README and Spec Fixes

**Subsystem:** Deployment · **Depends on:** 89, 24 · **Reference:** deployment plan, Task 14 · **[live]**

## Goal

Run the bootstrap, ship the first deploy through GitHub, run the live checks, and write the README's Operations section.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets
- `context/project-overview.md` → Success Criteria → Definition of done · deployment §11; Remaining deployment work · deployment §9
- `feature-specs/77-deploy-platform-checks.md` → Capacity limits · deployment §8

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Modify: `README.md` (Operations section), `docs/superpowers/specs/2026-09-26-data-pipeline-design.md` (§7), `docs/superpowers/specs/2026-10-01-deployment-design.md` (a changelog for the planning adjustments), this plan (append "Task 14 results")

### Interfaces

- Consumes: everything above; the UI plan's `infra/realtime/scripts/probe-subscribe.ts` and Task 24 Step 4 (the live smoke walk).
- Produces: the deployed URLs, the measured latencies and quotas, and the README record.

### Notes

- Step 5's "spec corrections" (pipeline §7 role name, the planning changelog) are recorded in `progress-tracker.md` → Architecture Decisions and in `context/architecture-context.md`, not in `docs/design/`.
- Record the results in `progress-tracker.md`, not in the plan.

## Scope Limits

- running the bootstrap, live verification, the README Operations section, and two spec corrections. **Every step that touches AWS, Jev or Bedrock needs the owner's explicit approval for that step.**
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- spec §11 (definition of done) is met and recorded in "Task 14 results" at the end of this file.
- The reference task's tests exist and pass:
  (no automated tests in this task)
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 14 (Bootstrap the account, first deploy, live checks, README and spec fixes), lines 3538–3698
