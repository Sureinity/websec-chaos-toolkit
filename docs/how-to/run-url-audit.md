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

## What The Command Does

- validates the supplied URL through the ad hoc target builder
- derives an internal app id, allowlist, and health endpoint from that URL
- captures an `httpx` preflight fingerprint before deeper scanner execution
- discovers same-origin routes with `katana`
- feeds the seed URL plus discovered routes into ZAP and Nuclei
- keeps Nmap limited to conservative host and service context
- captures an `httpx` preflight fingerprint before deeper scanner execution
- builds the built-in safe remote-web profile
- runs ZAP, Nuclei, and Nmap through the selected runtime backend
- streams live tool stdout and stderr while scanners are running
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
with `2`. Live tool output that was already emitted stays visible in the
terminal.

## Failure Behavior

The command exits with `2` when:

- the supplied value is not a valid HTTP or HTTPS URL
- no audit runtime is ready
- the selected runtime is explicitly requested but unavailable
- the live pentest execution fails at runtime

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
