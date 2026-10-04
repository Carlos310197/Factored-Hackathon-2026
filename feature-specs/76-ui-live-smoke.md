# 76 · UI Live Smoke Run and the Design Pass

**Subsystem:** UI · **Depends on:** 75, 90 · **Reference:** ui plan, Task 24 · **[live]**

## Goal

Run the UI definition of done against the deployed stack, record latencies, and do the one-time `impeccable` design pass.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → UI
- `context/project-overview.md` → Success Criteria → Definition of done · ui §13
- `context/ui-context.md` → Summary

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Create: `web/Dockerfile` (Next.js standalone output, X86_64, listens on 3000), `web/.dockerignore`
- Modify: `docs/superpowers/plans/2026-09-30-ui.md` (append "Task 24 results")

### Interfaces

- Consumes: everything above; the Task 1 results.
- Produces: the deployed app URL and the recorded smoke results.

### Notes

- **Superseded steps** *(updated 2026-10-04)*: Steps 1–3 (`amplify.yml`, the hand-made BFF IAM policy, the console-created Amplify app) are replaced by the web image and the Terraform `infra/terraform/app` ECS service (units 85, 89). Use Steps 4–6 against the ECS URL (`bin/app-url`, or the ALB once it exists).
- Record the results in `progress-tracker.md`, not in the plan.

## Scope Limits

- hosting configuration, environment, IAM, the live verification, and the one-time design detector pass. Anything that creates AWS resources or calls live services needs the owner's approval for that step.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).
- **[live]**: stop before every step that calls an external service or creates or changes cloud resources, and ask the owner.

## Check When Done

- the spec §13 definition of done is met and recorded in "Task 24 results" at the end of this file, with latencies.
- The reference task's tests exist and pass:
  (no automated tests in this task)
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-09-30-ui.md`: Task 24 (Deploy to Amplify Hosting, the live smoke run and the design pass), lines 7315–7422
