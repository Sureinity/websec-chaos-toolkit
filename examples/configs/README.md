# Sample Config Packs

This directory is reserved for user-facing sample configuration bundles.

The locked v1 config contract currently supports these authentication methods:

- `none`
- `bearer_token`
- `cookie`
- `session`
- `form`

Secrets remain out of YAML. Sample configs and future examples should only use
environment variable references such as `token_env_var`,
`cookie_value_env_var`, `session_value_env_var`, `username_env_var`, and
`password_env_var`.

Runtime auth resolution is fail-closed:

- missing env vars are hard failures
- blank env var values are hard failures
- form login is supported only for direct username/password flows
- SSO and MFA remain explicitly unsupported in v1

The exhaustive contract matrix currently lives in `tests/fixtures/configs/`.
The repository root YAML files provide the current human-facing sample bundle
for `toolkit validate`.

Current example packs:

- `sample-webapp/`
  - local-safe example with `auth.method: none`
  - enables both `pentest` and `chaos`
  - intended for fixture-backed operator walkthroughs
- `sample-api/`
  - staging-safe example with `auth.method: bearer_token`
  - keeps secrets in `token_env_var` only
  - intended for authenticated API-oriented validation examples
