# Architecture

The bootstrap scaffold separates responsibilities early so later work does not
collapse into ad hoc shell wrappers.

## Package Boundaries

- `commands/` owns CLI registration and argument capture
- `config/` owns YAML loading and typed models
- `pentest/` and `chaos/` own orchestration flows
- `adapters/` owns external tool boundaries
- `auth/` owns reusable session and credential handling helpers
- `results/` owns normalized finding contracts
- `reports/` owns rendered outputs
- `safety/` owns fail-closed checks

## Why The Commands Exit Early

The scaffold wires the public command tree now so future implementation can
grow behind a stable interface. Returning exit code `2` avoids falsely implying
that scans or experiments are already safe to run.
