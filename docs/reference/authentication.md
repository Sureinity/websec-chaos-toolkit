# Authentication Reference

This document locks the runtime authentication contract for v1. It describes
how validated app config is expected to turn into runtime auth material for
scanner and chaos workflows.

Current state:

- config-level auth validation is implemented
- runtime auth resolution is implemented for `api_login` with JSON login
  payloads and reusable auth extraction modes
- env-backed runtime auth resolution is implemented for `bearer_token`,
  `cookie`, and `session`
- direct form login is implemented for operator-supplied form field names and
  cookie-based session reuse
- a shared runtime auth/session payload is implemented for supported auth modes
- a higher-level auth bootstrap entrypoint is implemented for validated app
  config
- this document remains the runtime auth contract for scanner and chaos adapter integration
- Milestone 16 extends this contract into the URL-first `toolkit audit <url>`
  path and introduces `api_login` as the primary automated auth path for apps
  whose login logic is API-based with JSON

## Supported Auth Modes

The runtime layer supports these auth modes only:

- `none`
- `api_login`
- `bearer_token`
- `cookie`
- `session`
- `form`

Anything outside this list is out of scope for v1.

## Runtime Resolution Rules

### `none`

- no secret resolution is attempted
- no headers or cookies are injected
- the runtime auth payload should be explicitly marked as unauthenticated
- this remains valid for URL-first audit even when the target login route is
  disabled

### `api_login`

- perform a scripted HTTP login against `login_url`
- resolve credentials only from `username_env_var` and `password_env_var`
- send a JSON payload for the current milestone
- use configurable credential field names for the JSON request body
- extract reusable authenticated session material derived from the login API
- support response extraction into:
  - bearer token from JSON
  - reusable cookies from the response
  - session/header value from JSON
- do not attempt browser automation, SSO handshakes, or MFA bypass
- treat `api_login` as the primary documented automated auth path for
  URL-first audit on modern web apps

### `bearer_token`

- resolve the token only from `token_env_var`
- inject the resolved secret as `Authorization: Bearer <token>`
- do not support inline token values in YAML

### `cookie`

- use `cookie_name` from config
- resolve the cookie value only from `cookie_value_env_var`
- inject the resolved pair as a request cookie

### `session`

- use `session_header` from config
- resolve the header value only from `session_value_env_var`
- inject the resolved pair as a request header

### `form`

- perform a scripted HTTP login against `login_url`
- resolve credentials only from `username_env_var` and `password_env_var`
- return reusable authenticated session material derived from the login flow
- submit operator-supplied username and password form field names
- treat reusable cookies as the success signal for the current implementation
- do not attempt browser automation, SSO handshakes, or MFA bypass
- treat `form` as a secondary compatibility path for classic HTML login forms

## URL-First Audit Rules

The URL-first `toolkit audit <url>` path follows these auth rules:

- authentication is optional overall
- if no auth mode is selected, the audit runs unauthenticated
- at most one auth mode may be selected per run
- mixed auth-mode flag sets must fail closed
- selecting one auth mode makes that mode's flags required
- explicit auth modes must never silently downgrade to unauthenticated audit

For URL-first audit, recommended auth-mode priority is:

1. `api_login`
2. `form`
3. manual `bearer_token`, `cookie`, or `session`

## URL-First Audit Prerequisites

Before running authenticated URL-first audit, the operator should have:

- authorization to test the target
- a reachable target URL
- a valid test account or reusable auth material
- the chosen auth mode for the target
- a shell environment where secret values can be supplied through environment
  variables

Mode-specific prerequisites:

- `api_login`
  - the login API route is enabled and reachable during the run
  - the login request uses JSON
  - the username and password field names are known
  - the reusable auth result shape is known:
    - bearer token in JSON
    - session/header value in JSON
    - reusable cookies from the response
- `form`
  - the visible login route is enabled and reachable during the run
  - the username and password input field names are known
  - successful login returns reusable cookies
- `bearer_token`
  - the operator already has a valid bearer token
- `cookie`
  - the operator already has a valid authenticated cookie name and value
- `session`
  - the operator already has a valid session header name and value

## Failure Policy

All runtime auth resolution is fail-closed.

- missing env vars are hard failures
- blank env var values are hard failures
- login failures are hard failures
- unsupported login flows are hard failures
- runtime auth should never silently downgrade from authenticated to
  unauthenticated behavior
- disabled or unreachable login endpoints are hard failures for explicit
  `form` or `api_login` modes
- responses that produce no reusable auth material are hard failures for
  explicit `form` or `api_login` modes

## Secret Handling Rules

- YAML stores references only, never live credentials
- secret values must never appear in logs, exception strings, or report output
- redaction must apply to bearer tokens, cookie values, session values,
  usernames, and passwords
- debug metadata may describe the source env var name, but not its resolved
  value
- the persisted URL-first audit auth context must store only secret-safe
  provenance keys, not raw headers, cookies, or resolved auth material
- verbose runtime logs must redact auth-bearing command arguments before they
  are printed

## Unsupported Flows

These flows must fail explicitly rather than partially working:

- full SSO orchestration
- MFA challenges
- interactive browser login
- CAPTCHAs or human-verification checkpoints
- any flow that requires manual operator intervention mid-run

## Runtime Session Shape

The runtime auth layer now normalizes supported modes into one reusable
session/auth payload for adapters. That payload describes:

- auth method
- headers to inject
- cookies to inject
- limited, redacted provenance metadata

The current bootstrap entrypoint resolves a validated app config into that
shared runtime session shape for:

- `none`
- `api_login`
- `bearer_token`
- `cookie`
- `session`
- `form`
