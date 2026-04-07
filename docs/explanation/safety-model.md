# Safety Model

This document explains why the toolkit behaves conservatively and how each
execution path stays within the v1 safety boundaries.

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

These guardrails exist so execution-backed integrations do not widen
scope by accident.

See also:

- `docs/reference/configuration.md`
- `docs/how-to/run-validation.md`

## Execution Mode Boundary

Two pentest execution modes are maintained with distinct safety profiles:

### Live execution mode (current default)

`toolkit pentest run` invokes real external scanner binaries against a live
target. Safety limits in this mode:

- environments must be `local` or `staging`; production-like targets are
  rejected before any binary runs
- all adapters operate in safe mode; `safe_mode: false` is a hard error
- tool commands are built from allowlists only (ZAP rules, Nuclei templates)
- core binary missing → hard failure (exit 2); no silent degradation
- optional binary missing → explicit skip; run continues

### Fixture-backed mode (onboarding and offline testing)

`run_pentest_fixture_flow()` reads pre-recorded tool outputs from repository
fixture files. No external binaries or live targets are required. This mode is
used for onboarding, CI without scanner installations, and adapter unit tests.

### Live chaos execution mode (current default)

`toolkit chaos run` connects to a real Toxiproxy API server, captures live
health observations, and injects real faults. Safety limits:

- environments must be `local` or `staging`
- health monitoring and rollback config are mandatory
- one active experiment per app/environment (filesystem lock)
- rollback always attempted (finally block)
- `packet_loss` is fail-closed (no safe Toxiproxy mapping)
- `controlled_restart` is rejected until a safe implementation exists
- the toolkit never installs or manages Toxiproxy

### Fixture-backed chaos mode (onboarding and offline testing)

`run_chaos_fixture_flow()` reads pre-recorded observations from repository
fixture files and uses a non-networked controller. No Toxiproxy or live
target is required.

Report rebuild (`toolkit report build`) is fully implemented from stored
normalized findings and does not depend on replaying raw tool output in
either mode.

## Pentest Safety Boundaries

The live pentest path preserves these operator-visible limits:

- only the curated core v1 tool set runs by default: ZAP, Nuclei, Nmap
- optional tools (Trivy, Semgrep) run only when explicitly enabled in the profile
- command construction is safe by default and allowlist-driven
- disabled tools produce explicit skips rather than being run implicitly
- destructive or exploit-heavy behavior is not part of the default profiles
- findings are normalized before reporting so vendor-specific raw output does
  not leak into the stable report contract
- core tool binaries must be pre-installed; the toolkit never downloads them

See also:

- `docs/reference/pentest-adapters.md`
- `docs/reference/pentest-run.md`
- `docs/how-to/run-pentest.md`
- `docs/how-to/run-live-pentest.md`
- `docs/explanation/live-execution-model.md`

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
- `docs/how-to/run-live-chaos.md`
- `docs/explanation/live-chaos-model.md`

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
