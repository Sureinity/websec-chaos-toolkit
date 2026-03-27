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

The exhaustive contract matrix currently lives in `tests/fixtures/configs/`.
The repository root YAML files provide the current human-facing sample bundle
for `toolkit validate`.
