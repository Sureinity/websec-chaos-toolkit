# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows Semantic
Versioning while it remains in the pre-1.0 phase.

## [Unreleased]

### Added

- URL-first commands for `toolkit audit`, `toolkit edge-chaos`, and
  `toolkit code-audit`
- Audit intensity modes plus URL-first auth flags, including `api_login`
- Live pentest execution through host and Docker container runtime backends
- Live Toxiproxy-backed chaos execution and managed URL-first edge-chaos runs
- Expanded `toolkit doctor` readiness checks for code-audit paths and tool
  selection
- Checked-in Compose workflow assets and the Compose-aware sample config pack

### Changed

- Optional Trivy and Semgrep adapters now participate in live pentest runs
  when explicitly enabled and skip cleanly when unavailable
- Report rebuilding can enrich summaries with stored execution metadata and
  secret-safe audit context when those artifacts exist
- Documentation now distinguishes static Compose contract coverage from direct
  host or runtime-backed execution paths

### Notes

- `tests/integration/test_compose_workflow.py` validates the Compose assets
  statically; it does not start containers or verify a packaged runner image

## [0.2.0] - 2026-04-06

### Added

- Real configuration loading and validation through `toolkit validate`
- Stable run workspace creation, manifest writing, normalized result bundles,
  and Markdown report rebuilding through `toolkit report build`
- Runtime authentication bootstrap for:
  - bearer token
  - cookie
  - session
  - direct form login
- Safe scanner adapter contract plus fixture-driven adapters for:
  - ZAP
  - Nuclei
  - Nmap
- Optional fixture-driven adapters for:
  - Trivy
  - Semgrep
- Fixture-backed pentest orchestration with stable artifacts and exit codes
- Fixture-backed chaos orchestration with:
  - deterministic planning
  - host locking
  - Toxiproxy wrapper
  - baseline monitoring
  - abort-threshold evaluation
  - rollback handling
- Sanitized example config packs for a sample web app and a sample API app
- Example-driven smoke coverage for documented validation, pentest, chaos, and
  report flows

### Changed

- Contributor and operator docs now follow an example-driven onboarding path
- Safety rationale, fixture-backed boundaries, and scheduling guidance are now
  documented explicitly
- Optional Trivy and Semgrep adapters now participate in pentest runs only when
  explicitly enabled and skip cleanly when unavailable

### Notes

- `toolkit pentest run` and `toolkit chaos run` are implemented now, but remain
  fixture-backed rather than live-target execution
- External-binary smoke tests remain opt-in through
  `TOOLKIT_RUN_EXTERNAL_TOOL_TESTS=1`
- Live scanner execution and live Toxiproxy-backed chaos execution are planned
  later

## [0.1.0]

Initial bootstrap version used during early repository setup before formal
release notes were published.
