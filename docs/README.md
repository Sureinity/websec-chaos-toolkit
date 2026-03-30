# Documentation

The documentation scaffold follows the Diataxis framework:

- `tutorials/` for learning-oriented walkthroughs
- `how-to/` for task-focused procedures
- `reference/` for commands, config keys, outputs, and contracts
- `explanation/` for architecture and rationale

Start here for example-driven onboarding:

1. `docs/tutorials/get-started.md`
2. `examples/configs/sample-webapp/`
3. `docs/how-to/run-validation.md`
4. `docs/how-to/run-pentest.md`
5. `docs/how-to/run-chaos.md`
6. `docs/how-to/schedule-execution.md`

Alternative onboarding path:

- `examples/configs/sample-api/`
  - authenticated API-oriented variant
  - useful when you want to validate env-var-backed auth references without
    changing the default web app walkthrough

The main system overview and high-level architecture live in
`docs/explanation/architecture.md`.

The operator documentation scope for Milestone 7 is locked in
`docs/explanation/operator-docs-contract.md`.

The current safety and fixture-boundary rationale lives in
`docs/explanation/safety-model.md`.

The scanner adapter contract lives in
`docs/reference/pentest-adapters.md`.

Command and artifact references:

- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`

The pentest orchestration contract lives in
`docs/reference/pentest-run.md`.

The chaos orchestration contract lives in
`docs/reference/chaos-run.md`.

Operator run guides live in:

- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/schedule-execution.md`

Example config packs live in:

- `examples/configs/sample-webapp/`
- `examples/configs/sample-api/`

Status language used across the docs:

- `Implemented now`
  - behavior exists in the repository and is test-backed
- `Fixture-backed now`
  - behavior is implemented but currently uses repository fixtures or non-live
    controllers
- `Planned later`
  - contract exists, but the live implementation is still future work

The implementation milestone plan lives in
`docs/explanation/implementation-roadmap.md`.
