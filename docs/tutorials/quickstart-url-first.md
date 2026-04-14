# Quickstart With A URL

This tutorial is the fastest way to use the toolkit. It walks through running
an audit against one reachable web URL without creating `apps.yaml`,
`pentest-profiles.yaml`, or `chaos-profiles.yaml`.

## Goal

Install the project with `uv`, check runtime readiness, and run a safe
remote-web audit from a single URL.

## Before You Start

- repository checked out locally
- dependencies installed with `uv`
- one reachable web target
- Docker recommended for the simplest runtime path

The current URL-first path is:

- remote-web only
- unauthenticated only
- audit only

Use the managed YAML workflow when you need repeatable target definitions,
authentication setup, or live chaos experiments.

## Steps

1. Install dependencies:

```bash
uv sync --extra dev
```

2. Inspect the current command tree:

```bash
uv run toolkit --help
```

3. Check runtime readiness:

```bash
uv run toolkit doctor
```

4. Run a URL-first audit:

```bash
uv run toolkit audit http://127.0.0.1:8000
```

5. Inspect the summary output:

- `Run:` identifies the output directory under `outputs/<run-id>/`
- `Runtime:` shows whether the toolkit used `container` or `host`
- `Report:` points to the generated Markdown summary

## What The Command Does

- derives an ad hoc target from the supplied URL
- builds a built-in safe remote-web profile
- prefers Docker container execution when available
- falls back to host execution when the required binaries are installed
- writes raw artifacts, normalized findings, and a Markdown summary

## Exit Codes

- `0` — no actionable findings
- `1` — one or more actionable findings
- `2` — invalid URL, no ready runtime, or execution failure

## Next Reading

- `docs/how-to/run-url-audit.md`
- `docs/how-to/run-with-compose.md`
- `docs/tutorials/get-started.md`
- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
