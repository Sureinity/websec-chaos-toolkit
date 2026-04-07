# Run A Live Chaos Experiment

Use this guide to run `toolkit chaos run` against a real Toxiproxy runtime and
a live target service.

## Before You Start

### Required: Toxiproxy server

A Toxiproxy server must be running and accessible. The default endpoint is
`http://127.0.0.1:8474`.

Install and start Toxiproxy:

```bash
# macOS
brew install toxiproxy
toxiproxy-server &

# Linux (download from https://github.com/Shopify/toxiproxy/releases)
./toxiproxy-server &
```

Verify the server is reachable:

```bash
curl http://127.0.0.1:8474/version
```

### Required: configured proxy

The target service must be fronted by a Toxiproxy proxy whose name matches
`target_service` in the chaos profile. The proxy must be enabled before the
experiment starts.

Create a proxy:

```bash
toxiproxy-cli create \
  --listen 127.0.0.1:19000 \
  --upstream 127.0.0.1:9000 \
  payments-api
```

### Required: live target

The target application must be running and reachable at the `base_url` in
`apps.yaml`. The `health_endpoint` must return HTTP 2xx during baseline.

### Required: toolkit dependencies

```bash
uv sync --extra dev
```

## Command

Run from the directory containing your config bundle:

```bash
uv run toolkit chaos run --app <app-id> --env <env> --profile <profile-name>
```

Example:

```bash
uv run toolkit chaos run \
  --app sample-internal-app \
  --env local \
  --profile dependency-latency-baseline
```

## What The Command Does

1. Validates app, environment, and chaos profile
2. Builds one deterministic experiment plan
3. Acquires a per-app lock (prevents concurrent experiments)
4. Preflights the Toxiproxy server and target proxy
5. Captures a live steady-state baseline via health polling
6. Injects exactly one reversible proxy fault via Toxiproxy
7. Monitors live health during the experiment window
8. Aborts on threshold breach
9. Always attempts rollback (removes toxic or re-enables proxy)
10. Persists artifacts and writes the Markdown summary

## Supported Fault Types

| Fault type | Toxiproxy operation | Status |
|---|---|---|
| `latency` | create `latency` toxic | supported |
| `bandwidth` | create `bandwidth` toxic | supported |
| `timeout` | create `timeout` toxic | supported |
| `connection_refused` | disable proxy | supported |
| `packet_loss` | — | fail-closed (no safe mapping) |

`controlled_restart` is schema-reserved but rejected at runtime.

## Exit Codes

- `0` — experiment passed, target stayed within thresholds
- `1` — abort threshold breached (resilience failure)
- `2` — config error, missing Toxiproxy, missing proxy, rollback failure, lock
  contention, or any runtime error

## Expected Outputs

After a run:

```
outputs/<run-id>/manifest.json
outputs/<run-id>/raw/chaos/baseline-observations.json
outputs/<run-id>/raw/chaos/experiment-observations.json
outputs/<run-id>/raw/chaos/orchestration-actions.json
outputs/<run-id>/normalized/findings.json
outputs/<run-id>/reports/executive-summary.md
```

Artifacts are written even on failure, so failed runs remain auditable.

## Safety Constraints

- Only `local` and `staging` environments are allowed
- Health monitoring is mandatory; no fault injection without a `health_endpoint`
- Rollback configuration is mandatory in the chaos profile
- One active experiment per app/environment on the operator host
- Rollback is always attempted, even on timeout or error
- The toolkit never installs or manages Toxiproxy; operators are responsible
  for the runtime

## Live Versus Fixture-Backed Runs

The fixture-backed flow (`run_chaos_fixture_flow`) is preserved for onboarding
and offline testing. It reads pre-recorded observations from repository fixture
files. No Toxiproxy or live target is needed.

The live flow (`run_chaos_live_flow`) connects to a real Toxiproxy runtime.
Both flows produce the same artifact layout and follow the same exit-code
contract.

## What Is Not Supported

- `packet_loss` faults (no safe Toxiproxy mapping)
- `controlled_restart` (schema-reserved, not implemented)
- Containerized or remote Toxiproxy runtime management
- Concurrent experiments on the same app/environment
- Production or production-like targets

## See Also

- `docs/reference/chaos-run.md` — authoritative run contract
- `docs/explanation/live-chaos-model.md` — how the live chaos path works
- `docs/explanation/safety-model.md` — safety rationale
