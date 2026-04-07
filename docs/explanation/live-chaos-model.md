# Live Chaos Execution Model

This document explains how the live chaos execution path works, what
distinguishes it from the fixture-backed path, what is still planned, and
where the safety boundaries are enforced.

## Two Execution Modes

The toolkit supports two chaos execution modes. Both satisfy the same
contract: same artifact layout, same exit-code semantics, same normalized
result schema.

### Fixture-backed mode

- reads pre-recorded observation files from repository fixtures
- uses a non-networked `FixtureToxiproxyController`
- no Toxiproxy server or live target required
- entry point: `run_chaos_fixture_flow()` in `src/toolkit/chaos/runner.py`

### Live execution mode

- connects to a real Toxiproxy API server
- captures live health/metrics observations via HTTP polling
- injects real faults through the Toxiproxy HTTP API
- requires a running Toxiproxy server and a live target behind a proxy
- entry point: `run_chaos_live_flow()` in `src/toolkit/chaos/runner.py`

`toolkit chaos run` uses the live execution mode.

## Live Execution Lifecycle

```
CLI invocation
  |
  v
validate app / environment / chaos profile
  |
  v
build deterministic experiment plan (one fault, one target service)
  |
  v
acquire per-app filesystem lock
  |
  v
preflight Toxiproxy server and target proxy
  - missing server -> exit 2
  - missing or disabled proxy -> exit 2
  |
  v
capture live steady-state baseline (poll health at intervals)
  - any unhealthy observation -> BaselineCaptureError -> exit 2
  |
  v
inject one reversible proxy fault via ChaosExecutionService
  |
  v
monitor live experiment window (poll health at intervals)
  |
  v
evaluate abort thresholds
  - consecutive health failures >= threshold -> abort
  - error_rate > max_error_rate -> abort
  |
  v
always attempt rollback (remove toxic or re-enable proxy)
  - rollback failure escalates to exit 2
  |
  v
release per-app lock
  |
  v
persist: baseline observations, experiment observations,
         orchestration actions, normalized findings,
         manifest, executive summary
  |
  v
return ChaosRunSummary with stable exit code (0, 1, or 2)
```

## Execution Service

The live path delegates fault injection and rollback to
`src/toolkit/chaos/execution.py` (`ChaosExecutionService`). This service:

- wraps `ToxiproxyClient` from `src/toolkit/chaos/toxiproxy.py`
- provides `preflight()` to check server reachability and proxy state
- provides `inject_fault()` and `rollback_fault()` with operation logging
- satisfies the `ChaosFaultController` protocol so the runner can use it
  interchangeably with `FixtureToxiproxyController`

## Live Monitoring

The monitoring module (`src/toolkit/chaos/monitoring.py`) provides:

- `capture_live_baseline()` — polls health at regular intervals and aggregates
  into a `SteadyStateBaseline`
- `collect_live_experiment_observations()` — polls health during the experiment
  and returns a tuple of `MonitoringObservation` objects
- `evaluate_abort_thresholds()` — evaluates observations against configured
  thresholds (works identically with fixture-loaded and live-sampled data)

Health-only mode is valid. Metrics are optional.

## Safety Boundaries

Safety constraints that apply to both modes:

- environments limited to `local` and `staging`
- health monitoring is mandatory; no fault injection without `health_endpoint`
- rollback is mandatory; chaos profiles require rollback configuration
- one active experiment per app/environment (filesystem lock)
- rollback always attempted in the finally block (success, abort, timeout, error)
- `controlled_restart` rejected at runtime
- `packet_loss` fail-closed (no safe Toxiproxy mapping)

Additional constraints in live mode:

- Toxiproxy server must be running and reachable before any fault injection
- target proxy must exist and be enabled before the experiment
- the toolkit never downloads, installs, or manages Toxiproxy

## Fault-Type Mapping

| Chaos fault | Toxiproxy API | Rollback |
|---|---|---|
| latency | POST toxic (type=latency) | DELETE toxic |
| bandwidth | POST toxic (type=bandwidth) | DELETE toxic |
| timeout | POST toxic (type=timeout) | DELETE toxic |
| connection_refused | POST proxy (enabled=false) | POST proxy (enabled=true) |
| packet_loss | rejected (UnsupportedToxiproxyFaultError) | n/a |

## What Remains Planned

- **Containerized runtime**: The toolkit does not manage Toxiproxy containers.
  Operators must ensure the server is running. Container lifecycle management
  is planned as a future convenience layer.
- **packet_loss support**: Requires a safe, reliable mapping to a Toxiproxy
  toxic or an alternative proxy runtime.
- **controlled_restart**: Requires a dedicated safe implementation beyond
  proxy-based faults.
- **Multi-fault experiments**: The contract locks one fault at a time. Future
  iterations may support sequential multi-fault plans.

## See Also

- `docs/how-to/run-live-chaos.md` — operator task guide
- `docs/reference/chaos-run.md` — authoritative run contract
- `docs/explanation/safety-model.md` — safety rationale
- `src/toolkit/chaos/execution.py` — execution service implementation
- `src/toolkit/chaos/contracts.py` — run contract and safety invariants
