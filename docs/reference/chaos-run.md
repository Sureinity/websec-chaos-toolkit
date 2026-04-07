# Chaos Run Reference

This document is the authoritative contract for `toolkit chaos run`. It covers
both the current fixture-backed flow and the live execution flow. Both flows
must satisfy every contract defined here.

## Live Execution Contract

### Run Lifecycle

A live chaos run performs these steps in order:

1. load and validate the requested app, environment, and chaos profile
2. build one deterministic chaos experiment plan
3. acquire a per-app lock on the operator host
4. preflight the Toxiproxy runtime and target proxy
5. capture a live steady-state baseline from health and optional metrics
6. inject exactly one reversible proxy fault via Toxiproxy
7. monitor live observations during the experiment window
8. abort on threshold breach
9. always attempt rollback
10. persist artifacts and rebuild the Markdown summary

### Safety Invariants

These invariants hold for both execution modes:

- **No fault injection without health monitoring and rollback config.**
  The planner rejects missing `health_endpoint` and missing `rollback`
  before any experiment starts.
- **One active experiment per app at a time.** A filesystem lock under
  `.toolkit-locks/chaos/` prevents concurrent experiments on the same
  app/environment from the same operator host.
- **Rollback always attempted.** The runner finally block attempts rollback
  on success, abort, timeout, and general error paths. A failed rollback
  escalates to exit code `2`.
- **`controlled_restart` remains rejected.** The fault type is schema-reserved
  but raises `ValueError` until a dedicated safe implementation exists.
- **`packet_loss` stays fail-closed.** The Toxiproxy HTTP API does not expose
  a first-party packet-loss toxic. `build_toxiproxy_fault_request()` raises
  `UnsupportedToxiproxyFaultError` until a safe live mapping exists.

## Supported Fault Contract

The v1 runner contract supports exactly these reversible proxy-style faults:

| Fault type | Toxiproxy operation | Live status |
|---|---|---|
| `latency` | create `latency` toxic (latency_ms, jitter_ms) | supported |
| `bandwidth` | create `bandwidth` toxic (rate_kbps) | supported |
| `timeout` | create `timeout` toxic (timeout_ms) | supported |
| `connection_refused` | disable proxy; re-enable on rollback | supported |
| `packet_loss` | no HTTP API mapping | fail-closed |

`controlled_restart` is schema-reserved but rejected at runtime.

Exactly one fault may be active at a time.

## Exit-Code Contract

`toolkit chaos run` uses the shared exit-code contract:

- `0` — experiment completed and target stayed within thresholds
- `1` — abort-threshold breach or resilience failure
- `2` — config error, missing Toxiproxy runtime, missing proxy, monitoring
  failure, rollback failure, lock contention, or other runtime error

## Monitoring Contract

The monitoring layer combines mandatory health checks with optional metrics:

- every observation records a health result and timestamp
- metrics are optional; when configured they must parse deterministically
  into an error-rate value
- steady-state baseline capture requires all observations to be healthy
- abort evaluation records structured evidence for:
  - consecutive health-check failures
  - `max_error_rate` threshold breaches

Health-only mode and health-plus-metrics mode both remain valid paths.

## Planner Contract

The planner returns one deterministic experiment plan containing:

- app id, environment, profile name
- target service
- one supported fault type
- baseline and experiment durations
- health endpoint
- rollback method
- abort-threshold values (consecutive failures, optional max error rate)

## Preconditions

The chaos runner refuses to start when:

- the selected app does not provide `health_endpoint`
- the selected chaos profile does not provide rollback configuration
- the requested fault type is unsupported or explicitly reserved

## Artifact Expectations

Every chaos run writes or preserves:

```
outputs/<run-id>/manifest.json
outputs/<run-id>/raw/chaos/baseline-observations.json
outputs/<run-id>/raw/chaos/experiment-observations.json
outputs/<run-id>/raw/chaos/orchestration-actions.json
outputs/<run-id>/normalized/findings.json
outputs/<run-id>/reports/executive-summary.md
```

The normalized bundle preserves experiment outcome evidence, not just raw
proxy or monitoring logs.

## Fixture-Versus-Live Boundary

### Fixture-backed flow (onboarding and offline testing)

- reads pre-recorded observation files from repository fixtures
- uses a non-networked `FixtureToxiproxyController`
- no Toxiproxy runtime or live target required
- entry point: `run_chaos_fixture_flow()` in `src/toolkit/chaos/runner.py`

### Live execution flow

- connects to a real Toxiproxy API server
- captures live health/metrics observations via HTTP
- injects real faults through the Toxiproxy HTTP API
- requires a running Toxiproxy server and a live target behind a proxy
- entry point: `run_chaos_live_flow()` in `src/toolkit/chaos/runner.py`

A contributor reading the code can identify which path is active by the
runner function name:

| Function | Mode |
|----------|------|
| `run_chaos_fixture_flow` | fixture-backed |
| `run_chaos_live_flow` | live execution |

## Locking And Rollback Guarantees

The runner contract requires:

- one active experiment per app/environment on the operator host
- a repo-local filesystem lock under `.toolkit-locks/chaos/`
- threshold-driven abort handling during the experiment window
- rollback attempts on success, abort, timeout, and general error paths

## Current State

- live chaos execution service, monitoring, and runner are implemented
- live Toxiproxy client wrapper with preflight, inject, and rollback is
  implemented
- live monitoring layer (health + metrics HTTP polling) is implemented
- **the current command executes live Toxiproxy-backed experiments**
- fixture-backed flow is preserved as `run_chaos_fixture_flow()` for
  onboarding and offline testing

## Current Command Usage

Run against a live Toxiproxy runtime:

```bash
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
```

Prerequisites: Toxiproxy server at `http://127.0.0.1:8474`, target proxy
configured, and live target reachable at `base_url`.

Safety rationale:

- `docs/explanation/safety-model.md`
- `docs/explanation/live-chaos-model.md`
