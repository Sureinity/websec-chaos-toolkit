# Implementation Roadmap

This roadmap turns the current scaffold into a concrete delivery sequence for
v1. It is intended to be decision-complete enough that each milestone can be
implemented without reopening the basic product shape.

## Locked Decisions

- The public CLI currently includes:
  - `toolkit audit <url> [--runtime host|container]`
  - `toolkit edge-chaos <url> [--fault <name>]`
  - `toolkit validate --app <id> --env <env>`
  - `toolkit doctor`
  - `toolkit pentest run --app <id> --env <env> --profile <name>`
  - `toolkit chaos run --app <id> --env <env> --profile <name>`
  - `toolkit report build --run-id <id>`
- YAML remains the managed and advanced config surface:
  - `apps.yaml`
  - `pentest-profiles.yaml`
  - `chaos-profiles.yaml`
- A later milestone may add:
  - `toolkit code-audit <path> [--tool semgrep|trivy]`
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
- Milestone 7 documentation scope, status language, and example personas are
  locked in `docs/explanation/operator-docs-contract.md`.
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

## Milestone 9: Execution-Backed Pentest Runs

Goal

- Replace the current fixture-backed pentest execution path with real adapter
  execution against live targets while preserving the existing safety,
  artifact, and exit-code contracts.

Deliverables

- Execution-backed adapter invocation in `toolkit pentest run`
- Preflight availability and skip/fail policy for core and optional tools
- Raw artifact capture from real tool runs
- Normalized findings built from real adapter outputs
- Safe live-target integration coverage against a local test app
- Clear operator docs for live pentest prerequisites and limits

Files/directories to create

- `src/toolkit/pentest/execution.py`
- `tests/integration/test_pentest_run_live.py`
- `tests/integration/test_pentest_command_live.py`
- `tests/fixtures/results/live-pentest/`
- `docs/how-to/run-live-pentest.md`
- `docs/explanation/live-execution-model.md`

Acceptance criteria

- `toolkit pentest run` executes enabled core adapters against a live
  reachable target instead of copying repository fixture artifacts
- Missing required core binaries fail clearly with exit code `2`
- Missing optional binaries skip cleanly when the tool is optional
- Raw outputs, normalized findings, manifest, and Markdown summary are still
  produced under `outputs/<run-id>/`
- Exit codes remain unchanged:
  - `0` for no actionable findings
  - `1` for medium/high findings
  - `2` for config/runtime failures
- Safe-mode restrictions and allowlists remain enforced during live execution
- Docs clearly distinguish live execution-backed runs from fixture-backed
  examples

Verification commands

```bash
uv run python -m unittest tests.integration.test_pentest_run_live tests.integration.test_pentest_command_live
uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 4
- Milestone 5
- Milestone 8

## Milestone 10: Live Chaos Execution

Goal

- Replace the current fixture-backed chaos path with real Toxiproxy-backed
  chaos execution while preserving the existing safety, artifact, and exit-code
  contracts.

Deliverables

- Live Toxiproxy runtime integration in `toolkit chaos run`
- Real proxy lookup, toxic injection, and rollback execution
- Live health and optional metrics observation during experiments
- Abort-threshold enforcement against live observations
- One-active-experiment-per-app lock enforcement in real runs
- Safe live chaos operator docs and integration coverage

Files/directories to create

- `src/toolkit/chaos/execution.py`
- `tests/integration/test_chaos_run_live.py`
- `tests/integration/test_chaos_command_live.py`
- `docs/how-to/run-live-chaos.md`
- `docs/explanation/live-chaos-model.md`

Acceptance criteria

- `toolkit chaos run` performs real reversible proxy-based fault injection
  against a live reachable target
- Baseline capture, abort evaluation, and rollback are executed against live
  observations rather than fixture JSON
- Missing Toxiproxy runtime or missing required runtime dependencies fail
  clearly with exit code `2`
- Output artifacts remain stable under `outputs/<run-id>/`
- Exit codes remain unchanged:
  - `0` for a passing experiment
  - `1` for a resilience failure
  - `2` for configuration or runtime failures
- Docs clearly distinguish live chaos execution from the earlier fixture-backed
  path

Verification commands

```bash
uv run python -m unittest tests.integration.test_chaos_run_live tests.integration.test_chaos_command_live
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 6
- Milestone 9

## Milestone 11: Containerized Tool Runtime

Goal

- Make live pentest execution portable across generic Linux environments by
  running scanner tools through a managed container runtime instead of
  requiring host-installed binaries.

Deliverables

- Runtime abstraction for host-binary mode and container mode
- Container-backed execution for core pentest tools:
  - ZAP
  - Nuclei
  - Nmap
- Optional container-backed execution support for:
  - Trivy
  - Semgrep
- Mounted raw artifact capture from containerized runs
- Stable environment, network, and volume mapping contract
- Operator docs for Docker-first usage

Files/directories to create

- `src/toolkit/runtime/base.py`
- `src/toolkit/runtime/host.py`
- `src/toolkit/runtime/container.py`
- `src/toolkit/runtime/models.py`
- `tests/unit/runtime/`
- `tests/integration/test_pentest_run_container.py`
- `tests/integration/test_runtime_container.py`
- `docs/how-to/run-pentest-with-docker.md`
- `docs/explanation/container-runtime-model.md`

Acceptance criteria

- `toolkit pentest run` can execute enabled core adapters through a container
  runtime without requiring the scanner binaries on the host
- The same pentest artifact layout is preserved:
  - `raw/`
  - `normalized/findings.json`
  - `reports/executive-summary.md`
  - `manifest.json`
- Host-binary mode continues to work as a supported fallback
- Missing Docker/container runtime availability fails clearly with exit code `2`
- Containerized optional adapters still require explicit enablement and skip
  cleanly when unavailable
- Docs clearly state the preferred Docker-first path and the remaining safety
  boundaries

Verification commands

```bash
uv run python -m unittest tests.unit.runtime tests.integration.test_runtime_container tests.integration.test_pentest_run_container
uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 4
- Milestone 5
- Milestone 8
- Milestone 9
- Milestone 10

## Milestone 13: Target-Aligned Pentest Modes And Tool Separation

Goal

- Make live pentest execution reliable by aligning profiles to the actual
  assessment target, fixing the remaining container-mode runtime blockers, and
  separating remote web testing from source or artifact analysis.

Deliverables

- A remote-web pentest profile family for live target assessment
- Fixed ZAP container runtime output handling
- Fixed Trivy container first-run behavior
- Separate profile and execution expectations for:
  - remote webapp testing
  - source tree analysis
  - image or artifact analysis
- Clear docs that explain which tools belong to which assessment mode

Files/directories to create

- `docs/explanation/pentest-target-model.md`
- `docs/how-to/run-code-and-artifact-checks.md`
- `tests/integration/test_pentest_profiles_target_modes.py`

Acceptance criteria

- A remote webapp pentest profile can complete successfully without requiring
  Trivy or Semgrep to be active
- ZAP container mode writes artifacts successfully without the current
  `/zap/wrk` mount mismatch
- Trivy can run successfully in container mode for a valid filesystem or image
  target without failing on first-run DB behavior
- Semgrep is no longer implied to assess a remote running web server unless a
  source tree target is explicitly provided
- Docs clearly distinguish remote web pentest, code scan, and artifact/image
  scan workflows

Verification commands

```bash
uv run python -m unittest tests.integration.test_pentest_profiles_target_modes
uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline --runtime container
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 4
- Milestone 8
- Milestone 9
- Milestone 11

## Milestone 14: URL-First Audit And Edge Chaos UX

Goal

- Make the toolkit approachable for simple operators by adding zero-config,
  URL-first entrypoints for safe web auditing and simplified edge-chaos
  testing, while preserving the current YAML-driven workflow for advanced use.

Deliverables

- Top-level simplified commands:
  - `toolkit audit <url>`
  - `toolkit edge-chaos <url>`
  - `toolkit doctor`
- Ephemeral target derivation from a single URL without requiring repository
  YAML files
- Built-in safe remote-web audit profile for URL-first runs
- Automatic runtime selection for pentest execution:
  - prefer container mode when Docker is available
  - fall back to host mode when required binaries are present
- Managed local proxy boundary for URL-first edge-chaos execution
- Updated operator docs that present the URL-first path as the easiest
  onboarding flow and keep the YAML path as the advanced mode

Files/directories to create

- `src/toolkit/commands/audit.py`
- `src/toolkit/commands/doctor.py`
- `src/toolkit/commands/edge_chaos.py`
- `src/toolkit/targets/`
- `src/toolkit/runtime/selector.py`
- `src/toolkit/chaos/edge_runtime.py`
- `tests/unit/targets/`
- `tests/unit/runtime/test_selector.py`
- `tests/integration/test_audit_command.py`
- `tests/integration/test_doctor_command.py`
- `tests/integration/test_edge_chaos_command.py`
- `docs/tutorials/quickstart-url-first.md`
- `docs/how-to/run-url-audit.md`
- `docs/how-to/run-edge-chaos.md`
- `docs/explanation/url-first-ux-model.md`

Acceptance criteria

- `toolkit audit <url>` can execute a safe remote-web assessment without
  requiring `apps.yaml`, `pentest-profiles.yaml`, or `chaos-profiles.yaml`
- URL-first audit runs write the same core artifact layout used by the current
  pentest flow:
  - `raw/`
  - `normalized/findings.json`
  - `reports/executive-summary.md`
  - `manifest.json`
- `toolkit doctor` reports whether audit and edge-chaos execution are ready and
  gives actionable remediation when Docker, host binaries, or the simplified
  proxy runtime are unavailable
- `toolkit edge-chaos <url>` can execute one safe reversible edge fault against
  a URL-derived target, monitor `GET /`, and always attempt rollback
- The current YAML-driven commands remain supported and do not regress
- Docs clearly distinguish:
  - URL-first ad hoc usage
  - advanced managed-target usage
  - edge-chaos versus full proxy-attached chaos workflows

Verification commands

```bash
uv run python -m unittest tests.unit.targets tests.unit.runtime.test_selector tests.integration.test_audit_command tests.integration.test_doctor_command tests.integration.test_edge_chaos_command
uv run toolkit doctor
uv run toolkit audit http://127.0.0.1:8000
uv run toolkit edge-chaos http://127.0.0.1:8000
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 4
- Milestone 5
- Milestone 6
- Milestone 9
- Milestone 10
- Milestone 11
- Milestone 13

## Milestone 15: URL-First Code Audit UX

Goal

- Make static analysis accessible to simple operators by adding a zero-config
  codebase audit command that runs Semgrep and Trivy against a local source
  tree without requiring repository YAML config or explicit pentest profiles.

Deliverables

- Top-level simplified command:
  - `toolkit code-audit <path>`
- Optional tool narrowing flag:
  - `--tool semgrep`
  - `--tool trivy`
- Ephemeral source-tree target derivation from a filesystem path
- Built-in safe code-audit profile that maps to `assessment_mode: source_tree`
- Runtime selection and readiness diagnostics for Semgrep and Trivy execution
- Artifact, normalization, and Markdown reporting parity with the existing
  audit and pentest flows
- Operator docs that clearly distinguish:
  - live remote web audit
  - codebase audit
  - image or artifact analysis

Files/directories to create

- `src/toolkit/commands/code_audit.py`
- `src/toolkit/codeaudit/`
- `src/toolkit/targets/source_tree.py`
- `tests/unit/codeaudit/`
- `tests/unit/targets/test_source_tree.py`
- `tests/integration/test_code_audit_command.py`
- `docs/tutorials/quickstart-code-audit.md`
- `docs/how-to/run-code-audit.md`
- `docs/explanation/code-audit-model.md`

Acceptance criteria

- `toolkit code-audit <path>` runs without requiring `apps.yaml`,
  `pentest-profiles.yaml`, or `chaos-profiles.yaml`
- The default code-audit path runs both:
  - `semgrep`
  - `trivy`
- `--tool semgrep` runs only Semgrep
- `--tool trivy` runs only Trivy filesystem analysis
- The built-in code-audit path never enables remote-web tools:
  - `zap`
  - `nuclei`
  - `nmap`
- The command writes the standard run artifact layout:
  - `raw/`
  - `normalized/findings.json`
  - `reports/executive-summary.md`
  - `manifest.json`
- Docs clearly explain when to use:
  - `toolkit audit <url>`
  - `toolkit code-audit <path>`
  - advanced profile-driven source tree or image workflows

Verification commands

```bash
uv run python -m unittest tests.unit.codeaudit tests.unit.targets.test_source_tree tests.integration.test_code_audit_command
uv run toolkit code-audit .
uv run toolkit code-audit . --tool semgrep
uv run toolkit code-audit . --tool trivy
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 4
- Milestone 5
- Milestone 8
- Milestone 11
- Milestone 13
- Milestone 14

## Milestone 16: Authenticated And Discovery-Driven URL Audit

Goal

- Expand `toolkit audit <url>` from a seed-URL, unauthenticated audit into a
  safer authenticated and discovery-driven assessment flow that can reach real
  operator-relevant application surfaces while preserving the zero-config UX.
  Treat API-based JSON login as the primary documented automated auth path for
  typical modern web applications, while keeping classic HTML form login as a
  secondary compatibility path and bearer, cookie, and session modes as
  secondary expert/manual paths.

Deliverables

- URL-first authenticated audit inputs that reuse the existing auth contract:
  - `--auth-mode none|bearer_token|cookie|session|form`
  - `--auth-mode api_login`
  - `--token-env-var`
  - `--cookie-name`
  - `--cookie-value-env-var`
  - `--session-header`
  - `--session-value-env-var`
  - `--login-url`
  - `--username-env-var`
  - `--password-env-var`
- `api_login`-first operator guidance for standard web apps that:
  - use a JSON login API
  - return reusable auth material such as bearer tokens, cookies, or session
    values
  - require the login API route to be enabled and reachable during the run
- Form-login compatibility guidance for classic HTML login forms that:
  - use standard username/password fields
  - return reusable authenticated cookies after login
  - require the visible login route to be enabled and reachable during the run
- Explicit fail-closed auth behavior for URL-first form and API login when:
  - the login route is disabled
  - the login route is unreachable
  - the response cannot be parsed
  - the response returns no reusable auth material
- `httpx`-backed preflight fingerprinting for the supplied URL
- `katana`-backed route discovery for links, JS-referenced endpoints,
  sitemaps, and robots content
- Route-aware audit execution where ZAP and Nuclei consume the seed URL plus
  discovered routes
- Audit report enrichment that includes:
  - target fingerprint summary
  - discovery coverage summary
  - auth mode provenance without secret leakage
  - findings grouped against the discovered audit surface
- Doctor and runtime-readiness updates for the expanded audit toolchain:
  - `httpx`
  - `katana`
  - `zap`
  - `nuclei`
  - `nmap`

Files/directories to create

- `src/toolkit/audit/`
- `src/toolkit/audit/discovery.py`
- `src/toolkit/audit/fingerprint.py`
- `tests/unit/audit/`
- `tests/integration/test_audit_command.py` updates for authenticated and
  discovery-driven flows
- `docs/tutorials/quickstart-authenticated-audit.md`
- `docs/how-to/run-authenticated-url-audit.md`
- `docs/explanation/url-audit-model.md`

Acceptance criteria

- `toolkit audit <url>` continues to work with no auth flags and no YAML files
- `toolkit audit <url>` without auth flags remains valid even when the target
  login route is disabled
- `toolkit audit <url>` can accept URL-first authenticated inputs through CLI
  flags and environment-variable references without requiring `apps.yaml`
- auth remains optional overall for `toolkit audit <url>`
- at most one auth mode may be selected per run
- mode-specific auth flags become required when that mode is selected
- mixed auth-mode flag sets fail closed with exit code `2`
- `api_login` is the primary documented automated auth mode for apps whose
  login logic is API-based with JSON
- `form` remains a secondary compatibility mode for basic HTML login forms
- `toolkit audit <url> --auth-mode form ...` fails with exit code `2` when
  `login_url` is disabled, unreachable, rejected, or returns no reusable
  session cookies
- `toolkit audit <url> --auth-mode form ...` never silently downgrades to an
  unauthenticated audit
- `toolkit audit <url> --auth-mode api_login ...` fails with exit code `2`
  when `login_url` is disabled, unreachable, rejected, unparseable, or
  returns unusable auth material
- `toolkit audit <url> --auth-mode api_login ...` never silently downgrades to
  an unauthenticated audit
- Secret material is never echoed into stdout, reports, manifests, or raw
  artifacts
- `httpx` fingerprints the target before the deeper audit stages begin
- `katana` discovers additional routes and writes a deterministic discovery
  artifact under `outputs/<run-id>/raw/`
- ZAP and Nuclei run against the seed URL plus discovered routes
- Nmap remains limited to conservative host and service context rather than
  route discovery
- The audit report includes target fingerprinting, discovery coverage, and
  auth-mode context alongside findings
- `toolkit doctor` can report readiness for the expanded URL-first audit
  toolchain

Verification commands

```bash
uv run python -m unittest tests.unit.audit tests.integration.test_audit_command tests.integration.test_doctor_command
uv run toolkit doctor
uv run toolkit audit http://127.0.0.1:8000
uv run toolkit audit http://127.0.0.1:8000 --auth-mode api_login --login-url http://127.0.0.1:8000/api/login --username-env-var TOOLKIT_AUDIT_USERNAME --password-env-var TOOLKIT_AUDIT_PASSWORD --login-content-type json --login-username-field username --login-password-field password --auth-result bearer_json --auth-result-path token
uv run toolkit audit http://127.0.0.1:8000 --auth-mode bearer_token --token-env-var TOOLKIT_AUDIT_TOKEN
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 4
- Milestone 5
- Milestone 9
- Milestone 11
- Milestone 13
- Milestone 14

## Milestone 17: URL-First Audit Hardening And Trustworthiness

Goal

- Harden the default URL-first audit path so operators can trust the outcome
  on common real targets, especially authenticated and containerized runs,
  without widening the default scan intensity or changing the safe-by-default
  posture introduced in Milestone 16.

Deliverables

- A hardened URL-first audit runtime contract for common real-world targets:
  - authenticated form-login runs
  - authenticated API-login runs
  - containerized ZAP execution
  - discovery-driven route scope with malformed-route filtering
- ZAP container-runtime hardening that keeps wrapper-generated side files,
  summaries, and reports inside the mounted output directory and avoids false
  runtime failures caused by wrapper argument parsing or container-path
  assumptions
- Robust auth-session transport handling for reused login state, including:
  - duplicate cookie names across paths or scopes
  - explicit `Cookie` header transport when cookie jars cannot be represented
    as a simple mapping
  - secret-safe propagation of auth material into ZAP, Nuclei, and Katana
- Discovery-scope sanitization and quality controls that:
  - remove malformed crawler artifacts
  - drop obviously low-value helper and static routes from downstream scope
  - diversify selected route families so one URL family does not dominate the
    safe audit budget
  - preserve deterministic route selection for the default audit mode
- Clearer audit outcome semantics for core scanner execution, including:
  - accepted artifact-backed completions
  - hard runtime failures
  - parse failures
  - timeouts
  - preserved findings from tools that completed successfully even when a
    different core tool failed
- Operator-facing reporting and documentation updates that explain:
  - which tool actually failed
  - when a run is partially useful versus fully failed
  - what findings were still preserved
  - which URL-first hardening rules exist to keep scans bounded and reliable
- Regression coverage for common target patterns such as:
  - WordPress-style form login
  - duplicate-cookie sessions
  - auth headers with spaces or multi-cookie values
  - malformed discovery output from JavaScript-heavy pages

Files/directories to create

- `tests/unit/audit/` fixture and regression additions for malformed and
  low-value discovered-route cases
- `tests/unit/adapters/test_zap.py` hardening coverage for auth-backed ZAP
  execution and wrapper argument handling
- `tests/unit/runtime/test_container_runtime.py` updates for containerized ZAP
  output-directory and environment assumptions
- `tests/unit/auth/` additions for duplicate-cookie and explicit-cookie-header
  transport behavior
- `tests/integration/test_audit_command.py` updates for hardened URL-first
  failure and partial-success behavior
- `docs/how-to/run-url-audit.md` updates for operator troubleshooting and
  trustworthy-result expectations
- `docs/reference/output-artifacts.md` updates for partial-result and
  preserved-artifact semantics
- `docs/explanation/url-audit-model.md` updates for the hardened default audit
  contract

Acceptance criteria

- Auth-backed containerized ZAP runs do not fail because of wrapper-generated
  side-file paths, quoted header values, or multi-cookie auth material
- Duplicate-cookie login sessions no longer crash auth bootstrap and can be
  reused safely during audit execution
- URL-first audit filters malformed or obviously invalid discovered routes
  before they are handed to downstream scanners
- Default `zap_routes` and `nuclei_routes` remain deterministic, bounded, and
  diversified across route families instead of clustering on one crawler-heavy
  section of the target
- `toolkit audit <url>` preserves findings from tools that completed
  successfully even when another core tool fails, while still exiting with `2`
  for a true core-tool runtime failure
- Accepted artifact-backed non-zero tool exits do not become false hard
  failures in logs, reports, or final run status
- Audit logs and reports identify the actual failed tool and failure reason
  without exposing secrets
- The current default audit behavior remains safe and bounded:
  - no new default tools
  - no broader default rule/template allowlists
  - no deeper default route budgets beyond the hardened bounded scope
- Hardening covers both unauthenticated and authenticated URL-first audit
  paths

Verification commands

```bash
uv run python -m unittest tests.unit.auth tests.unit.audit tests.unit.adapters.test_zap tests.unit.runtime.test_container_runtime tests.integration.test_audit_command
uv run toolkit doctor
uv run toolkit audit http://127.0.0.1:8000
uv run toolkit audit http://127.0.0.1:8000 --auth-mode form --login-url http://127.0.0.1:8000/login --username-env-var TOOLKIT_AUDIT_USERNAME --password-env-var TOOLKIT_AUDIT_PASSWORD --login-username-field username --login-password-field password
uv run toolkit audit http://127.0.0.1:8000 --auth-mode api_login --login-url http://127.0.0.1:8000/api/login --username-env-var TOOLKIT_AUDIT_USERNAME --password-env-var TOOLKIT_AUDIT_PASSWORD --login-content-type json --login-username-field username --login-password-field password --auth-result bearer_json --auth-result-path token
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 4
- Milestone 5
- Milestone 9
- Milestone 11
- Milestone 13
- Milestone 14
- Milestone 16

## Milestone 18: Opt-In URL Audit Intensity Modes

Goal

- Add explicit operator-selectable intensity modes to `toolkit audit <url>` so
  broader coverage and longer scanner budgets are available on demand while
  keeping the omitted/default audit safe, bounded, and read-only.

Deliverables

- `--intensity safe|balanced|deep` for `toolkit audit <url>`
- Locked intensity semantics where omitted intensity is equivalent to `safe`
- A centralized intensity planning surface for route limits, scanner budgets,
  Nmap profile selection, and Nuclei allowlists
- Operator-visible reporting and documentation that explain the difference
  between `safe`, `balanced`, and `deep`

Acceptance criteria

- omitted `--intensity` behaves exactly like `safe`
- `safe` preserves the current bounded default URL audit behavior
- `balanced` increases route and scanner budgets relative to `safe`
- `deep` increases route and scanner budgets relative to `balanced`
- all intensity modes remain read-only and non-destructive
- the default Nuclei allowlist remains unchanged when intensity is omitted

Verification commands

```bash
uv run python -m unittest tests.unit.audit tests.unit.adapters.test_zap tests.unit.adapters.test_nuclei tests.unit.adapters.test_nmap tests.unit.pentest.test_runner tests.unit.test_report_writer tests.integration.test_audit_command
uv run toolkit doctor
uv run pre-commit run --all-files
```

Dependencies on earlier milestones

- Milestone 1
- Milestone 2
- Milestone 3
- Milestone 4
- Milestone 5
- Milestone 9
- Milestone 11
- Milestone 13
- Milestone 14
