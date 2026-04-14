# Internal Security Toolkit

This repository contains a Python-first internal security testing toolkit
with URL-first and config-driven commands for live execution against real
targets.

Current state:

- `toolkit audit` runs a zero-config safe web audit from a single URL and
  auto-selects `container` or `host` runtime readiness
- `toolkit validate` validates app/profile config against the locked schema
- `toolkit pentest run` executes real scanner binaries (zap, nuclei, nmap)
  against a live target via host subprocess or Docker container backend; a
  fixture-backed flow is preserved for onboarding and offline testing
- `toolkit doctor` reports environment readiness for the simplified audit path
- `toolkit chaos run` executes live Toxiproxy-backed experiments against a
  live target; a fixture-backed flow is preserved for onboarding and offline
  testing
- `toolkit report build` rebuilds Markdown summaries from stored normalized
  result bundles
- scanner adapters (ZAP, Nuclei, Nmap, Trivy, Semgrep) are implemented with a
  shared contract, runtime backend abstraction, and normalizers

## Current Status

Implemented now:

- `toolkit audit`
- `toolkit validate`
- `toolkit pentest run`
- `toolkit doctor`
- `toolkit chaos run`
- `toolkit report build`

Live execution now:

- pentest runs execute real scanner binaries against a reachable target;
  `--runtime host` (default) or `--runtime container` (Docker)
- chaos runs execute live Toxiproxy-backed experiments against a live target
- fixture-backed flows preserved for onboarding and offline testing

External tool requirements:

- `toolkit pentest run --runtime host` requires `zap-baseline.py`, `nuclei`,
  and `nmap` on `PATH`
- `toolkit pentest run --runtime container` requires Docker on `PATH` and
  pre-pulled scanner images
- `toolkit chaos run` requires a running Toxiproxy server and a configured
  proxy for the target service
- optional adapter smoke tests are gated behind
  `TOOLKIT_RUN_EXTERNAL_TOOL_TESTS=1` and skip cleanly when binaries are absent

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

## Quick Start (URL-First)

For the shortest path, run the toolkit against one reachable URL without YAML
config files:

```bash
uv run toolkit doctor
uv run toolkit audit http://127.0.0.1:8000
```

Start here when you want:

- zero-config remote web auditing
- automatic runtime selection
- one ad hoc target without named app/profile setup

Read next:

- `docs/tutorials/quickstart-url-first.md`
- `docs/how-to/run-url-audit.md`

## Docker-First Operator Workflow (Preferred)

The preferred portability path runs the toolkit, target app, and optional
Toxiproxy service together via Docker Compose:

```bash
docker compose up -d toolkit-runner sample-app
docker compose exec toolkit-runner toolkit validate \
  --app sample-internal-app --env local
docker compose exec toolkit-runner toolkit pentest run \
  --app sample-internal-app --env local --profile safe-web-baseline \
  --runtime container
```

Add the chaos profile when running live chaos experiments:

```bash
docker compose --profile chaos up -d toolkit-runner sample-app toxiproxy
```

See `docs/how-to/run-with-compose.md` for the complete workflow.

## Advanced Config-Driven Start

For development on a host that already has the required binaries, the
direct CLI path also works.

Choose one sanitized example pack:

- `examples/configs/sample-webapp/` — default local walkthrough
- `examples/configs/sample-webapp-compose/` — Compose-aware variant with
  service-name URLs
- `examples/configs/sample-api/` — authenticated API-oriented variant

Default walkthrough:

```bash
cd examples/configs/sample-webapp
uv run toolkit validate --app sample-internal-app --env local
uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
uv run toolkit report build --run-id <existing-run-id>
```

Task-oriented guides:

- `docs/how-to/run-url-audit.md` — zero-config audit from a URL
- `docs/how-to/run-with-compose.md` — Compose-based operator workflow
- `docs/how-to/run-pentest-with-docker.md` — Docker container runtime
- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/schedule-execution.md`

Reference and rationale:

- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
- `docs/explanation/compose-workflow-model.md`
- `docs/explanation/safety-model.md`
- `docs/explanation/architecture.md`

## Command Tree

The public CLI surface is implemented and uses one entrypoint:

```text
toolkit audit <url> [--runtime host|container]
toolkit validate --app <id> --env <env>
toolkit doctor
toolkit pentest run --app <id> --env <env> --profile <name> [--runtime host|container]
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

`toolkit audit` runs a zero-config remote web audit from a URL and writes run
artifacts.
`toolkit validate` now performs real configuration loading and validation.
`toolkit doctor` reports simplified runtime readiness for the audit path.
`toolkit pentest run` now executes real scanner binaries against a live target
and writes run artifacts.
`toolkit chaos run` now executes live Toxiproxy-backed experiments and writes
run artifacts.
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

The safety model and execution mode boundaries live in
`docs/explanation/safety-model.md`.

For the full docs index, see `docs/README.md`.
