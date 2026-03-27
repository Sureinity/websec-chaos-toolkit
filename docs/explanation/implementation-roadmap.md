# Implementation Roadmap

This roadmap turns the current scaffold into a concrete delivery sequence for
v1. It is intended to be decision-complete enough that each milestone can be
implemented without reopening the basic product shape.

## Locked Decisions

- The public CLI remains:
  - `toolkit validate --app <id> --env <env>`
  - `toolkit pentest run --app <id> --env <env> --profile <name>`
  - `toolkit chaos run --app <id> --env <env> --profile <name>`
  - `toolkit report build --run-id <id>`
- YAML remains the user-facing config surface:
  - `apps.yaml`
  - `pentest-profiles.yaml`
  - `chaos-profiles.yaml`
- Secrets are never stored directly in repository YAML. Config stores references
  such as environment variable names.
- Use `uv` as the canonical Python package manager and tool runner for local
  development, verification, and contributor documentation.
- Run artifacts live under `outputs/<run-id>/raw/`,
  `outputs/<run-id>/normalized/`, and `outputs/<run-id>/reports/`.
- Run commands create raw artifacts, normalized results, and reports in one
  flow. `toolkit report build` reuses the same report builder against stored
  normalized results.
- External-tool tests remain behind markers or explicit environment checks.
- Chaos v1 is proxy-first. `controlled_restart` remains schema-reserved but is
  rejected until a dedicated implementation exists.
- The Trivy and Semgrep milestone is optional and does not block pilot
  readiness.

## Milestone 1: Real Config Schema And Validation

Goal

- Replace placeholder config models with strict, fail-closed validation and a
  working `toolkit validate` command.

Deliverables

- Complete Pydantic schemas for all three YAML files
- Cross-file validation for app, environment, and profile references
- Validation rules for allowlists, health endpoints, auth settings, and chaos
  rollback requirements
- Readable CLI validation output with grouped errors and stable exit codes

Files/directories to create

- `src/toolkit/config/errors.py`
- `src/toolkit/config/validators.py`
- `tests/unit/config/`
- `tests/integration/test_validate_command.py`
- `tests/fixtures/configs/valid/`
- `tests/fixtures/configs/invalid/`
- `examples/configs/`

Acceptance criteria

- Valid sample configs return exit code `0`
- Missing allowlists, missing health endpoints, invalid auth config, missing
  rollback, and production-like targets return exit code `2`
- Validation output identifies the failing file and field
- Config docs describe the implemented schema rather than placeholders

Verification commands

```bash
uv run pytest tests/unit/config tests/integration/test_validate_command.py
uv run toolkit validate --app sample-internal-app --env local
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- None

## Milestone 2: Run Artifact And Report Foundation

Goal

- Establish the stable run workspace and deterministic report generation shared
  by pentest and chaos flows.

Deliverables

- Run-id generation and output directory creation
- Artifact manifest metadata
- JSON bundle writing for normalized results
- Markdown executive summary generation grouped by app and severity
- Working `toolkit report build --run-id <id>` from stored normalized results

Files/directories to create

- `src/toolkit/core/run_context.py`
- `src/toolkit/results/io.py`
- `src/toolkit/reports/writer.py`
- `src/toolkit/reports/loader.py`
- `tests/unit/test_run_context.py`
- `tests/unit/test_report_writer.py`
- `tests/fixtures/results/`

Acceptance criteria

- A normalized result fixture can be written to
  `outputs/<run-id>/normalized/findings.json`
- `toolkit report build` creates
  `outputs/<run-id>/reports/executive-summary.md`
- JSON and Markdown ordering is deterministic
- Empty runs still produce a valid summary

Verification commands

```bash
uv run pytest tests/unit/test_run_context.py tests/unit/test_report_writer.py
uv run toolkit report build --run-id fixture-run-id
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1

## Milestone 3: Auth And Session Bootstrap

Goal

- Support non-interactive authenticated testing without placing secrets in
  repository files.

Deliverables

- Environment-variable based bearer token resolution
- Cookie and session injection helpers
- Scripted HTTP form login helper
- Secret redaction helpers for logs and reports
- Auth failure types that map cleanly to exit code `2`

Files/directories to create

- `src/toolkit/auth/resolver.py`
- `src/toolkit/auth/form_login.py`
- `src/toolkit/auth/redaction.py`
- `tests/unit/auth/`
- `tests/integration/test_auth_resolution.py`
- `tests/integration/test_form_login.py`
- `tests/fixtures/auth/`

Acceptance criteria

- Bearer token and cookie/session material resolve only from configured secret
  references
- Form login obtains a usable session against mocked endpoints
- Auth failures never print secret values
- Unsupported SSO and MFA flows fail explicitly rather than degrading silently

Verification commands

```bash
uv run pytest tests/unit/auth tests/integration/test_auth_resolution.py tests/integration/test_form_login.py
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1

## Milestone 4: Safe Pentest Adapter Layer

Goal

- Wrap ZAP, Nuclei, and Nmap behind stable adapter boundaries and normalize
  their outputs.

Deliverables

- Subprocess runner abstraction
- Adapter availability checks
- Safe invocation builders for ZAP, Nuclei, and Nmap
- Raw artifact capture
- Normalization into the shared result model
- Fixture-based parser coverage for vendor output formats

Files/directories to create

- `src/toolkit/adapters/process.py`
- `src/toolkit/adapters/zap.py`
- `src/toolkit/adapters/nuclei.py`
- `src/toolkit/adapters/nmap.py`
- `src/toolkit/results/normalizers.py`
- `tests/unit/adapters/`
- `tests/fixtures/zap/`
- `tests/fixtures/nuclei/`
- `tests/fixtures/nmap/`

Acceptance criteria

- Enabled tools can be preflight-checked before execution
- Missing required binaries fail clearly
- Disabled tools skip cleanly
- Adapter command lines do not include destructive options
- Sample raw outputs normalize into stable severities and evidence fields

Verification commands

```bash
uv run pytest tests/unit/adapters
uv run pytest -m external_tools tests/integration/test_tool_adapters_external.py
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3

## Milestone 5: Pentest Run Orchestration

Goal

- Make `toolkit pentest run` perform a full validated run from config load
  through artifacts and report output.

Deliverables

- Pentest run service
- Tool-selection planner from profile config
- Auth/session injection into adapters
- Raw artifact storage
- Normalized bundle writing
- Automatic report generation
- Stable exit-code handling for findings and failures

Files/directories to create

- `src/toolkit/pentest/runner.py`
- `src/toolkit/pentest/planner.py`
- `tests/integration/test_pentest_run.py`
- `tests/fixtures/pentest/`

Acceptance criteria

- `toolkit pentest run` creates raw, normalized, and report artifacts in a run
  directory
- Exit code `0` is used when no medium or high findings exist
- Exit code `1` is used when medium or high findings are present
- Exit code `2` is used for config or runtime failures
- Disabled tools are skipped without breaking the run

Verification commands

```bash
uv run pytest tests/integration/test_pentest_run.py
uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 4

## Milestone 6: Chaos Runner With Baseline, Abort, And Rollback

Goal

- Make `toolkit chaos run` execute safe reversible proxy-based faults with
  steady-state validation and automatic rollback.

Deliverables

- Toxiproxy client wrapper
- Baseline capture and health monitoring
- Experiment runner for `latency`, `bandwidth`, `packet_loss`, `timeout`, and
  `connection_refused`
- Abort-threshold evaluation
- Mandatory rollback execution
- One-active-experiment-per-app lock on the operator host
- Chaos artifacts and report output

Files/directories to create

- `src/toolkit/chaos/toxiproxy.py`
- `src/toolkit/chaos/monitoring.py`
- `src/toolkit/chaos/runner.py`
- `src/toolkit/chaos/locking.py`
- `tests/unit/chaos/`
- `tests/integration/test_chaos_run.py`
- `tests/fixtures/chaos/`

Acceptance criteria

- Chaos runs refuse to start without health monitoring and rollback config
- A steady-state baseline is captured before fault injection
- Exactly one reversible proxy fault is active at a time
- Threshold breaches trigger abort and rollback
- Rollback is attempted on timeout and on general errors
- `controlled_restart` is rejected until a dedicated implementation exists
- Exit codes follow the published contract

Verification commands

```bash
uv run pytest tests/unit/chaos tests/integration/test_chaos_run.py
uv run pytest -m external_tools tests/integration/test_chaos_run_external.py
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2

## Milestone 7: Operator Documentation, Sample Configs, And Pilot Coverage

Goal

- Make the repository usable by contributors and operators without tribal
  knowledge.

Deliverables

- End-to-end Diataxis docs for validation, pentest runs, chaos runs, report
  generation, scheduler usage, and local setup
- Sanitized sample configs for one sample web app and one sample API app
- Pilot smoke coverage for documented examples
- Updated contract docs where behavior changes

Files/directories to create

- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/schedule-execution.md`
- `docs/reference/output-artifacts.md`
- `docs/explanation/safety-model.md`
- `examples/configs/sample-webapp/`
- `examples/configs/sample-api/`
- `tests/integration/test_example_configs.py`

Acceptance criteria

- A new contributor can install dependencies, validate sample configs, run
  fixture-backed pentest and chaos flows, and rebuild reports using repository
  docs alone
- Docs state clearly which tests require external binaries and which can run
  fixture-only
- Example configs contain no secrets or production targets

Verification commands

```bash
uv run pytest tests/integration/test_example_configs.py
uv run pre-commit run --all-files
uv run toolkit validate --app sample-internal-app --env local
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 4
- Milestone 5
- Milestone 6

## Milestone 8: Optional Trivy And Semgrep Adapters

Goal

- Add optional static and artifact checks without changing the DAST-first v1
  product shape.

Deliverables

- Trivy adapter
- Semgrep adapter
- Profile toggles
- Clean skip behavior when optional tools are not installed
- Normalization mappings into the shared result model

Files/directories to create

- `src/toolkit/adapters/trivy.py`
- `src/toolkit/adapters/semgrep.py`
- `tests/unit/adapters/test_trivy.py`
- `tests/unit/adapters/test_semgrep.py`
- `tests/fixtures/trivy/`
- `tests/fixtures/semgrep/`

Acceptance criteria

- Trivy and Semgrep run only when enabled in a pentest profile
- Missing binaries skip clearly when optional and fail validation only when
  explicitly required by policy
- Normalized outputs use the same shared result schema and exit-code contract

Verification commands

```bash
uv run pytest tests/unit/adapters/test_trivy.py tests/unit/adapters/test_semgrep.py
uv run pytest -m external_tools tests/integration/test_optional_adapters_external.py
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 5

Optional status

- This milestone is optional for initial pilot readiness and can land after the
  operator documentation milestone.
