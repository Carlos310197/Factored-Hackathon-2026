# 87 · Cross-Stack Checks: IAM Wildcards, Log Retention, cdk-nag

**Subsystem:** Deployment · **Depends on:** 86 · **Reference:** deployment plan, Task 11

## Goal

Test every stack for wildcard IAM, 30-day log retention and a clean cdk-nag run, and fix or justify what they find.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Deployment
- `context/architecture-context.md` → Deployment Topology; Access Controls and Secrets

## Requirements

No spec section belongs only to this unit. The requirements are the context sections under Read First, plus the interfaces below.

## Implementation

### Files

- Test: `infra/tests/test_iam.py`, `infra/tests/test_nag.py`
- Modify (only if the tests require): `infra/lb_infra/nag.py` (`REASONS`) and the stack files' `nag.suppress(...)` lists

### Interfaces

- Consumes: `build_all`, `nag.apply`, and the `stacks`/`templates` fixtures.
- Produces: `STAR_OK: dict[str, str]`, the allow-list with reasons that spec §4.2 refers to.

## Scope Limits

- tests over all stacks, plus the fixes or written suppressions they force. No new resources.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- `uv run pytest -q` passes (every infra test), and `npx aws-cdk@2 synth -q` prints no cdk-nag errors.
- The reference task's tests exist and pass:
  `test_no_service_wide_actions`, `test_star_resource_only_for_allow_listed_actions`, `test_every_log_group_keeps_30_days`, `test_no_unsuppressed_cdk_nag_errors`, `test_every_suppression_has_a_reason`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-deployment.md`: Task 11 (Cross-stack checks: IAM wildcards, log retention, cdk-nag clean), lines 2541–2660
