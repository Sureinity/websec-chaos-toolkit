# AGENTS.md

These instructions apply to this repository directory. If a deeper
`AGENTS.md` is added later, follow the nearest file.

## Project Status (Current State)

- Treat this file as the authoritative project contract.
- The repository is no longer documentation-only.
- The repository now contains a bootstrap Python package, packaging metadata,
  valid sample configuration files, basic tests, Diataxis documentation
  structure, and a scaffolded CLI surface.
- `toolkit audit <url>` is now implemented for zero-config remote web audits.
- `toolkit edge-chaos <url>` is now implemented for managed local edge-chaos
  experiments against one URL-derived target.
- `toolkit code-audit <path>` is now implemented for zero-config source-tree
  audits using Semgrep and/or Trivy with host/container runtime selection.
- `toolkit validate` is now implemented for config loading and validation.
- `toolkit pentest run` executes real scanner binaries (zap, nuclei, nmap)
  against a live target. A fixture-backed flow is preserved for onboarding and
  offline testing.
- Optional Trivy and Semgrep adapters participate in pentest runs when
  explicitly enabled in a profile, and skip cleanly when their binaries are
  unavailable.
- `toolkit chaos run` executes live Toxiproxy-backed experiments. A
  fixture-backed flow is preserved for onboarding and offline testing.
- `toolkit report build` is now implemented for stored normalized result
  bundles.
- `toolkit doctor` is now implemented for simplified audit runtime readiness
  diagnostics.
- Scanner adapters for ZAP, Nuclei, Nmap, Trivy, and Semgrep are implemented
  with a shared contract, process runner, and normalizers.
- Optional external smoke tests exist behind the
  `TOOLKIT_RUN_EXTERNAL_TOOL_TESTS=1` environment flag.
- The repository does not yet contain full schema validation coverage,
  notification delivery, or end-to-end report generation pipelines.
- `security-testing-resources.md` exists as placeholder background reading
  material. Treat it as reference material, not as a behavioral contract.

## Project Overview (Future Intent)

- Build a single Python-first package with one CLI entrypoint for scheduled or
  operator-triggered testing of internal web applications and APIs in `local`
  and `staging` environments.
- Keep two top-level product domains in v1:
  - `pentest`
  - `chaos`
- Keep the toolkit DAST-first with limited supporting static and configuration
  checks.
- Orchestrate mature external tools. Do not reimplement scanning engines or
  fault injection engines.
- Use external schedulers in v1. Do not assume a daemon, web UI, or
  CI/CD-native runtime.
- Keep standard run modes to validation, operator-triggered run-once execution,
  and scheduled execution through the same CLI.
- Optimize for minimal human intervention after initial per-application
  configuration, while expecting periodic rule and profile tuning.
- Keep safe mode, explicit allowlists, and fail-closed validation as defaults.
- Support authenticated testing in v1 through config-driven bearer token,
  cookie or session injection, or scripted username and password login.
- Keep Docker- and VM-based chaos targets first-class in v1.
- Treat Kubernetes support, full SSO or MFA orchestration, destructive
  exploitation, password spraying, brute force, data mutation, logic-heavy
  manual business-flow abuse testing, broad infrastructure outages, and random
  kill loops as out of scope for v1.
- Treat framework differences such as Laravel, Python, C#, and Vue
  applications as configuration variants rather than separate product lines.

## Current Repo Layout

- Top-level files that exist now:
  - `AGENTS.md`
  - `README.md`
  - `security-testing-resources.md`
  - `pyproject.toml`
  - `.pre-commit-config.yaml`
  - `ruff.toml`
  - `mypy.ini`
  - `pytest.ini`
  - `.gitignore`
  - `apps.yaml`
  - `pentest-profiles.yaml`
  - `chaos-profiles.yaml`
- Top-level directories that exist now:
  - `src/`
  - `tests/`
  - `docs/`
  - `examples/`
  - `config/`
- The Python package root is `src/toolkit/`.
- The CLI command tree is implemented under `src/toolkit/commands/`.
- Test layout is split into `tests/unit/` and `tests/integration/`.
- Documentation is organized using Diataxis under `docs/tutorials/`,
  `docs/how-to/`, `docs/reference/`, and `docs/explanation/`.
- The repository-level YAML files are valid sample configs for the current
  validation command. Keep them aligned with the implemented schema.

## Package Boundaries

- Keep boundaries explicit:
  - CLI entrypoints and command wiring
  - YAML config loading and validation
  - pentest orchestration
  - chaos orchestration
  - tool adapters
  - auth and session helpers
  - result normalization
  - report generation
  - safety guards and abort logic
- Keep the single Python package under `src/toolkit/`.
- Keep raw tool outputs, normalized JSON bundles, and Markdown summaries grouped
  by run in a stable output layout.

## Current CLI Behavior

- The intended public interface is already wired:
  - `toolkit audit <url> [--runtime host|container] [--intensity safe|balanced|deep] [-v|-vv|-vvv]`
  - `toolkit edge-chaos <url> [--fault <name>]`
  - `toolkit code-audit <path> [--tool semgrep|trivy] [--runtime host|container] [-v|-vv|-vvv]`
  - `toolkit validate --app <id> --env <env>`
  - `toolkit doctor`
  - `toolkit pentest run --app <id> --env <env> --profile <name> [-v|-vv|-vvv]`
  - `toolkit chaos run --app <id> --env <env> --profile <name>`
  - `toolkit report build --run-id <id>`
- Current behavior:
  - `toolkit audit` derives an ad hoc target from a single URL, executes a
    safe remote-web audit, writes raw artifacts, normalized findings, and a
    Markdown summary under `outputs/<run-id>/`, emits structured runtime log
    records for tool start, output, and finish events, and exits with `0`,
    `1`, or `2`; auto-selects `container` then `host` runtime when possible;
    curates a smaller discovered-route subset for ZAP and a larger but filtered
    same-origin route set for Nuclei; omitted intensity behaves like `safe`
    and explicit `balanced` and `deep` modes increase bounded route and
    scanner budgets without changing the read-only safety posture;
    `-v` shows stderr tool output, `-vv` adds stdout tool output, and `-vvv`
    adds command-level context such as command and working directory
  - `toolkit edge-chaos` derives an ad hoc chaos target from a single URL,
    starts a managed local Toxiproxy container, creates one local proxy,
    probes the requested URL path through that proxy, injects one reversible
    fault, verifies rollback recovery, and writes raw artifacts, normalized
    findings, and a Markdown summary under `outputs/<run-id>/`, and exits with
    `0`, `1`, or `2`
  - `toolkit code-audit` derives an ad hoc source-tree target from one local
    path, runs Semgrep and/or Trivy using the built-in `source_tree` profile,
    selects host or container runtime for the selected tools, writes raw
    artifacts, normalized findings, and a Markdown summary under
    `outputs/<run-id>/`, emits structured runtime log records for tool start,
    output, and finish events, and exits with `0`, `1`, or `2`; `-v` shows
    stderr tool output, `-vv` adds stdout tool output, and `-vvv` adds
    command-level context such as command and working directory
  - `toolkit validate` loads and validates repository YAML config from the
    current working directory and exits with `0` on success or `2` on
    validation/runtime failure
  - `toolkit doctor` reports simplified audit runtime readiness and the
    current edge-chaos readiness status
  - `toolkit pentest run` executes real scanner binaries against a live target,
    writes raw artifacts, normalized findings, and a Markdown summary under
    `outputs/<run-id>/`, emits structured runtime log records for tool start,
    output, and finish events, and exits with `0`, `1`, or `2`; `-v` shows
    stderr tool output, `-vv` adds stdout tool output, and `-vvv` adds
    command-level context such as command and working directory; requires core
    binaries on `PATH`; optional Trivy and Semgrep join when explicitly enabled
  - `toolkit chaos run` executes a live Toxiproxy-backed chaos experiment,
    writes raw artifacts, normalized findings, and a Markdown summary under
    `outputs/<run-id>/`, and exits with `0`, `1`, or `2`; requires a running
    Toxiproxy server and a configured proxy
  - `toolkit report build` rebuilds a Markdown summary from
    `outputs/<run-id>/normalized/findings.json` and exits with `0` on success
    or `2` on runtime/input failure
- Both pentest and chaos paths execute against live targets. Fixture-backed
  flows are preserved for onboarding and offline testing.

## Future CLI Commands & Interfaces

- Keep these YAML files as the managed and advanced configuration surface:
  - `apps.yaml`
  - `pentest-profiles.yaml`
  - `chaos-profiles.yaml`
- Keep the simplified URL-first path additive and preserve the YAML-driven
  commands for advanced and repeatable workflows.
- Keep minimum config expectations:
  - `apps.yaml` should describe app id, environment, base URL, host targets,
    auth method, health endpoint, optional metrics endpoint or query, and
    enabled modules.
  - `pentest-profiles.yaml` should describe tool enablement, scan depth or
    profile, template or rule allowlists, and schedule labels when used.
  - `chaos-profiles.yaml` should describe fault types, target dependency or
    service, baseline duration, experiment duration, abort thresholds, and
    rollback method.
- Keep normalized result fields:
  - `app_id`
  - `environment`
  - `target`
  - `tool`
  - `category`
  - `severity`
  - `confidence`
  - `evidence`
  - `remediation_summary`
  - `timestamps`
- Keep output artifacts:
  - raw tool outputs per run
  - normalized JSON result bundle per run
  - Markdown executive summary per run, grouped by app and severity
- Keep stable exit codes:
  - `0` for no findings or a passing experiment
  - `1` for medium or high findings, or a resilience failure
  - `2` for configuration or runtime errors
- Keep notifications optional in v1. If implemented, use a simple webhook sink
  after report generation. Do not make notifications a core dependency.

## Installation & Setup

Currently Applicable

- The repository now includes a `pyproject.toml` package definition.
- Use Python-first tooling.
- Use `uv` by Astral as the canonical Python package manager and tool runner.
- Canonical bootstrap commands:
  - `uv sync --extra dev`
- The repository includes `.pre-commit-config.yaml`. Install hooks with
  `uv run pre-commit install`.
- Run all hooks with `uv run pre-commit run --all-files`.
- External binaries such as ZAP, Nuclei, Nmap, and Toxiproxy are not required
  for the current scaffold tests.
- Trivy and Semgrep are also not required for the default local test suite.

Planned / Future Expectations

- Expected development libraries:
  - `typer`
  - `pydantic`
  - `PyYAML`
  - `httpx`
  - `tenacity`
  - `jinja2`
  - `rich`
  - `prometheus-client`
- Expected development tools:
  - `pytest`
  - `pytest-cov`
  - `respx`
  - `mypy`
  - `ruff`
  - `pre-commit`
- Expected required external tools:
  - `OWASP ZAP`
  - `nuclei`
  - `nmap`
  - `toxiproxy-server`
- Expected optional external tools:
  - `trivy`
  - `semgrep`
  - `docker`
  - `docker compose`
- If package wrappers such as `make`, `tox`, or task runners are added later,
  document the canonical `uv`-based commands here and keep them accurate.

## Development Workflow

Currently Applicable

- Keep changes small and reviewable.
- Separate orchestration code from tool-specific adapter code.
- Update docs, examples, tests, and this file whenever public behavior changes.
- Keep documentation changes aligned with the actual repository state.
- Keep placeholder behavior explicit. Do not silently upgrade a stub into
  partially working behavior without updating tests and docs.
- Prefer `uv run ...` for local development commands documented in this
  repository.
- Use structured Conventional Commit messages.

Planned / Future Expectations

- Build the project in this order unless a documented reason requires a
  different sequence:
  - configuration schema, CLI skeleton, validation flow, and report scaffolding
  - ~~ZAP, Nuclei, and Nmap adapters with normalized findings~~ (implemented)
  - ~~fixture-backed pentest planner and orchestration runner~~ (implemented)
  - ~~Toxiproxy-based chaos runner with health or metrics baseline and abort logic~~ (implemented: live execution via real Toxiproxy runtime)
  - ~~scheduler-facing docs, sample configs, and pilot coverage for one or two internal apps~~ (implemented: example config packs, operator how-to guides, safety model doc, and schedule-execution guide)
  - ~~optional Trivy and Semgrep adapters for local code, artifact, or image checks~~ (implemented: fixture-backed, explicitly enabled, skip cleanly when unavailable)
  - ~~live chaos execution through a real Toxiproxy runtime~~ (implemented)
  - ~~containerized tool runtime for portable execution across generic Linux environments~~ (implemented: Docker container backend via `--runtime container`)
  - target-aligned pentest modes and tool-role separation so remote web
    pentest, code scanning, and artifact analysis are not conflated
  - URL-first operator UX with zero-config audit, readiness diagnostics, and a
    simplified edge-chaos path for ad hoc assessments
  - URL-first codebase audit UX with built-in Semgrep and Trivy execution for
    local source trees
- Keep the detailed milestone sequence in
  `docs/explanation/implementation-roadmap.md` aligned with this order.
- Keep allowed commit types to:
  - `feat`
  - `fix`
  - `docs`
  - `refactor`
  - `test`
  - `style`
  - `chore`
- Write commit titles as:
  - `type(optional-scope): short summary`
- Keep the summary concise:
  - imperative mood
  - about 50 characters or fewer when practical
- After the title, include a short bullet list in the commit body.
- Each commit-body bullet should:
  - start with a verb
  - describe what changed
  - describe why it matters when that is not obvious
- Prefer a wrapped body width of about 72 characters.
- Mark breaking changes with `!` in the header or a `BREAKING CHANGE:` footer.
- Keep commits focused. Do not mix refactors and behavior changes unless they
  are inseparable.

## Testing Expectations

Currently Applicable

- Keep unit tests under `tests/unit/`.
- Keep integration-style scaffold checks under `tests/integration/`.
- Run `uv run pytest` for the current scaffold when dependencies are installed.
- Use deterministic fixtures and assertions so bootstrap checks remain stable.

Planned / Future Expectations

- Add unit tests for config validation, adapter behavior, result normalization,
  and safety guards.
- Add command-level tests when CLI behavior changes.
- Add tests for valid and invalid YAML examples when schema changes.
- Verify both JSON and Markdown outputs when reporting changes.
- Verify baseline capture, rollback, abort behavior, and recovery reporting when
  chaos behavior changes.
- Gate integration tests behind explicit markers or environment checks when
  they require external binaries or live services.
- Cover these behaviors over time:
  - reject missing allowlists
  - reject missing health endpoints
  - reject invalid auth config
  - reject missing rollback for chaos profiles
  - accept minimal valid config for unauthenticated and authenticated apps
  - run against a deliberately vulnerable local web app and verify normalized
    findings are produced
  - verify safe scan profiles do not perform destructive actions
  - verify auth injection works for bearer token, cookie or session injection,
    and scripted form login
  - verify disabled tools are skipped cleanly
  - inject latency via proxy and verify baseline, observation, rollback, and
    recovery reporting
  - trigger abort when health or metrics thresholds breach
  - verify only one experiment runs per app
  - verify rollback occurs on error or timeout
  - confirm raw outputs, JSON bundles, and Markdown summaries are produced for
    each run
  - confirm severities and run status remain stable and deterministic
  - verify scheduler-compatible non-interactive execution
  - verify idempotent output directory creation and log rotation behavior
  - confirm production-like targets are refused unless explicitly allowed
  - confirm excluded destructive actions cannot be selected through
    configuration

## Coding Conventions

Currently Applicable

- Keep instructions explicit and actionable.
- Use typed Python throughout new runtime code.
- Type-annotate public interfaces and config models.
- Keep optional integrations optional. Missing binaries should fail clearly or
  skip cleanly once adapters exist.
- Avoid hidden global state, import-time side effects, and
  environment-specific hardcoding.

Planned / Future Rules

- Use structured validation such as Pydantic for user-facing configuration.
- Normalize all scanner and experiment results into a shared result model before
  reporting.
- Keep raw tool output as an artifact. Do not make report generation depend
  directly on vendor-specific raw output shapes.
- Keep documentation under the Diataxis framework:
  - tutorials for learning-oriented walkthroughs
  - how-to guides for task-focused procedures
  - reference for commands, config keys, schemas, outputs, and exit codes
  - explanation for rationale, tradeoffs, and concepts
- Update the relevant Diataxis documents when CLI behavior, config schema,
  outputs, tools, hooks, or contributor workflow changes.

## Safety and Guardrails

Currently Applicable

- Do not commit secrets, real credentials, real session material, or
  unsanitized target data.
- Do not add real production targets or unsafe sample data to this repository.
- Do not assume destructive scanning or unsafe chaos behavior is permitted.
- Keep reference material sanitized.
- Keep scaffold commands fail-closed rather than implying unsafe execution is
  ready.

Planned / Future Rules

- Never widen a target allowlist implicitly.
- Never disable safe mode by default.
- Never add destructive scan behavior to default profiles.
- Keep ZAP active scanning limited to safe rules and profiles.
- Keep Nuclei templates restricted to curated allowlisted sets.
- Keep Nmap usage restricted to configured ports or conservative discovery
  profiles.
- Limit pentest coverage to low-risk, high-value findings such as exposed admin
  or debug endpoints, missing or weak security headers, known CVE-style
  exposures, TLS or configuration weaknesses, and safe common injection
  indicators.
- Allow default-credential or obvious exposure checks only when the selected
  engine supports them safely and non-destructively.
- Require explicit target allowlists and environment allowlists.
- Require an explicit rollback action for every injectable chaos fault.
- Require duration caps, abort thresholds, and one active experiment per app.
- Keep chaos faults limited to safe, reversible faults such as latency,
  bandwidth throttling, packet loss or timeout simulation, dependency
  connection refusal through proxy control, and controlled restart only when
  explicitly enabled.
- Exclude disk corruption, data deletion, broad CPU or memory stress,
  infrastructure-wide outages, and random kill loops.
- Require a steady-state baseline before fault injection.
- Apply one chaos fault at a time.
- Require health monitoring during experiments.
- Treat metrics as optional. Allow health-only mode when metrics are absent.

## Pre-commit Hooks

Currently Applicable

- `.pre-commit-config.yaml` exists in this directory.
- Use `pre-commit` as the default local quality gate before a PR or final
  handoff.
- Keep hook coverage focused on fast, deterministic checks.
- At minimum, maintain hooks for file hygiene, YAML validation, and Python
  linting and formatting.

Planned / Future Expectations

- Enforce lightweight static validation through hooks when practical instead of
  undocumented manual steps.
- Update this file and contributor docs when hooks are added, removed, or
  materially changed.

## Do Not

- Do not treat placeholder commands, adapters, tests, or config files as fully
  implemented production behavior.
- Do not change public CLI behavior, YAML schema, JSON output shape, or
  exit-code semantics without updating tests, docs, examples, and this file.
- Do not add destructive security checks, brute-force behavior, password
  spraying, unsafe chaos experiments, or production-by-default behavior.
- Do not bypass `pre-commit` once hook configuration exists.
- Do not scatter shell-heavy tool invocations across the codebase when an
  adapter boundary is more appropriate.
- Do not write documentation that mixes Diataxis modes without a clear primary
  mode.
