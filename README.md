# Internal Security Toolkit

This repository now contains the initial scaffold for a Python-first internal
security testing toolkit.

The current state is intentionally narrow:

- the package layout, command tree, docs skeleton, tests skeleton, and valid
  sample config files exist
- `toolkit validate` is implemented against the current config bundle and exit
  code contract
- `toolkit pentest run` is implemented against the current fixture-backed
  pentest flow
- `toolkit chaos run` is implemented against the current fixture-backed chaos
  flow
- `toolkit report build` is implemented for stored normalized result bundles
- fixture-driven scanner adapters (ZAP, Nuclei, Nmap) are implemented with a
  shared contract and normalizers; execution-backed scanning and live external
  chaos control are not yet wired

## Current Status

Implemented now:

- `toolkit validate`
- `toolkit pentest run`
- `toolkit chaos run`
- `toolkit report build`

Fixture-backed now:

- pentest runs use repository scanner fixtures rather than live external
  scanner binaries
- chaos runs use fixture-backed monitoring data and a Toxiproxy-like
  controller rather than a live Toxiproxy runtime

Planned later:

- execution-backed pentest scanning through real external binaries
- live Toxiproxy-backed chaos execution

Optional external verification:

- external-binary checks remain opt-in and are not required for the default
  local workflow

## Bootstrap Layout

The scaffold creates the boundaries expected by the project contract:

- `src/toolkit/` for the Python package
- `tests/unit/` and `tests/integration/` for test separation
- `docs/` split by Diataxis mode
- `examples/` for sample artifacts and structure notes
- `config/` for future local config fragments and templates

## Local Setup

The canonical Python package manager for this repository is `uv` by Astral.
Use `uv` for environment creation, dependency installation, and local tool
execution.

```bash
uv sync --extra dev
uv run pre-commit install
uv run pytest
```

## Example-Driven Start

Choose one sanitized example pack:

- `examples/configs/sample-webapp/`
  - default local-safe walkthrough
  - `auth.method: none`
  - `pentest` and `chaos` enabled
- `examples/configs/sample-api/`
  - authenticated API-oriented variant
  - `auth.method: bearer_token`
  - `pentest` enabled

Default walkthrough:

```bash
cd examples/configs/sample-webapp
uv run toolkit validate --app sample-internal-app --env local
uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
uv run toolkit report build --run-id <existing-run-id>
```

Task-oriented guides:

- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/schedule-execution.md`

Reference and rationale:

- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
- `docs/explanation/safety-model.md`
- `docs/explanation/architecture.md`

## Command Tree

The public CLI surface is implemented and uses one entrypoint:

```text
toolkit validate --app <id> --env <env>
toolkit pentest run --app <id> --env <env> --profile <name>
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

`toolkit validate` now performs real configuration loading and validation.
`toolkit pentest run` now performs the current fixture-backed pentest flow and
writes run artifacts.
`toolkit chaos run` now performs the current fixture-backed chaos flow and
writes run artifacts.
`toolkit report build` now rebuilds Markdown summaries from stored normalized
results.

## Sample Configs

The repository root contains valid sample configuration files:

- `apps.yaml`
- `pentest-profiles.yaml`
- `chaos-profiles.yaml`

The current root sample apps are:

- `sample-internal-app` in `local` with `auth.method: none`
- `sample-staging-auth-app` in `staging` with `auth.method: form`

For example-driven onboarding, prefer:

- `examples/configs/sample-webapp/`
- `examples/configs/sample-api/`

## Implementation Roadmap

The planned delivery sequence for turning the scaffold into a working toolkit
is documented in `docs/explanation/implementation-roadmap.md`.

The system overview and architecture diagrams live in
`docs/explanation/architecture.md`.

The current safety and fixture-boundary rationale lives in
`docs/explanation/safety-model.md`.

For the full docs index, see `docs/README.md`.
