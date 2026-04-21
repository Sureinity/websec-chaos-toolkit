# Quickstart: Authenticated URL Audit

Use this tutorial when you want to run `toolkit audit <url>` against an
authenticated web application without preparing YAML files.

## Before You Start

Have these ready:

- a reachable target URL
- authorization to test the target
- one supported auth mode
- required auth environment variables exported in your shell

For API-based login flows, this is the preferred path:

```bash
export TOOLKIT_AUDIT_USERNAME="alice"
export TOOLKIT_AUDIT_PASSWORD="hunter2"
```

## Check Readiness

Run:

```bash
uv run toolkit doctor
```

Look for audit readiness covering:

- `httpx`
- `katana`
- `zap`
- `nuclei`
- `nmap`

## Run An API-Login Audit

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

What happens:

- `httpx` fingerprints the target
- `api_login` creates reusable auth state
- `katana` discovers same-origin routes
- ZAP and Nuclei audit the seed URL plus discovered routes
- Nmap stays limited to conservative host/service context

## Alternative: Classic HTML Form Login

Use `form` only when the target still exposes a classic login page, you know
the input field names, and it returns reusable cookies:

```bash
uv run toolkit audit https://target.internal \
  --auth-mode form \
  --login-url https://target.internal/login \
  --username-env-var TOOLKIT_AUDIT_USERNAME \
  --password-env-var TOOLKIT_AUDIT_PASSWORD \
  --login-username-field email \
  --login-password-field password
```

## Expected Output

The command prints:

- auth mode and auth source
- fingerprint final URL, title, and server
- discovered route count
- findings and report locations

## See Also

- `docs/how-to/run-authenticated-url-audit.md`
- `docs/reference/authentication.md`
- `docs/explanation/url-audit-model.md`
