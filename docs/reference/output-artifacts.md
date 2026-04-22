# Run Artifacts Reference

This document defines the run output layout implemented by `run_context` and the
report builder. It serves as the stable contract for downstream tooling and future
orchestration workflows.

## Layout

Each run lives under the project `outputs/` directory (created on demand). The
per-run path is:

```
outputs/
  <run-id>/
    manifest.json
    raw/
      audit/
        auth-context.json
        intensity-context.json
      pentest/
        execution-summary.json
      <tool>/
        ... (tool-specific logits)
    normalized/
      findings.json
    reports/
      executive-summary.md
```

`raw/` can store vendor outputs; normalized JSON and Markdown summaries are the
shared artifacts we care about for downstream automation.

Current examples:

- URL-first audit writes secret-safe audit metadata under `raw/audit/`,
  including `auth-context.json` and `intensity-context.json`
- pentest-backed runs write `raw/pentest/execution-summary.json` with the final
  per-tool execution summary
- pentest runs write scanner artifacts under `raw/zap/`, `raw/nuclei/`, and
  `raw/nmap/`
- chaos runs write experiment artifacts under `raw/chaos/`, including
  `baseline-observations.json`, `experiment-observations.json`, and
  `orchestration-actions.json`

## Run ID

- Generated with `YYYYMMDD-HHMMSS-<short-hash>` (timestamp in UTC plus digest of
  the requested app/env/profile inputs).
- Used to create the run directory and referenced in reports/notifications.
- If the directory already exists, `prepare_run_context` raises `FileExistsError`
  by default. Pass `allow_existing=True` to reopen an existing run directory.

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

`normalized/findings.json` is a JSON array of result objects with:

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

The json writer sorts keys and uses 2-space indentation so diffs stay readable.

## Rebuild A Report

Operators can rebuild the Markdown summary from an existing normalized bundle
without rerunning pentest or chaos commands.

Command:

```bash
uv run toolkit report build --run-id <existing-run-id>
```

What the command expects:

- `outputs/<run-id>/` exists
- `outputs/<run-id>/normalized/findings.json` exists

What the command writes:

- `outputs/<run-id>/reports/executive-summary.md`

Current behavior notes:

- report rebuild is implemented now
- it reads stored normalized findings only
- it can also enrich the report with secret-safe audit and execution metadata
  when those raw context artifacts exist

See also:

- `docs/reference/cli.md`
- `docs/how-to/schedule-execution.md`
- `docs/explanation/safety-model.md`
