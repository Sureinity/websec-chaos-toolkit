# Config Fixture Matrix

These fixtures freeze the intended validation contract before the real
validators are implemented.

Valid matrix:

- `valid/auth-method-matrix/`
  - one `apps.yaml` file containing representative valid app entries for:
    - `none`
    - `bearer_token`
    - `cookie`
    - `session`
    - `form`

Invalid cases:

- `invalid/missing-target-allowlist/`
- `invalid/missing-health-endpoint/`
- `invalid/auth-none-with-secret/`
- `invalid/auth-cookie-missing-value-ref/`
- `invalid/auth-session-missing-header/`
- `invalid/auth-form-missing-password/`
- `invalid/pentest-tool-missing-allowlist/`
- `invalid/chaos-missing-rollback/`
- `invalid/production-like-environment/`
- `invalid/controlled-restart-fault/`

Each invalid directory is self-contained so future tests can load only that
case and assert the exact failure mode.
