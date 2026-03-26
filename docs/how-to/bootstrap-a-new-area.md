# Bootstrap A New Area

Use the existing package boundaries when adding new implementation work.

1. Put CLI wiring under `src/toolkit/commands/`.
2. Put user-facing config models and loaders under `src/toolkit/config/`.
3. Put orchestration flow under either `src/toolkit/pentest/` or
   `src/toolkit/chaos/`.
4. Keep vendor-specific process execution behind `src/toolkit/adapters/`.
5. Normalize findings before report generation.

This keeps the scaffold aligned with the repository contract in `AGENTS.md`.
