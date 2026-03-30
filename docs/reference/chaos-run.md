# Chaos Run Reference

This document locks the orchestration contract for `toolkit chaos run` before
the runner implementation lands.

Current implementation status:

- `toolkit chaos run` remains scaffold-only and currently exits with code `2`
- this reference defines the lifecycle and safety rules that Checkpoints 2 to 6
  must preserve

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

The future chaos run path must write or preserve:

- `outputs/<run-id>/manifest.json`
- `outputs/<run-id>/raw/chaos/...`
- `outputs/<run-id>/normalized/findings.json`
- `outputs/<run-id>/reports/executive-summary.md`

The normalized bundle must preserve experiment outcome evidence, not just raw
proxy or monitoring logs.

## Locking And Rollback Guarantees

The runner contract requires:

- one active experiment per app/environment on the operator host
- a repo-local filesystem lock under `.toolkit-locks/chaos/`
- threshold-driven abort handling during the experiment window
- rollback attempts on success, abort, timeout, and general error paths

Later checkpoints may change the underlying implementation details, but they
must preserve these operator-facing guarantees.
