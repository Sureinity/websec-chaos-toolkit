# Run A URL-First Audit

Use this guide when you want to audit one reachable web target without
preparing repository YAML config files.

## Before You Start

- install dependencies with `uv sync --extra dev`
- ensure the target URL is reachable from the machine running the toolkit
- prefer Docker for the simplest runtime path

The simplified audit path currently supports:

- remote web targets
- unauthenticated access by default
- one ad hoc URL at a time

Milestone 16 extends this path with authenticated and discovery-driven audit.
The locked contract for that work is:

- authentication is optional overall
- if no auth mode is selected, audit remains unauthenticated
- at most one auth mode may be selected per run
- mode-specific flags become required when that mode is selected
- `api_login` is the primary automated auth path for apps with JSON-based
  login logic
- `form` remains a secondary compatibility path for classic HTML login forms
- explicit auth modes fail closed and never silently downgrade
- unauthenticated audit still works even if the target login route is disabled
- the CLI now validates these auth inputs explicitly before a run starts

## Check Runtime Readiness

Run:

```bash
uv run toolkit doctor
```

Expected behavior:

- `container` is recommended when Docker is available
- `host` is usable when `zap-baseline.py`, `nuclei`, and `nmap` are present on
  `PATH`
- edge-chaos readiness is reported separately by `toolkit doctor`

## Run The Audit

Auto-select the runtime:

```bash
uv run toolkit audit http://127.0.0.1:8000
```

Force host execution:

```bash
uv run toolkit audit https://target.internal --runtime host
```

Force container execution:

```bash
uv run toolkit audit https://target.internal --runtime container
```

Increase runtime log verbosity when needed:

```bash
uv run toolkit audit -v https://target.internal
uv run toolkit audit -vv https://target.internal
uv run toolkit audit -vvv https://target.internal
```

## What The Command Does

- validates the supplied URL through the ad hoc target builder
- derives an internal app id, allowlist, and health endpoint from that URL
- captures an `httpx` preflight fingerprint before deeper scanner execution
- discovers same-origin routes with `katana`
- feeds a curated discovered-route subset into ZAP
- feeds a larger but filtered same-origin route set into Nuclei
- keeps Nmap limited to conservative host and service context
- captures an `httpx` preflight fingerprint before deeper scanner execution
- builds the built-in safe remote-web profile
- runs ZAP, Nuclei, and Nmap through the selected runtime backend
- emits structured runtime logs while scanners are running
- writes outputs under `outputs/<run-id>/`

## Successful Output

On success or findings, the command prints a summary similar to:

```text
Audit completed.
Target: http://127.0.0.1:8000/
Run: 20260414-010101-abcdef12
Status: findings
Runtime: container
Findings: 3
Actionable findings: 1
Normalized bundle: /path/to/outputs/<run-id>/normalized/findings.json
Report: /path/to/outputs/<run-id>/reports/executive-summary.md
```

If a core scanner fails at runtime, the command prints `Audit failed.`, keeps
the run summary, and reports the failed tool details on stderr before exiting
with `2`. Structured runtime logs that were already emitted stay visible in
the terminal.

This failed state can still be partially useful:

- findings from tools that completed successfully are still preserved
- the normalized bundle path is still printed when findings were written
- the Markdown report path is still printed when report generation completed
- the failed status means at least one core audit stage did not complete
  successfully, not that every artifact is unusable

The runtime logs are now organized as timestamped records, for example:

```text
2026-04-21T13:45:10+08:00 INFO event=tool.start runtime=container tool=zap output=/path/to/results.json timeout_seconds=600.0
2026-04-21T13:45:12+08:00 INFO event=tool.output runtime=container tool=zap stream=stdout message="passive scan started"
2026-04-21T13:45:20+08:00 INFO event=tool.finish runtime=container tool=zap status=success exit_code=0 duration_ms=9876
```

For ZAP specifically, a non-zero wrapper exit can still be accepted when the
JSON artifact was produced. In that case the finish record is reported as
`status=completed_with_findings` instead of `status=failed`.

Verbosity levels:

- default: tool start and finish records, plus warnings and errors
- `-v`: include stderr tool output
- `-vv`: include stdout and stderr tool output
- `-vvv`: include command-level context such as command and working directory

## Failure Behavior

The command exits with `2` when:

- the supplied value is not a valid HTTP or HTTPS URL
- no audit runtime is ready
- the selected runtime is explicitly requested but unavailable
- the live pentest execution fails at runtime

In practice, a true audit failure means one of these happened:

- a required runtime or core scanner could not run
- a core scanner timed out or exited without a usable artifact
- a required auth or discovery stage failed before scanner execution

That is different from a useful partial run, where:

- one core scanner failed
- one or more other scanners still completed
- preserved findings remain available in the normalized bundle and report

Common remediation steps:

- install Docker and rerun `uv run toolkit doctor`
- or install `zap-baseline.py`, `nuclei`, and `nmap` on `PATH`
- confirm the target URL is reachable from the operator host

## When To Use The Managed Workflow Instead

Use the YAML-driven path when you need:

- repeatable named app definitions
- full config-driven auth setup outside the URL-first path
- multiple reusable pentest profiles
- live chaos execution

Managed workflow entrypoints:

- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`

## See Also

- `docs/tutorials/quickstart-url-first.md`
- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
- `docs/how-to/run-pentest.md`
