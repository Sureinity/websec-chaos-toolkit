# Get Started

This tutorial is for contributors who want to inspect the scaffold locally.

## Goal

Create a local Python environment, install the package in editable mode, and
inspect the command tree.

## Steps

1. Create and activate a virtual environment.
2. Install the project with development dependencies.
3. Run `toolkit --help` and inspect the bootstrap command layout.
4. Run `pytest` to verify the minimal scaffold checks.

The current scaffold does not execute scanners or chaos experiments yet, so
operational commands will exit with code `2`.
