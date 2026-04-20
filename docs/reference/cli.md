# CLI Reference

The bootstrap scaffold exposes the implemented public command tree:

```text
toolkit audit <url> [--runtime host|container] [--auth-mode <mode>] [mode-specific auth flags]
toolkit edge-chaos <url> [--fault <name>]
toolkit code-audit <path> [--tool semgrep|trivy] [--runtime host|container]
toolkit validate --app <id> --env <env>
toolkit doctor
toolkit pentest run --app <id> --env <env> --profile <name> [--runtime host|container]
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

Current command behavior:

- `toolkit audit` derives an ad hoc target from the supplied URL, selects an
  available audit runtime (`container` preferred, `host` fallback), accepts
  optional auth-mode flags, validates one auth mode per run fail-closed,
  captures an `httpx` preflight fingerprint, executes a safe remote-web audit,
  writes run artifacts under
  `outputs/<run-id>/`, and exits with `0`, `1`, or `2`
- `toolkit edge-chaos` derives an ad hoc chaos target from the supplied URL,
  starts a managed local Toxiproxy container, creates a local proxy, probes
  the requested URL path through that proxy, runs one reversible edge-chaos
  experiment, reports runtime, fault, rollback, and recovery summary fields,
  writes run artifacts under `outputs/<run-id>/`, and exits with `0`, `1`,
  or `2`
- `toolkit code-audit` derives an ad hoc source-tree target from the supplied
  path, runs Semgrep and/or Trivy with the built-in `source_tree` profile, and
  selects runtime as follows:
  - `--runtime host`
  - `--runtime container`
  - host first, then container, when omitted
  It writes run artifacts under `outputs/<run-id>/`, and exits with `0`, `1`,
  or `2`
- `toolkit validate` loads the repository YAML files from the current working
  directory, validates the selected `--app/--env` pair, and exits with `0` on
  success
- `toolkit doctor` reports audit runtime readiness and the current simplified
  edge-chaos readiness status
- `toolkit pentest run` executes real scanner adapters (zap, nuclei, nmap)
  against a live target, writes run artifacts under `outputs/<run-id>/`, and
  exits with `0`, `1`, or `2` according to the pentest outcome contract;
  `--runtime host` (default) requires scanner binaries on `PATH`;
  `--runtime container` runs scanners in Docker containers instead
- `toolkit report build` reads `outputs/<run-id>/normalized/findings.json`,
  writes `outputs/<run-id>/reports/executive-summary.md`, and exits with `0` on
  success
- `toolkit chaos run` executes a live Toxiproxy-backed chaos experiment,
  writes run artifacts under `outputs/<run-id>/`, and exits with `0`, `1`,
  or `2` according to the chaos outcome contract; requires a running
  Toxiproxy server and a configured proxy for the target service

Stable exit-code contract:

- `0`: no findings or a passing experiment
- `1`: medium or high findings, or a resilience failure
- `2`: configuration or runtime errors

## Compose Operator Workflow

The preferred Docker-first operator path runs the toolkit as a service
inside `docker-compose.yml` alongside an example target app and an
optional Toxiproxy service:

```bash
docker compose up -d toolkit-runner sample-app
docker compose exec toolkit-runner toolkit pentest run \
  --app sample-internal-app --env local --profile safe-web-baseline \
  --runtime container
```

For chaos workflows, add the Toxiproxy profile:

```bash
docker compose --profile chaos up -d toolkit-runner sample-app toxiproxy
```

See `docs/how-to/run-with-compose.md` for the full workflow.

For task-oriented operator procedures, see:

- `docs/how-to/run-code-audit.md`
- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/run-live-pentest.md`
- `docs/how-to/run-live-chaos.md`
- `docs/how-to/run-pentest-with-docker.md`
- `docs/how-to/run-with-compose.md`
- `docs/how-to/schedule-execution.md`
