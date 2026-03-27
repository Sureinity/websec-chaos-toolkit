# Internal Security Toolkit

This repository now contains the initial scaffold for a Python-first internal
security testing toolkit.

The current state is intentionally narrow:

- the package layout, command tree, docs skeleton, tests skeleton, and config
  placeholders exist
- operational scanners, chaos adapters, report generation, and full config
  validation are not implemented yet
- scaffolded CLI commands currently exit with code `2` to signal that execution
  flow is still pending

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

## Command Tree

The public CLI surface has been stubbed to match the intended interface:

```text
toolkit validate --app <id> --env <env>
toolkit pentest run --app <id> --env <env> --profile <name>
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

Each command currently reports that the scaffold is present but the execution
logic is not implemented yet.

## Implementation Roadmap

The planned delivery sequence for turning the scaffold into a working toolkit
is documented in `docs/explanation/implementation-roadmap.md`.
