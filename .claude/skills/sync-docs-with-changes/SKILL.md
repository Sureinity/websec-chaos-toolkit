---
name: sync-docs-with-changes
description: Analyze recent git changes and update README.md, AGENTS.md, docs/, and examples/ so documentation stays aligned with implemented behavior, commands, config, outputs, and architecture.
argument-hint: [optional git range, commit, or path]
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(git:*)
---

Sync project documentation with recent code changes.

## When to use

Use this skill when the user asks to:

- update or sync docs after code changes
- align `README.md`, `AGENTS.md`, `docs/`, or `examples/` with recent implementation work
- figure out which docs should change for a recent commit, diff, or path

## Scope rules

- Update documentation only: `README.md`, `AGENTS.md`, `docs/`, `examples/`, and sample config docs.
- Do not change runtime code unless the user explicitly asks for code changes too.
- Do not invent behavior. Document only what the current codebase and git changes support.
- If no doc changes are needed, say so explicitly.

## Change discovery

1. Determine the review scope from `$ARGUMENTS`.
2. If `$ARGUMENTS` is provided:
   - If it looks like a git range, commit, or ref, inspect it with `git diff` and `git show`.
   - If it looks like a file or directory path, inspect current contents plus the relevant diff for that path.
3. If `$ARGUMENTS` is empty:
   - Prefer the working tree with `git diff HEAD`.
   - If the working tree is clean, inspect the latest commit with `git diff HEAD~1..HEAD` or `git show --stat --name-only HEAD`.
4. Extract only documentation-relevant changes:
   - CLI commands, flags, and exit codes
   - config schema or auth semantics
   - output artifact layout
   - architecture or package boundaries
   - current vs planned implementation state
   - examples and sample config behavior

## Doc mapping

- Update `README.md` for top-level current state, setup, and user-facing commands.
- Update `AGENTS.md` for durable repository contract changes.
- Update `docs/reference/` for CLI, configuration, authentication, outputs, and schemas.
- Update `docs/explanation/architecture.md` when high-level structure or system flow changes.
- Update `docs/tutorials/` or `docs/how-to/` only when user workflows changed.
- Update `examples/` when sample layouts or sample configs changed.

## Writing rules

- Keep Diataxis boundaries clean: reference for facts, explanation for rationale, tutorials/how-to for workflows.
- Prefer precise updates over broad rewrites.
- Keep “implemented now” and “planned next” clearly separated.
- Preserve and update Mermaid diagrams when architecture or output flow changes.
- Keep examples sanitized. Never add secrets, real credentials, or production targets.
- If one code change affects multiple docs, update all affected docs in one pass.

## Validation

- Re-read each changed doc for stale or contradictory statements.
- Make sure docs do not claim scaffold-only features are implemented, or the reverse.
- Use `git diff -- README.md AGENTS.md docs examples .claude/skills` to inspect the final doc-only changes.
- If a lightweight repo check helps confirm doc accuracy, run it after edits.

## Output

After editing, respond with:

- what changed
- which docs were updated
- any remaining documentation gaps or assumptions
- a suggested commit message
