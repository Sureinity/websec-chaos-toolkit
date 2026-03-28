# Internal Security Toolkit

This repository now contains the initial scaffold for a Python-first internal
security testing toolkit.

The current state is intentionally narrow:

- the package layout, command tree, docs skeleton, tests skeleton, and valid
  sample config files exist
- `toolkit validate` is implemented against the current config bundle and exit
  code contract
- `toolkit report build` is implemented for stored normalized result bundles
- operational scanners, chaos adapters, and full execution flows are not
  implemented yet
- `toolkit pentest run` and `toolkit chaos run` remain scaffold-only and
  currently exit with code `2`

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
uv run toolkit validate --app sample-internal-app --env local
uv run toolkit report build --run-id <existing-run-id>
```

## Command Tree

The public CLI surface has been stubbed to match the intended interface:

```text
toolkit validate --app <id> --env <env>
toolkit pentest run --app <id> --env <env> --profile <name>
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

`toolkit validate` now performs real configuration loading and validation.
`toolkit report build` now rebuilds Markdown summaries from stored normalized
results.
`toolkit pentest run` and `toolkit chaos run` remain scaffold-only.

## Sample Configs

The repository root contains valid sample configuration files:

- `apps.yaml`
- `pentest-profiles.yaml`
- `chaos-profiles.yaml`

The current root sample apps are:

- `sample-internal-app` in `local` with `auth.method: none`
- `sample-staging-auth-app` in `staging` with `auth.method: form`

## Implementation Roadmap

The planned delivery sequence for turning the scaffold into a working toolkit
is documented in `docs/explanation/implementation-roadmap.md`.

The system overview and architecture diagrams live in
`docs/explanation/architecture.md`.
