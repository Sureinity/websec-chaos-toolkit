# Quickstart With A Source Tree

This tutorial is the fastest way to use the toolkit for local code and config
analysis. It walks through running `toolkit code-audit` against one local path
without creating `apps.yaml`, `pentest-profiles.yaml`, or `chaos-profiles.yaml`.

## Goal

Install the project with `uv`, check code-audit readiness, and run a source
tree audit against one local path.

## Before You Start

- repository checked out locally
- dependencies installed with `uv`
- one local source tree to scan

The current code-audit path is:

- source-tree only
- one filesystem path per run
- Semgrep and Trivy by default
- host runtime first, then container when Docker is available

Use the profile-driven workflow when you need image or artifact analysis beyond
the simple source-tree path.

## Steps

1. Install dependencies:

```bash
uv sync --extra dev
```

2. Inspect the command tree:

```bash
uv run toolkit --help
```

3. Check code-audit readiness:

```bash
uv run toolkit doctor --code-path .
```

4. Run the default code audit:

```bash
uv run toolkit code-audit .
```

5. Narrow to one tool when needed:

```bash
uv run toolkit code-audit . --tool semgrep
uv run toolkit code-audit . --tool trivy
```

6. Force container execution when you want portability:

```bash
uv run toolkit code-audit . --tool trivy --runtime container
```

## What The Command Does

- validates the supplied path as a source tree
- derives an ad hoc source-tree target
- builds the built-in safe source-tree profile
- runs:
  - `semgrep`
  - `trivy`
- writes raw artifacts, normalized findings, and a Markdown summary

## Exit Codes

- `0` — no actionable findings
- `1` — one or more actionable findings
- `2` — invalid path, unsupported tool, unavailable tool, or runtime failure

## Next Reading

- `docs/how-to/run-code-audit.md`
- `docs/how-to/run-code-and-artifact-checks.md`
- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
