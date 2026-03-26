# CLI Reference

The bootstrap scaffold exposes the intended public command tree:

```text
toolkit validate --app <id> --env <env>
toolkit pentest run --app <id> --env <env> --profile <name>
toolkit chaos run --app <id> --env <env> --profile <name>
toolkit report build --run-id <id>
```

Current command behavior:

- commands are registered and available in help output
- commands print scaffold status information
- commands exit with code `2` because execution flow is not implemented yet

Stable exit-code contract:

- `0`: no findings or a passing experiment
- `1`: medium or high findings, or a resilience failure
- `2`: configuration or runtime errors
