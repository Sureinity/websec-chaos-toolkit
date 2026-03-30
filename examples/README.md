# Examples

This directory is reserved for sample artifacts and runnable examples that are
safe to share.

Bootstrap contents:

- `output-layout.md` documents the intended per-run artifact structure
- `configs/README.md` documents the locked v1 config contract and the reserved
  location for user-facing sample config packs
- `configs/sample-webapp/` is the default local-safe example bundle for
  fixture-backed validation, pentest, and chaos flows
- `configs/sample-api/` is the authenticated API-oriented example bundle for
  staging-safe validation and later smoke coverage

Future examples should stay sanitized and must not include real credentials,
real session material, or production targets.
