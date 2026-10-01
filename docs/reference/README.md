# Reference Implementation Plans

These are the original implementation plans, kept unchanged. They are **reference implementations, not requirements**: the working specs are `context/` and `feature-specs/`, and those win in any conflict.

- Never read a plan end to end (they're about 1,100–7,500 lines). Each feature spec names its task and exact line range.
- Paths inside the plans that start with `docs/superpowers/specs/` now live in `docs/design/`, and `docs/superpowers/plans/` now lives in `docs/reference/plans/`.
- Steps that append results to a plan or edit a spec record those results in `context/progress-tracker.md` instead.
- The agent-core and resolver plans were run offline during planning (168 and 238 tests passing). The pipeline, UI, deployment and evaluation plans were not executed.
