# CLI Reference

The bootstrap scaffold exposes the intended public command tree:

```text
toolkit validate --app <id> --env <env>
toolkit pentest run --app <id> --env <env> --profile <name>
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

Current command behavior:

- `toolkit validate` loads the repository YAML files from the current working
  directory, validates the selected `--app/--env` pair, and exits with `0` on
  success
- `toolkit pentest run` executes real scanner adapters (zap, nuclei, nmap)
  against a live target, writes run artifacts under `outputs/<run-id>/`, and
  exits with `0`, `1`, or `2` according to the pentest outcome contract;
  requires `zap-baseline.py`, `nuclei`, and `nmap` binaries on `PATH`
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

For task-oriented operator procedures, see:

- `docs/how-to/run-validation.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-chaos.md`
- `docs/how-to/run-live-chaos.md`
- `docs/how-to/schedule-execution.md`
