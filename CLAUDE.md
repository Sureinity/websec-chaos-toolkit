# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Authoritative Contract

`AGENTS.md` is the project contract. Read it before making any changes to CLI behavior, YAML schema, JSON output shape, or exit-code semantics. Any such change requires updating tests, docs, examples, and AGENTS.md together.

## Commands

**Setup:**
```bash
uv sync --extra dev
uv run pre-commit install
```

**Run tests:**
```bash
uv run pytest                              # full suite
uv run pytest tests/unit/                 # unit only
uv run pytest tests/integration/          # integration only
uv run pytest -m external_tools           # requires ZAP/Nuclei/Nmap binaries
uv run pytest tests/unit/config/test_loader.py::ClassName::test_method  # single test
uv run pytest --cov=src --cov-report=term-missing
```

**Lint and format:**
```bash
uv run ruff check src tests
uv run ruff format src tests
uv run mypy
uv run pre-commit run --all-files
```

**CLI (run from repo root where YAML configs live):**
```bash
uv run toolkit doctor
uv run toolkit audit <url>
uv run toolkit code-audit <path>
uv run toolkit validate --app <id> --env <env>
uv run toolkit pentest run --app <id> --env <env> --profile <name> [--runtime host|container]
uv run toolkit chaos run --app <id> --env <env> --profile <name>
uv run toolkit report build --run-id <id>
```

## Architecture

### Package layout (`src/toolkit/`)

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Typer app; registers top-level commands plus `pentest`, `chaos`, and `report` groups |
| `audit/` | URL-first audit auth, discovery, fingerprint, and intensity helpers |
| `codeaudit/` | Source-tree tool selection and readiness inspection |
| `commands/` | CLI entrypoints — thin wrappers that call domain services |
| `runtime/` | Host/container backend selection and readiness inspection |
| `config/` | Pydantic models + YAML loader + cross-file validator |
| `core/` | `RunContext` (per-run workspace), exit-code contract, scaffold helpers |
| `auth/` | Env-var secret resolution → `AuthSession`; API-login and form-login helpers |
| `adapters/` | `ToolAdapter` protocol + `ProcessRunner`; ZAP, Nuclei, Nmap, Trivy, and Semgrep wrappers |
| `pentest/` | Planner plus live and fixture-backed execution flows |
| `chaos/` | Live and fixture-backed chaos planning, monitoring, locking, and Toxiproxy integration |
| `results/` | `NormalizedResult` schema, JSON persistence |
| `reports/` | Markdown summary builder (reads normalized JSON) |
| `safety/` | Allowlist validation; refuses production targets |
| `targets/` | Ad hoc URL-first and source-tree target builders |

### Data flow for `toolkit pentest run`

```
CLI → load config (apps.yaml + pentest-profiles.yaml)
    → resolve auth (env vars → AuthSession)
    → PentestPlan (zap → nuclei → nmap, deterministic)
    → RunContext  (creates outputs/<run-id>/{raw,normalized,reports}/)
    → per-adapter: live subprocess or fixture → AdapterRunResult → NormalizedResult[]
    → write outputs/<run-id>/normalized/findings.json
    → write outputs/<run-id>/reports/executive-summary.md
    → exit 0 / 1 / 2
```

### Exit codes (stable contract)
- `0` — success, no actionable findings
- `1` — medium/high findings or resilience failure
- `2` — config or runtime error

### Configuration surface (three YAML files at repo root)
- `apps.yaml` — app registry (id, env, base URL, auth method, enabled modules)
- `pentest-profiles.yaml` — tool enablement, scan depth, template allowlists
- `chaos-profiles.yaml` — fault types, abort thresholds, rollback method

### Adapter contract
Each adapter returns `AdapterRunResult` with: `execution_ok`, `tool_available`,
`artifacts`, `findings: list[NormalizedResult]`, `skip_reason`, and
`error_detail`. The shared process runner underpins live execution, while
fixture-backed flows remain available for onboarding and offline tests.

### Test fixtures
- `tests/fixtures/configs/{valid,invalid}/` — YAML examples
- `tests/fixtures/{zap,nuclei,nmap,semgrep,trivy}/` — tool output samples
- `tests/fixtures/chaos/` — baseline and experiment observation samples
- `tests/fixtures/results/` — normalized result examples

### Commit convention
Use structured Conventional Commit messages.

Allowed types:
- `feat`
- `fix`
- `docs`
- `refactor`
- `style`
- `test`
- `chore`

Format:
- `type(optional-scope): short summary`

Rules:
- Keep the summary concise, ideally 50 characters or fewer
- Use imperative mood such as `add`, `fix`, or `update`
- After the title, add short bullet points in the commit body
- Start each bullet with a verb
- Describe what changed and why
- Prefer lines around 72 characters wide
- Mark breaking changes with `!` in the header or a `BREAKING CHANGE:` footer
