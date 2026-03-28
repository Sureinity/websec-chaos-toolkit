# Run Artifacts Reference

This document defines the run output layout that the toolkit will adopt before any
orchestration logic writes real artifacts. Treat it as the contract that `run_context`
and the report builder implement.

## Layout

Each run lives under the project `outputs/` directory (created on demand). The
per-run path is:

```
outputs/
  <run-id>/
    manifest.json
    raw/
      <tool>/
        ... (tool-specific logits)
    normalized/
      findings.json
    reports/
      executive-summary.md
```

`raw/` can store vendor outputs; normalized JSON and Markdown summaries are the
shared artifacts we care about for downstream automation.

## Run ID

- Generated with `YYYYMMDD-HHMMSS-<short-hash>` (timestamp in UTC plus digest of
  the requested app/env/profile inputs).
- Used to create the run directory and referenced in reports/notifications.
- If the directory already exists, subsequent attempts should incrementally
  reuse or reject based on `run_context` configuration.

## Manifest

`manifest.json` describes the run:

 - `run_id`
 - `app_id`
 - `environment`
 - `profile`
 - `modules`: list of enabled domains (e.g., `["pentest", "chaos"]`)
 - `start_time` / `end_time` (ISO 8601 UTC)
 - `status`: one of `pending`, `success`, `failed`
 - `exit_code`

Future checkpoints can extend the manifest (e.g., tools metadata, triggered_by).

## Normalized Results Schema

`normalized/findings.json` should be a JSON array of result objects with:

 - `app_id`
 - `environment`
 - `target`
 - `tool`
 - `category`
 - `severity` (`info`, `low`, `medium`, `high`, `critical`)
 - `confidence` (`low`, `medium`, `high`)
 - `evidence`: array of strings
 - `remediation_summary`
 - `timestamps` with `started_at` and optional `finished_at` in ISO format

The json writer should sort keys and use consistent indentation so diffs stay
readable.
