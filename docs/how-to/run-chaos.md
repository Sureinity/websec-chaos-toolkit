# Run Chaos

Use this guide to execute the current fixture-backed chaos flow from the
repository root.

## Before You Start

- install dependencies with `uv sync --extra dev`
- keep the repository fixture files in place under `tests/fixtures/chaos/`
- use the default example config pack in `examples/configs/sample-webapp/`, or
  another valid repository-style config bundle

## Command

```bash
cd examples/configs/sample-webapp
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
```

## What The Command Does

- validates the selected app, environment, and chaos profile
- resolves runtime auth for the selected app
- builds one deterministic chaos experiment plan
- acquires a per-app lock on the operator host
- loads fixture-backed baseline and experiment observations
- injects one fixture-backed proxy fault and always attempts rollback
- writes run artifacts under `outputs/<run-id>/`

## Expected Outputs

After a successful run, inspect:

- `outputs/<run-id>/manifest.json`
- `outputs/<run-id>/raw/chaos/baseline-observations.json`
- `outputs/<run-id>/raw/chaos/experiment-observations.json`
- `outputs/<run-id>/raw/chaos/orchestration-actions.json`
- `outputs/<run-id>/normalized/findings.json`
- `outputs/<run-id>/reports/executive-summary.md`

## Exit Codes

- `0`
  - the experiment stayed within configured thresholds
- `1`
  - the experiment triggered a resilience failure or abort-threshold breach
- `2`
  - configuration error, auth/runtime failure, or orchestration failure

## Current Limitations

- this command currently uses fixture-backed monitoring and fault-control data,
  not a live Toxiproxy environment
- `packet_loss` fails closed because the current Toxiproxy wrapper does not
  have a safe first-party mapping for it
- missing fixture files cause the run to fail with exit code `2`

See also:

- `docs/reference/chaos-run.md`
- `docs/reference/output-artifacts.md`
- `docs/explanation/safety-model.md`
- `examples/configs/sample-webapp/`
