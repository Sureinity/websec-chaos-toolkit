# Chaos Run Reference

This document describes the current fixture-backed behavior of
`toolkit chaos run` and the contract later chaos iterations must preserve.

Current implementation status:

- the fixture-backed chaos runner is implemented
- the current command writes raw artifacts, normalized findings, a manifest,
  and a Markdown summary
- the current command uses fixture-backed monitoring observations and
  Toxiproxy-like control instead of a live external Toxiproxy process

## Run Lifecycle

A chaos run must perform these steps in order:

1. load and validate the requested app, environment, and chaos profile
2. build one deterministic chaos experiment plan
3. acquire a per-app lock on the operator host
4. capture a steady-state baseline from app health monitoring
5. inject exactly one reversible proxy fault
6. observe the experiment window using health checks and optional metrics
7. abort on threshold breach
8. always attempt rollback
9. persist artifacts and rebuild the Markdown summary

## Supported Fault Contract

The v1 runner contract supports exactly these reversible proxy-style faults:

- `latency`
- `bandwidth`
- `packet_loss`
- `timeout`
- `connection_refused`

`controlled_restart` remains schema-reserved but must be rejected until a
dedicated implementation exists.

Exactly one fault may be active at a time.

## Toxiproxy Wrapper Contract

The current wrapper layer translates runner-facing chaos faults into official
Toxiproxy API operations:

- `latency`
  - create a `latency` toxic with `latency_ms` and optional `jitter_ms`
- `bandwidth`
  - create a `bandwidth` toxic with `rate_kbps`
- `timeout`
  - create a `timeout` toxic with `timeout_ms`
- `connection_refused`
  - disable the proxy and re-enable it during rollback

`packet_loss` currently fails closed in the wrapper because the official
Toxiproxy HTTP API does not expose a first-party packet-loss toxic. The runner
must surface that as a runtime failure until a safe supported mapping exists.

## Monitoring Contract

The monitoring layer combines mandatory health checks with optional metrics
sampling:

- every observation records a health result and timestamp
- metrics are optional, but when configured they must parse deterministically
  into an error-rate value
- steady-state baseline capture requires only healthy observations
- abort evaluation records structured evidence for:
  - consecutive health-check failures
  - `max_error_rate` threshold breaches

Health-only mode and health-plus-metrics mode both remain valid v1 paths.

## Planner Contract

The planner must return one deterministic experiment plan containing:

- app id
- environment
- profile name
- target service
- one supported fault type
- baseline duration
- experiment duration
- health endpoint
- rollback method
- abort-threshold values

## Preconditions

The chaos runner must refuse to start when these requirements are not met:

- the selected app does not provide `health_endpoint`
- the selected chaos profile does not provide rollback configuration
- the requested fault type is unsupported or explicitly reserved

Health monitoring is mandatory. Metrics remain optional.

## Exit-Code Contract

`toolkit chaos run` uses the shared exit-code contract:

- `0`
  - the experiment completed and the target stayed within thresholds
- `1`
  - the experiment triggered a resilience failure or abort-threshold breach
- `2`
  - configuration error, monitoring/runtime failure, timeout handling failure,
    or rollback/orchestration failure

## Artifact Expectations

The current chaos run path writes or preserves:

- `outputs/<run-id>/manifest.json`
- `outputs/<run-id>/raw/chaos/baseline-observations.json`
- `outputs/<run-id>/raw/chaos/experiment-observations.json`
- `outputs/<run-id>/raw/chaos/orchestration-actions.json`
- `outputs/<run-id>/normalized/findings.json`
- `outputs/<run-id>/reports/executive-summary.md`

The normalized bundle must preserve experiment outcome evidence, not just raw
proxy or monitoring logs.

## Current Command Usage

Run the current fixture-backed flow from the repository root:

```bash
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
```

Current command behavior:

- loads the validated app, environment, and chaos profile
- resolves runtime auth for the selected app
- plans one reversible chaos experiment
- loads fixture-backed baseline and experiment monitoring observations
- injects one fixture-backed fault, evaluates thresholds, and attempts rollback
- writes raw artifacts, normalized findings, a manifest, and a Markdown summary
- exits with `0`, `1`, or `2` according to the chaos outcome contract

## Current Limitations

- this command currently uses fixture-backed monitoring and fault-control data,
  not a live Toxiproxy runtime
- `packet_loss` currently fails closed in the wrapper
- missing fixture files cause the run to fail with exit code `2`

## Locking And Rollback Guarantees

The runner contract requires:

- one active experiment per app/environment on the operator host
- a repo-local filesystem lock under `.toolkit-locks/chaos/`
- threshold-driven abort handling during the experiment window
- rollback attempts on success, abort, timeout, and general error paths

Later checkpoints may change the underlying implementation details, but they
must preserve these operator-facing guarantees.
