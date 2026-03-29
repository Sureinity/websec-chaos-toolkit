# Configuration Reference

The repository-level configuration surface is fixed to these YAML files:

- `apps.yaml`
- `pentest-profiles.yaml`
- `chaos-profiles.yaml`

`toolkit validate` now enforces the current field-level and cross-file config
rules against these files when run from the repository root or another config
bundle directory.

The root repository copies of these files are valid sample configs and are safe
to use for local validation exercises.

## `apps.yaml`

Each app entry is expected to include:

- `id`
- `environment`
- `base_url`
- `host_targets`
- `target_allowlist`
- `auth`
- `health_endpoint`
- optional `metrics`
- `enabled_modules`

Locked application rules:

- `environment` is limited to `local` or `staging`
- `health_endpoint` must be a non-empty path starting with `/`
- `host_targets` must not be empty
- `target_allowlist` must not be empty
- the host from `base_url` must be present in `target_allowlist`
- `enabled_modules` must contain one or both of `pentest` and `chaos`
- production-like targets are fail-closed and are not part of the default v1
  contract

### Auth Method Matrix

`auth.method` is limited to these values:

- `none`
- `bearer_token`
- `cookie`
- `session`
- `form`

Locked auth rules:

- `none`
  - no auth-specific secret reference fields are allowed
- `bearer_token`
  - requires `token_env_var`
- `cookie`
  - requires `cookie_name`
  - requires `cookie_value_env_var`
- `session`
  - requires `session_header`
  - requires `session_value_env_var`
- `form`
  - requires `login_url`
  - requires `username_env_var`
  - requires `password_env_var`

Config stores references only. Real tokens, cookie values, usernames,
passwords, and session material must come from the runtime environment.

Runtime auth behavior, failure policy, and unsupported flows are defined in
`docs/reference/authentication.md`.

Repository-root sample coverage:

- `sample-internal-app`
  - `environment: local`
  - `auth.method: none`
- `sample-staging-auth-app`
  - `environment: staging`
  - `auth.method: form`
  - uses `username_env_var` and `password_env_var`

## `pentest-profiles.yaml`

Each profile is expected to define a profile name and tool settings.

Locked pentest profile rules:

- enabled tools must define at least one allowlisted rule or template
- safe mode remains enabled by default
- the core v1 tool set is `zap`, `nuclei`, and `nmap`
- `trivy` and `semgrep` remain optional add-ons and should not change the
  DAST-first default

## `chaos-profiles.yaml`

Each profile is expected to include:

- `name`
- `fault_type`
- `target_service`
- `baseline_duration_seconds`
- `experiment_duration_seconds`
- `abort_thresholds`
- `rollback`

Locked chaos rules:

- every injectable fault requires `abort_thresholds`
- every injectable fault requires `rollback`
- v1 faults are limited to safe, reversible proxy-style behaviors such as
  latency, bandwidth throttling, packet loss, timeout simulation, and
  connection refusal
- `controlled_restart` remains schema-reserved but should be rejected by
  validation until a dedicated implementation exists

## Contract Fixtures

The frozen config contract is represented in:

- `tests/fixtures/configs/valid/auth-method-matrix/`
- `tests/fixtures/configs/invalid/`

Those fixtures remain the source of truth for validation coverage beyond the
repository-root sample configs.
