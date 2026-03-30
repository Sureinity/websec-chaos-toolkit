# Operator Documentation Contract

This document locks the operator-facing documentation scope for Milestone 7 so
later doc work does not need to re-decide the target journeys, example shapes,
or status language.

## Purpose

Use this contract when writing or updating:

- README and onboarding docs
- tutorials
- how-to guides
- reference pages
- explanation pages that describe operator-visible constraints

The goal is simple: a contributor or operator should be able to use the
repository without tribal knowledge, while still understanding which flows are
fixture-backed and which capabilities are only planned.

## Required Operator Journeys

Milestone 7 documentation must cover these journeys explicitly.

### Local Setup And Orientation

- Primary docs:
  - `README.md`
  - `docs/tutorials/get-started.md`
- Required commands:
  - `uv sync --extra dev`
  - `uv run toolkit --help`
- Required outcome:
  - a contributor can install dependencies, inspect the CLI tree, and identify
    where the task-oriented and reference docs live

### Validation Workflow

- Primary doc:
  - `docs/how-to/run-validation.md`
- Required command:
  - `uv run toolkit validate --app sample-internal-app --env local`
- Required outcome:
  - an operator understands config selection, success behavior, and exit code
    `2` failure modes

### Fixture-Backed Pentest Workflow

- Primary doc:
  - `docs/how-to/run-pentest.md`
- Supporting references:
  - `docs/reference/pentest-run.md`
  - `docs/reference/output-artifacts.md`
- Required command:
  - `uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline`
- Required outcome:
  - an operator can run the fixture-backed pentest flow, inspect artifacts, and
    interpret exit codes `0`, `1`, and `2`

### Fixture-Backed Chaos Workflow

- Primary doc:
  - `docs/how-to/run-chaos.md`
- Supporting references:
  - `docs/reference/chaos-run.md`
  - `docs/reference/output-artifacts.md`
- Required command:
  - `uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline`
- Required outcome:
  - an operator can run the fixture-backed chaos flow, inspect artifacts, and
    understand abort, rollback, and exit code behavior

### Report Rebuild Workflow

- Primary references:
  - `docs/reference/cli.md`
  - `docs/reference/output-artifacts.md`
- Required command:
  - `uv run toolkit report build --run-id <existing-run-id>`
- Required outcome:
  - an operator can rebuild the Markdown summary from stored normalized results
    without rerunning pentest or chaos commands

### Scheduler-Style Non-Interactive Execution

- Primary doc:
  - `docs/how-to/schedule-execution.md`
- Required commands:
  - `uv run toolkit validate --app sample-internal-app --env local`
  - `uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline`
  - `uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline`
- Required outcome:
  - an operator understands how to run commands non-interactively, how to
    interpret exit codes, and which flows remain fixture-backed today

## Example Persona Contract

Milestone 7 must document and later implement two sanitized example config
trees.

### Sample Web App

- Planned path:
  - `examples/configs/sample-webapp/`
- Required shape:
  - local-safe target
  - `auth.method: none`
  - `pentest` and `chaos` both enabled
  - health endpoint present
  - optional metrics endpoint allowed
- Required role in docs:
  - default walkthrough for validation, pentest, chaos, and report rebuild

### Sample API App

- Planned path:
  - `examples/configs/sample-api/`
- Required shape:
  - staging-safe or local-safe target
  - env-var-backed auth reference
  - `pentest` enabled
  - health endpoint present
  - no secrets or production-like hosts
- Required role in docs:
  - demonstrate that authenticated API-style configs remain configuration
    variants, not a separate product line

## Status Language Contract

Milestone 7 docs must use these status labels consistently.

- `Implemented now`
  - use when a command or behavior is present in the repository and backed by
    tests
- `Fixture-backed now`
  - use when a flow is implemented but currently relies on repository fixtures
    or non-live controllers rather than real external binaries or services
- `Optional external verification`
  - use when behavior can be tested with external tools only under explicit
    environment checks or opt-in test flags
- `Planned later`
  - use when the contract exists but the real implementation is not yet present

Do not use vague language such as:

- “works end-to-end” for live scanner execution
- “real chaos execution” for the current fixture-backed flow
- “production-ready” for any sample config or local fixture scenario

## Cross-Link Contract

Milestone 7 docs must keep the Diataxis surfaces connected in a predictable
way.

```mermaidjs
flowchart LR
    readme[README / onboarding]
    tutorial[Tutorial]
    howto[How-to guides]
    reference[Reference]
    explanation[Explanation]
    examples[Example configs]
    tests[Smoke tests]

    readme --> tutorial
    readme --> howto
    tutorial --> howto
    tutorial --> reference
    howto --> reference
    howto --> examples
    explanation --> howto
    explanation --> reference
    examples --> tests
```

Required cross-links:

- README and tutorial pages must point to the relevant how-to guides
- each how-to guide must point to the command/output reference it depends on
- explanation pages must link back to the operator procedures they justify
- example config trees must be linked from onboarding and the relevant how-to
  guides
- smoke tests must execute the commands the docs ask operators to run, unless a
  page labels a command as illustrative only

## Current Boundaries To Preserve

Milestone 7 documentation must keep these statements explicit:

- `toolkit validate`, `toolkit pentest run`, `toolkit chaos run`, and
  `toolkit report build` are implemented now
- pentest and chaos runs are fixture-backed today
- external-binary checks remain opt-in
- live scanner execution and live Toxiproxy-backed chaos execution are planned
  later

This document is the decision point later Milestone 7 checkpoints should follow
without reopening scope.
