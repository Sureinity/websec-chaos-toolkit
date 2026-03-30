# Get Started

This tutorial is for contributors who want to inspect the implemented
fixture-backed workflows locally.

## Goal

Create a local Python environment with `uv`, install the project dependencies,
and run the example-driven validation, pentest, chaos, and report flows.

## Example Pack

Use the default sanitized sample web app config pack:

```bash
cd examples/configs/sample-webapp
```

This tutorial keeps all commands inside that directory so the YAML bundle is in
the current working directory.

Alternative pack:

- `examples/configs/sample-api/`
  - use this when you want the authenticated API-oriented variant after
    finishing the default walkthrough

## Steps

1. Run `uv sync --extra dev`.
2. Run `uv run toolkit --help` and inspect the bootstrap command layout.
3. Change into `examples/configs/sample-webapp`.
4. Run `uv run toolkit validate --app sample-internal-app --env local`.
5. Run `uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline`.
6. Copy the `Run:` value from the pentest output and run `uv run toolkit report build --run-id <that-run-id>`.
7. Run `uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline`.
8. Run `uv run pytest` to verify the minimal scaffold checks.

`toolkit report build` is implemented and rebuilds summaries from stored
normalized findings. `toolkit pentest run` and `toolkit chaos run` are
implemented for the current fixture-backed flows.

Status guide:

- Implemented now:
  - validate, pentest run, chaos run, report build
- Fixture-backed now:
  - pentest and chaos flows
- Planned later:
  - live scanner execution and live Toxiproxy-backed chaos execution

Next reading:

- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/schedule-execution.md`
- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
- `docs/explanation/safety-model.md`
