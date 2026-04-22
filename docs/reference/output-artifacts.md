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

Failure semantics:

- a run can end with `status: failed` while still preserving normalized
  findings and a rebuilt Markdown report
- this happens when at least one core tool fails after other tools already
  completed and contributed findings
- treat `manifest.json` as the final outcome signal and the normalized/report
  artifacts as preserved partial results when present

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
- it does not depend on raw vendor artifacts at rebuild time

Useful partial-result rule:

- if `normalized/findings.json` exists, the run already preserved findings
  that can still be reviewed even when the overall manifest status is
  `failed`

See also:

- `docs/reference/cli.md`
- `docs/how-to/schedule-execution.md`
- `docs/explanation/safety-model.md`
