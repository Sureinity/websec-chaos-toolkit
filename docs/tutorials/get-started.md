# Get Started

This tutorial is for contributors who want to inspect the scaffold locally.

## Goal

Create a local Python environment with `uv`, install the project dependencies,
and inspect the command tree.

## Steps

1. Run `uv sync --extra dev`.
2. Run `uv run toolkit --help` and inspect the bootstrap command layout.
3. Run `uv run toolkit validate --app sample-internal-app --env local`.
4. Run `uv run pytest` to verify the minimal scaffold checks.

The current scaffold does not execute scanners or chaos experiments yet, so
operational commands will exit with code `2`.
