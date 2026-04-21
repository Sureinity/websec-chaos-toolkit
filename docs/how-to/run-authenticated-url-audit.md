# Run An Authenticated URL Audit

Use this guide when you want `toolkit audit <url>` to reach authenticated
application surfaces without YAML config files.

## Choose An Auth Mode

Authentication is optional overall.

- no auth flags
  - unauthenticated audit
- `api_login`
  - primary automated path for JSON-based login APIs
- `form`
  - secondary compatibility path for classic HTML form login
- `bearer_token`, `cookie`, `session`
  - manual expert paths when reusable auth material already exists

Only one auth mode may be selected per run.

## Common Rules

- missing required flags fail closed
- mixed auth-mode flag sets fail closed
- explicit auth modes never downgrade to unauthenticated audit
- login endpoints must be enabled and reachable for `api_login` or `form`

## Preferred Path: `api_login`

Export credentials:

```bash
export TOOLKIT_AUDIT_USERNAME="alice"
export TOOLKIT_AUDIT_PASSWORD="hunter2"
```

Bearer token returned from JSON:

```bash
uv run toolkit audit https://target.internal \
  --auth-mode api_login \
  --login-url https://target.internal/api/login \
  --username-env-var TOOLKIT_AUDIT_USERNAME \
  --password-env-var TOOLKIT_AUDIT_PASSWORD \
  --login-content-type json \
  --login-username-field username \
  --login-password-field password \
  --auth-result bearer_json \
  --auth-result-path token
```

Reusable cookies returned by login:

```bash
uv run toolkit audit https://target.internal \
  --auth-mode api_login \
  --login-url https://target.internal/api/login \
  --username-env-var TOOLKIT_AUDIT_USERNAME \
  --password-env-var TOOLKIT_AUDIT_PASSWORD \
  --login-content-type json \
  --login-username-field email \
  --login-password-field password \
  --auth-result cookie
```

Session/header value returned from JSON:

```bash
uv run toolkit audit https://target.internal \
  --auth-mode api_login \
  --login-url https://target.internal/api/login \
  --username-env-var TOOLKIT_AUDIT_USERNAME \
  --password-env-var TOOLKIT_AUDIT_PASSWORD \
  --login-content-type json \
  --login-username-field username \
  --login-password-field password \
  --auth-result session_json \
  --auth-result-path data.session_id \
  --session-header X-Session-ID
```

## Compatibility Path: `form`

```bash
uv run toolkit audit https://target.internal \
  --auth-mode form \
  --login-url https://target.internal/login \
  --username-env-var TOOLKIT_AUDIT_USERNAME \
  --password-env-var TOOLKIT_AUDIT_PASSWORD \
  --login-username-field email \
  --login-password-field password
```

Use this only when:

- the target exposes an HTML login form
- you know the username and password input field names
- it returns reusable cookies after login

## Manual Expert Paths

Bearer token:

```bash
export TOOLKIT_AUDIT_TOKEN="..."
uv run toolkit audit https://target.internal \
  --auth-mode bearer_token \
  --token-env-var TOOLKIT_AUDIT_TOKEN
```

Cookie:

```bash
export TOOLKIT_AUDIT_COOKIE="..."
uv run toolkit audit https://target.internal \
  --auth-mode cookie \
  --cookie-name sessionid \
  --cookie-value-env-var TOOLKIT_AUDIT_COOKIE
```

Session header:

```bash
export TOOLKIT_AUDIT_SESSION="..."
uv run toolkit audit https://target.internal \
  --auth-mode session \
  --session-header X-Session-ID \
  --session-value-env-var TOOLKIT_AUDIT_SESSION
```

## Failure Cases

These return exit code `2`:

- disabled or unreachable login API for `api_login`
- disabled or unreachable login page for `form`
- invalid auth flag combinations
- missing required mode-specific flags
- missing reusable auth material after login

## Outputs

Authenticated URL audit still writes the standard run layout:

- `raw/httpx/fingerprint.json`
- `raw/katana/results.jsonl`
- `raw/katana/discovered-routes.txt`
- `raw/audit/auth-context.json`
- `normalized/findings.json`
- `reports/executive-summary.md`
- `manifest.json`
