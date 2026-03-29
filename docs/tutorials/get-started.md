# Get Started

This tutorial is for contributors who want to inspect the scaffold locally.

## Goal

Create a local Python environment with `uv`, install the project dependencies,
and inspect the command tree.

## Steps

1. Run `uv sync --extra dev`.
2. Run `uv run toolkit --help` and inspect the bootstrap command layout.
3. Run `uv run toolkit validate --app sample-internal-app --env local`.
4. Run `uv run toolkit pentest run --app local-no-auth-app --env local --profile safe-web-baseline`.
5. Run `uv run pytest` to verify the minimal scaffold checks.

`toolkit report build` is implemented and rebuilds summaries from stored
normalized findings. `toolkit pentest run` is implemented for the current
fixture-backed flow. `toolkit chaos run` is still scaffold-only and exits with
code `2`.
