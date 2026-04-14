# Run URL-First Edge Chaos

Use this guide when you want the toolkit to manage a local edge-chaos proxy for
one reachable web URL.

## Before You Start

- install dependencies with `uv sync --extra dev`
- Docker available on `PATH`
- one reachable web target

This command is intended for ad hoc edge testing. It does not replace the
advanced managed chaos workflow when you need named targets, reusable profiles,
or existing Toxiproxy topology.

## Check Readiness

Run:

```bash
uv run toolkit doctor
```

Expected behavior:

- `Audit runtime (container)` or `host` should describe audit readiness
- `Edge chaos` should report `ready` when Docker is available

## Run The Command

Default fault:

```bash
uv run toolkit edge-chaos http://127.0.0.1:8000
```

Choose a different fault:

```bash
uv run toolkit edge-chaos http://127.0.0.1:8000 --fault timeout
```

Supported faults:

- `latency`
- `bandwidth`
- `timeout`
- `connection_refused`

## What The Command Does

- derives an ad hoc chaos target from the supplied URL
- starts a managed Toxiproxy container on the operator host
- creates one local proxy that forwards to the requested upstream
- captures a baseline through the proxy using `GET /`
- injects one reversible fault
- monitors the target through the proxy during the experiment window
- rolls back the fault, removes the proxy, and stops the managed container

## Exit Codes

- `0` — the experiment completed and stayed within thresholds
- `1` — the experiment breached resilience thresholds
- `2` — invalid URL, Docker/runtime failure, startup failure, or cleanup failure

## When To Use The Managed YAML Workflow Instead

Use the existing managed workflow when you need:

- pre-existing Toxiproxy topology
- named app definitions and reusable profiles
- metrics-driven thresholds
- more explicit operator control over the runtime

See:

- `docs/how-to/run-chaos.md`
- `docs/how-to/run-live-chaos.md`
- `docs/reference/chaos-run.md`
