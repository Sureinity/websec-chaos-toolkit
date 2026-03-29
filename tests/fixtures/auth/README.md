# Authentication Fixture Contract

This directory reserves the auth-specific fixture matrix for the runtime auth
checkpoint work.

Planned valid coverage:

- `none`
- `bearer_token` with `token_env_var`
- `cookie` with `cookie_name` and `cookie_value_env_var`
- `session` with `session_header` and `session_value_env_var`
- `form` with `login_url`, `username_env_var`, and `password_env_var`

Planned failure coverage:

- missing env var
- blank env var value
- unsupported auth method
- unsupported SSO or MFA login flow
- login request failure
- login success response without reusable session material

Security expectations for all auth fixtures:

- never store live credentials in fixture files
- use env var names only
- verify that logs and error messages stay redacted
