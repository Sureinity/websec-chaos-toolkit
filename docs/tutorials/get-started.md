# Get Started With Managed Config

This tutorial walks contributors through the managed, YAML-driven toolkit
workflow.

If you want the shortest path first, start with
`docs/tutorials/quickstart-url-first.md`. This tutorial is the follow-up path
for repeatable named targets, profile-driven runs, and the broader operator
workflow.

## Two Operator Paths

The toolkit supports two workflows:

1. **Compose-based (preferred for operators)**: run the toolkit, the
   target app, and the optional Toxiproxy service together via Docker
   Compose. No scanner binaries are required on the host. Start here:
   `docs/how-to/run-with-compose.md`.
2. **Direct CLI (for development)**: run the toolkit on the host with
   `uv run toolkit ...`. This path is useful for inspecting the toolkit
   source and iterating on adapter behavior.

This tutorial walks through the config-driven direct CLI path. Operators
running the toolkit in CI or on shared infrastructure should prefer the
Compose path.

## Goal

Create a local Python environment with `uv`, install the project dependencies,
and run the config-driven validation, pentest, chaos, and report flows.

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
normalized findings. `toolkit pentest run` and `toolkit chaos run` execute
against live targets by default. Fixture-backed flows are preserved for
onboarding and offline testing.

Status guide:

- URL-first now:
  - `toolkit audit <url>` for zero-config remote web auditing
  - `toolkit doctor` for simplified runtime readiness checks
- Live execution now:
  - pentest runs execute real scanner binaries (`--runtime host` or `--runtime container`)
  - chaos runs execute live Toxiproxy-backed experiments
- Fixture-backed flows preserved for onboarding and offline testing
- Config-driven commands implemented: validate, pentest run, chaos run, report build

Next reading:

- `docs/tutorials/quickstart-url-first.md` — shortest onboarding path
- `docs/how-to/run-url-audit.md` — zero-config audit procedure
- `docs/how-to/run-with-compose.md` — Compose-based operator workflow
- `docs/explanation/compose-workflow-model.md` — service topology rationale
- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/schedule-execution.md`
- `docs/reference/cli.md`
- `docs/reference/output-artifacts.md`
- `docs/explanation/safety-model.md`
