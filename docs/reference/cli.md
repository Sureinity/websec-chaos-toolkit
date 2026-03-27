# CLI Reference

The bootstrap scaffold exposes the intended public command tree:

```text
toolkit validate --app <id> --env <env>
toolkit pentest run --app <id> --env <env> --profile <name>
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

Current command behavior:

- `toolkit validate` loads the repository YAML files from the current working
  directory, validates the selected `--app/--env` pair, and exits with `0` on
  success
- `toolkit pentest run`, `toolkit chaos run`, and `toolkit report build` remain
  scaffold-only and currently exit with code `2`

Stable exit-code contract:

- `0`: no findings or a passing experiment
- `1`: medium or high findings, or a resilience failure
- `2`: configuration or runtime errors
