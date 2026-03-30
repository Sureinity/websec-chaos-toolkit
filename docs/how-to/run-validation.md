# Run Validation

Use this guide to validate one selected app/environment pair from a config
bundle.

## Before You Start

- install dependencies with `uv sync --extra dev`
- work from a directory that contains:
  - `apps.yaml`
  - `pentest-profiles.yaml`
  - `chaos-profiles.yaml`
- use one of the sanitized example packs under `examples/configs/` when you
  want a safe starting point

## Command

```bash
cd examples/configs/sample-webapp
uv run toolkit validate --app sample-internal-app --env local
```

## What The Command Does

- loads the repository-style YAML config bundle from the current working
  directory
- validates the selected `--app` and `--env` pair against the implemented
  schema and cross-file rules
- prints a short summary of the selected app, enabled modules, and available
  profile counts

Supporting reference:

- `docs/reference/configuration.md`
- `docs/reference/cli.md`

## Successful Output

On success, the command exits with `0` and prints a summary similar to:

```text
Configuration is valid.
App: sample-internal-app
Environment: local
Enabled modules: pentest, chaos
Pentest profiles: 1
Chaos profiles: 1
```

## Failure Behavior

On failure, the command exits with `2`.

Common failure cases:

- requested app/environment pair does not exist
- missing or invalid auth settings
- missing allowlists for enabled pentest tools
- missing health endpoint
- missing rollback config for chaos profiles
- production-like targets rejected by fail-closed validation

The error output includes the failing path and logical section when available.

## Example Packs

Safe example config bundles live in:

- `examples/configs/sample-webapp/`
- `examples/configs/sample-api/`

Use these to validate schema changes or verify local setup without introducing
real targets or secrets.

See also:

- `examples/configs/README.md`
- `docs/explanation/safety-model.md`
