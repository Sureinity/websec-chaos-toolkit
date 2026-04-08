# Live Execution Model

This document explains how the live pentest execution path works, what
distinguishes it from the fixture-backed path, what is still planned, and where
the safety boundaries are enforced.

## Two Execution Modes

The toolkit supports two pentest execution modes. Both satisfy the same
contract: same artifact layout, same exit-code semantics, same normalized
result schema.

### Fixture-backed mode

Used for onboarding, offline testing, and CI without real scanner installations.

- reads pre-recorded tool output from repository fixture files
  (`tests/fixtures/zap/`, `tests/fixtures/nuclei/`, `tests/fixtures/nmap/`)
- no external binaries required
- no live target required
- entry point: `run_pentest_fixture_flow()` in `src/toolkit/pentest/runner.py`

### Live execution mode

Used to test a real running application with real scanner binaries.

- runs external scanner binaries (`zap-baseline.py`, `nuclei`, `nmap`) against
  a live target URL
- requires installed binaries for all enabled core tools
- requires a live and reachable target at `app.base_url`
- entry point: `run_pentest_live_flow()` in `src/toolkit/pentest/runner.py`

`toolkit pentest run` uses the live execution mode.

## Live Execution Lifecycle

```
CLI invocation
  ↓
load and validate app / environment / profile
  ↓
resolve runtime auth from environment variables
  ↓
build deterministic tool plan (zap → nuclei → nmap → [trivy] → [semgrep])
  ↓
for each planned tool:
  check binary availability
    CORE tool missing binary → failed result (exit 2)
    OPTIONAL tool missing binary → skipped result (run continues)
    disabled tool → skipped result (run continues)
  execute via process runner
    non-zero exit or timeout → failed result
    success → parse output → normalized findings
  ↓
write raw artifacts to outputs/<run-id>/raw/<tool>/
write normalized findings to outputs/<run-id>/normalized/findings.json
rebuild outputs/<run-id>/reports/executive-summary.md
write manifest to outputs/<run-id>/manifest.json
return PentestRunSummary with stable exit code
```

## Execution Service

The live path delegates adapter execution to
`src/toolkit/pentest/execution.py`. This module:

- receives a `PentestPlan` from the planner
- calls `execute_planned_tool()` for each tool in plan order
- applies role-based availability logic (CORE vs OPTIONAL)
- calls `run_tool_execution()` from `src/toolkit/adapters/process.py`
- returns a tuple of `AdapterRunResult` objects to the runner

The runner (`run_pentest_live_flow()`) is responsible for:

- creating the run context and output directories
- resolving auth before execution starts
- invoking the execution service
- collecting findings and writing downstream artifacts

These responsibilities are kept separate so command, runner, and execution
service can be tested and modified independently.

## Required Versus Optional Tools

```
CORE tools:   zap, nuclei, nmap
OPTIONAL tools: trivy, semgrep
```

The `PentestToolRole` enum in `src/toolkit/pentest/contracts.py` and the
`role` field on `PentestPlannedTool` carry this classification. The execution
service reads the role to decide skip-versus-fail behavior without knowing the
tool name.

| Role | Missing binary | Adapter failure |
|------|---------------|-----------------|
| CORE | hard fail — exit 2 | hard fail — exit 2 |
| OPTIONAL | clean skip | clean skip |

All tools are constrained by safe-mode settings. An adapter refuses to build
its command when `safe_mode: false` is set in the profile and returns a
config error (exit 2) before any subprocess call is made.

## Artifact Contract

Both execution modes produce the same layout:

```
outputs/<run-id>/
  manifest.json
  raw/<tool>/results.<ext>    ← written by the real tool subprocess
  normalized/findings.json    ← written by the runner from parsed adapter output
  reports/executive-summary.md ← rebuilt from stored normalized findings
```

The `raw/` artifacts come from the tool's actual subprocess output. The runner
does not copy or transform them — the tool binary writes them directly to the
path embedded in the command.

The report is always rebuilt from `normalized/findings.json`, not from raw
output. This keeps report generation stable as underlying tool formats change.

## Safety Boundaries

Safety constraints that apply to both modes:

- environments are limited to `local` and `staging`; production-like targets are
  rejected by config validation before any tool runs
- all tools operate in safe mode by default; safe mode cannot be disabled in
  a profile without causing an adapter error at execution time
- rule and template allowlists are enforced per-tool in the profile
- auth secrets are resolved only from environment variables; they never appear
  in YAML files or run artifacts
- one pentest plan executes at a time per invocation; no concurrency is
  introduced

Additional safety constraints in the live path:

- core tool binaries must be present on `PATH`; the toolkit does not download
  or install them
- the target must be reachable before adapters run; connection errors are
  surfaced as tool failures (exit 2)
- safe-mode adapter commands are conservative by design (ZAP baseline only,
  Nuclei template allowlist, Nmap `-F`/`--top-ports`)

## What Remains Planned

These items are planned but not yet implemented:

- **Scheduler integration**: No daemon, web UI, or CI-native runtime.
- **Notification sinks**: No webhook or alerting integration.
- **Kubernetes and SSO auth**: Not yet supported; only the five auth methods
  declared in `apps.yaml` are implemented.

## See Also

- `docs/how-to/run-live-pentest.md` — operator task guide
- `docs/reference/pentest-run.md` — authoritative run contract
- `docs/explanation/safety-model.md` — safety rationale
- `src/toolkit/pentest/execution.py` — execution service implementation
- `src/toolkit/pentest/contracts.py` — PentestToolRole and run contract types
