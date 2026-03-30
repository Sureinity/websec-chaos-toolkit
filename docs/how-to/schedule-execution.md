# Schedule Execution

Use this guide when running the toolkit non-interactively from cron, a task
scheduler, or another external job runner.

## Scheduling Model

The toolkit does not run a daemon. Schedule the CLI commands directly from the
host that contains the config bundle and fixture assets.

Current implemented non-interactive commands:

- `uv run toolkit validate --app sample-internal-app --env local`
- `uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline`
- `uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline`
- `uv run toolkit report build --run-id <existing-run-id>`

## Preparation

- install dependencies with `uv sync --extra dev`
- keep the selected config bundle in the working directory
- keep fixture assets available when running the current pentest or chaos flows
  from a scheduled job
- export any required auth environment variables before launching the command

## Exit Codes

The scheduler should treat exit codes as the primary status signal:

- `0`
  - validation succeeded, no actionable pentest findings were produced, or the
    chaos experiment passed
- `1`
  - the pentest run produced medium/high findings or the chaos run detected a
    resilience failure
- `2`
  - configuration, auth, fixture, or orchestration failure

## Example Cron-Style Commands

Validation:

```bash
cd /path/to/config-bundle
UV_CACHE_DIR=/tmp/uv-cache uv run toolkit validate --app sample-internal-app --env local
```

Fixture-backed pentest:

```bash
cd /path/to/config-bundle
UV_CACHE_DIR=/tmp/uv-cache uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline
```

Fixture-backed chaos:

```bash
cd /path/to/config-bundle
UV_CACHE_DIR=/tmp/uv-cache uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
```

Report rebuild:

```bash
cd /path/to/config-bundle
UV_CACHE_DIR=/tmp/uv-cache uv run toolkit report build --run-id <existing-run-id>
```

## Current Limits

- the current pentest and chaos commands are implemented now, but remain
  fixture-backed
- external-binary verification remains opt-in
- live scanner execution and live Toxiproxy-backed chaos execution are planned
  later

Supporting references:

- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
- `docs/explanation/operator-docs-contract.md`
- `docs/explanation/safety-model.md`
- `examples/configs/sample-webapp/`
