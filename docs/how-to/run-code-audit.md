# Run A Code Audit

Use this guide when you want to analyze one local source tree with the
zero-config `toolkit code-audit` command.

## Before You Start

- install dependencies with `uv sync --extra dev`
- ensure the target path exists locally
- use a checked-out repository or source tree

The simplified code-audit path supports:

- `semgrep`
- `trivy`
- one local path per run

It does not support:

- live URLs
- running web targets
- image analysis in this command

For those cases, use:

- `toolkit audit <url>`
- the advanced profile-driven code and artifact workflow

## Check Readiness

Run:

```bash
uv run toolkit doctor --code-path .
```

Narrow readiness to one tool:

```bash
uv run toolkit doctor --code-path . --code-tool semgrep
uv run toolkit doctor --code-path . --code-tool trivy
```

## Run The Audit

Default dual-tool run:

```bash
uv run toolkit code-audit .
```

Semgrep only:

```bash
uv run toolkit code-audit . --tool semgrep
```

Trivy only:

```bash
uv run toolkit code-audit . --tool trivy
```

## What The Command Does

- validates the path as a source-tree target
- derives an ad hoc source-tree app id
- builds the built-in safe source-tree profile
- passes the selected path to:
  - `semgrep`
  - `trivy`
- writes outputs under `outputs/<run-id>/`

## Successful Output

On success, the command prints a summary similar to:

```text
Code audit completed.
Target path: /path/to/repo
Run: 20260416-120000-fedcba98
Status: findings
Findings: 4
Actionable findings: 2
Normalized bundle: /path/to/outputs/<run-id>/normalized/findings.json
Report: /path/to/outputs/<run-id>/reports/executive-summary.md
```

## Failure Behavior

The command exits with `2` when:

- the supplied path does not exist
- the supplied path is not a directory
- the selected tool is unsupported
- the selected tool is unavailable on the operator host
- Semgrep or Trivy fails at runtime

## When To Use The Advanced Workflow Instead

Use the profile-driven workflow when you need:

- reusable named profiles
- image analysis
- advanced artifact analysis
- explicit profile customization

See:

- `docs/how-to/run-code-and-artifact-checks.md`
- `docs/explanation/pentest-target-model.md`
- `docs/reference/pentest-run.md`
