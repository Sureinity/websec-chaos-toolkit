# URL Audit Model

`toolkit audit <url>` is the simple operator path for remote web assessment.

It now has three layers:

1. preflight fingerprinting via `httpx`
2. same-origin route discovery via `katana`
3. safe remote-web scanning via ZAP, Nuclei, and Nmap

## Intensity Model

URL-first audit supports three explicit intensity modes:

- `safe`
  - the omitted default
  - preserves the current bounded audit behavior
- `balanced`
  - increases route and scanner budgets relative to `safe`
- `deep`
  - increases route and scanner budgets relative to `balanced`

All intensity modes remain read-only and non-destructive.
Higher intensity increases traffic volume, total runtime, and timeout risk.

## Auth Model

Auth is optional overall.

- no auth flags
  - unauthenticated audit
- `api_login`
  - primary automated path for modern apps with JSON login APIs
- `form`
  - compatibility path for classic HTML login forms
- `bearer_token`, `cookie`, `session`
  - manual expert modes

Only one auth mode is allowed per run.

The audit path fails closed when:

- required auth flags are missing
- auth modes are mixed
- explicit auth cannot produce reusable auth material

## Discovery Model

Route discovery is same-origin only.

- the seed URL is always kept in scope
- `katana` adds same-origin routes
- discovered routes are deduplicated deterministically
- external links are excluded from the audit scope

## Scanner Roles

- `httpx`
  - fingerprint summary only
- `katana`
  - discovery only
- `ZAP`
  - passive and safe web checks across the in-scope routes
- `Nuclei`
  - curated HTTP exposure checks across the in-scope routes
- `Nmap`
  - conservative host and service context only

## Artifact Model

The URL-first audit flow preserves the standard run layout and adds
preflight/discovery metadata under `raw/`:

- `raw/httpx/fingerprint.json`
- `raw/katana/results.jsonl`
- `raw/katana/discovered-routes.txt`
- `raw/audit/auth-context.json`

Those artifacts enrich reporting but do not become normalized findings by
themselves.
