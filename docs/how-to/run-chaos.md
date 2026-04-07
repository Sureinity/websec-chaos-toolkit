# Run Chaos

This guide covers both ways to run `toolkit chaos run`:

- **Live execution** (default): real Toxiproxy runtime against a live target
- **Fixture-backed**: pre-recorded observations for onboarding and offline testing

## Live Execution

See [run-live-chaos.md](run-live-chaos.md) for full prerequisites including
Toxiproxy setup, proxy configuration, and supported fault types.

### Quick start

```bash
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
```

Requires: Toxiproxy server at `http://127.0.0.1:8474`, configured proxy, and
live target reachable at `base_url`.

### What it does

- validates app, environment, and chaos profile
- acquires per-app lock, preflights Toxiproxy
- captures live baseline, injects one fault
- monitors experiment window, aborts on threshold breach
- always attempts rollback
- writes artifacts under `outputs/<run-id>/`

### Exit codes

- `0` — experiment passed, resilience held
- `1` — abort threshold breached (resilience failure)
- `2` — config error, missing runtime, rollback failure, or other error

## Fixture-Backed Execution (Onboarding And Offline Testing)

The fixture-backed flow reads pre-recorded observations from repository
fixture files. No Toxiproxy server or live target is required.

> **Note**: The fixture-backed runner (`run_chaos_fixture_flow`) is available
> in `src/toolkit/chaos/runner.py` for integration tests and onboarding use.
> The default CLI command uses the live path. To use the fixture flow in
> tests, call `run_chaos_fixture_flow` directly with fixture paths.

## Expected Outputs

Both modes write the same artifact layout:

```
outputs/<run-id>/manifest.json
outputs/<run-id>/raw/chaos/baseline-observations.json
outputs/<run-id>/raw/chaos/experiment-observations.json
outputs/<run-id>/raw/chaos/orchestration-actions.json
outputs/<run-id>/normalized/findings.json
outputs/<run-id>/reports/executive-summary.md
```

## See Also

- `docs/how-to/run-live-chaos.md` — live execution prerequisites
- `docs/reference/chaos-run.md` — authoritative run contract
- `docs/explanation/live-chaos-model.md` — how the live path works
- `docs/explanation/safety-model.md` — safety rationale
- `examples/configs/sample-webapp/` — sample config pack
