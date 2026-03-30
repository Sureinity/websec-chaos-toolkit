# Safety Model

This document explains why the toolkit behaves conservatively and how the
current fixture-backed implementation stays within the v1 safety boundaries.

## Why The Toolkit Fails Closed

The toolkit is meant for internal testing, but that does not make implicit risk
acceptable. The repository therefore prefers explicit refusal over permissive
guessing.

Current safety posture:

- validation rejects incomplete or ambiguous configuration before a run starts
- auth material stays out of YAML and resolves only from runtime environment
  variables
- pentest and chaos outputs are normalized before reporting
- run artifacts are written under a stable `outputs/<run-id>/` layout so later
  review does not depend on transient tool output

This is why the implemented commands return exit code `2` for config and
runtime failures instead of silently degrading.

## Config And Target Guardrails

The current implementation keeps these boundaries explicit:

- environments are limited to `local` and `staging`
- target allowlists must exist and must cover the selected base URL host
- production-like targets are rejected by fail-closed validation
- enabled pentest tools require allowlisted rules or templates
- chaos profiles require rollback configuration and abort thresholds
- `controlled_restart` is schema-reserved but rejected until a dedicated safe
  implementation exists

These guardrails exist so later execution-backed integrations do not widen
scope by accident.

See also:

- `docs/reference/configuration.md`
- `docs/how-to/run-validation.md`

## Fixture-Backed Boundary

The current pentest and chaos commands are implemented now, but they are
fixture-backed.

That means:

- pentest adapters currently read repository fixture artifacts instead of
  invoking live external scanner binaries
- chaos orchestration currently uses fixture-backed monitoring observations and
  a Toxiproxy-like controller instead of a live Toxiproxy runtime
- report rebuild is fully implemented from stored normalized findings and does
  not depend on replaying raw external tool output

This boundary is deliberate. It keeps the command surface, artifact model, and
exit-code contract stable while execution-backed integrations are added later.

Do not describe the current state as live end-to-end scanner execution or live
chaos execution.

## Pentest Safety Boundaries

The current pentest path preserves these operator-visible limits:

- only the curated core v1 tool set is modeled by default:
  - ZAP
  - Nuclei
  - Nmap
- command construction is safe by default and allowlist-driven
- disabled tools skip cleanly instead of being run implicitly
- destructive or exploit-heavy behavior is not part of the default profiles
- findings are normalized before reporting so vendor-specific raw output does
  not leak into the stable report contract

Today, the safety boundary is expressed through fixture-backed adapter outputs.
Later execution-backed work must preserve the same operator-facing limits.

See also:

- `docs/reference/pentest-adapters.md`
- `docs/reference/pentest-run.md`
- `docs/how-to/run-pentest.md`

## Chaos Safety Boundaries

The current chaos path preserves these operator-visible limits:

- one reversible fault at a time
- mandatory health monitoring before and during an experiment
- optional metrics, with health-only mode remaining valid
- required abort thresholds
- required rollback configuration
- one active experiment per app/environment on the operator host
- rollback attempts on success, abort, timeout, and general error paths

The supported contract remains intentionally narrow:

- `latency`
- `bandwidth`
- `timeout`
- `connection_refused`

`packet_loss` is part of the contract surface but currently fails closed in the
wrapper because the present Toxiproxy mapping is not available as a safe
first-party toxic in the official API.

See also:

- `docs/reference/chaos-run.md`
- `docs/how-to/run-chaos.md`

## External Verification Boundary

Some verification paths are intentionally optional:

- external scanner-binary checks
- external tool adapter smoke tests
- future live Toxiproxy-backed chaos checks

These remain opt-in so the default local workflow stays deterministic and safe.
When external verification exists, the docs should say so explicitly instead of
implying that the default workflow depends on those binaries.

## What Changes Later Must Preserve

Future execution-backed work can replace fixture-backed inputs, but it must
preserve these operator-visible properties:

- fail-closed validation before execution
- sanitized sample configs and example docs
- explicit allowlists and explicit rollback requirements
- stable raw, normalized, and report artifact layout
- stable exit code meanings
- clear separation between implemented now, fixture-backed now, and planned
  later

This safety model is the rationale that supports the current how-to and
reference pages.
