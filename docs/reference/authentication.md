# Authentication Reference

This document locks the runtime authentication contract for v1. It describes
how validated app config is expected to turn into runtime auth material for
scanner and chaos workflows.

Current state:

- config-level auth validation is implemented
- runtime auth resolution helpers are not implemented yet
- this document is the contract those helpers should follow

## Supported Auth Modes

The runtime layer supports these auth modes only:

- `none`
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

### `bearer_token`

- resolve the token only from `token_env_var`
- inject the resolved secret as an authorization header
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
- do not attempt browser automation, SSO handshakes, or MFA bypass

## Failure Policy

All runtime auth resolution is fail-closed.

- missing env vars are hard failures
- blank env var values are hard failures
- login failures are hard failures
- unsupported login flows are hard failures
- runtime auth should never silently downgrade from authenticated to
  unauthenticated behavior

## Secret Handling Rules

- YAML stores references only, never live credentials
- secret values must never appear in logs, exception strings, or report output
- redaction must apply to bearer tokens, cookie values, session values,
  usernames, and passwords
- debug metadata may describe the source env var name, but not its resolved
  value

## Unsupported Flows

These flows must fail explicitly rather than partially working:

- full SSO orchestration
- MFA challenges
- interactive browser login
- CAPTCHAs or human-verification checkpoints
- any flow that requires manual operator intervention mid-run

## Future Runtime Shape

The runtime auth layer should normalize all supported modes into one reusable
session/auth payload for adapters. That payload should be able to describe:

- auth method
- headers to inject
- cookies to inject
- limited, redacted provenance metadata

That normalized runtime shape is implemented in a later checkpoint, but the
behavior above is already fixed by this contract.
