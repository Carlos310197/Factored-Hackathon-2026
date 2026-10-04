# LATAM Bank Customer-Service System: Agent Instructions

Factored Hackathon 2026. Spec-driven build: `context/` says what the system is and which rules hold everywhere, `feature-specs/` splits the build into numbered units, and `context/progress-tracker.md` says where the build is.

## Application Building Context

Read these files in order before implementing or making any architectural decision:

1. `context/project-overview.md`: product definition, goals, features, scope and success criteria. Read Overview → Scope once per session; Dataset Facts and Success Criteria when a unit points to them.
2. `context/architecture-context.md`: stack, decisions, boundaries, storage and contracts, interfaces, access controls, failure handling and invariants. Always read **Stack**, **System Boundaries** and **Invariants**; read other sections when your unit lists them.
3. `context/ui-context.md`: visual worlds, tokens, surfaces, trace, demo stage, accessibility and the BFF routes. Only for `web/` work.
4. `context/code-standards.md`: implementation rules. Read General, Testing and Live Calls, and the section for your subsystem.
5. `context/ai-workflow-rules.md`: workflow, sources of truth, scoping, live-run approval and how to use the reference plans.
6. `context/progress-tracker.md`: current phase, completed work, open questions, **Architecture Decisions** (which override copied spec text), and next steps.

Then open the next unit in `feature-specs/` (index: `feature-specs/README.md`) and read only the sections its **Read First** list names.

## Rules That Save Context

- Never read a whole file in `docs/reference/plans/`. Each feature spec names a task's exact line range; read only that range, and only when you need exact code, test bodies or commands.
- `docs/design/` holds the original specs, frozen. Their text already lives in `context/` and `feature-specs/`. To resolve a `§` reference, use `docs/design/README.md`.
- Don't edit `docs/design/` or `docs/reference/`. Results that a plan step would write into a plan or spec go to `context/progress-tracker.md`.

## Repo Rules

- Do not add `Co-Authored-By: Claude` (or any Claude attribution line) to commit messages or PR descriptions in this repo.
- For every feature: write the tests first, then implement, then run the tests again, and keep fixing until everything passes.
- Implement every feature in a worktree, using the `.agents/skills/using-git-worktrees` skill. Include the work of each feature (worktree) under `.worktree` creating a folder called `worktree-{name_of_feature}` where `{name_of_feature}` is the name of the file from `feature-specs` without the number, i.e., for the implementation of the feature `01-pipeline-scaffold.md` use `worktree-pipeline-scaffold` as the name of the folder. After finishing the implementation, create a remote branch of the worktree and push the changes there, and finally create a PR in which you include an adecuate title and description (summary in bullets of what's being implement in the current feature).

## Keeping Context Current

Update `context/progress-tracker.md` after each meaningful implementation change.

If implementation changes the architecture, a contract, the scope or the standards documented in the context files, update the relevant file and record the change under Architecture Decisions before continuing.

Anything that calls Jev, Bedrock, the persona model, Snowflake or real AWS runs only after the owner approves that specific run.
