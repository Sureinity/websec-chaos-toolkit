# Code Audit Model

This document locks the intended shape of the planned `toolkit code-audit`
workflow before command wiring begins.

Status:

- `Planned later`

The command described here is not implemented yet. This document exists so the
future implementation can follow one stable contract.

## Purpose

`toolkit code-audit <path>` is intended to be the codebase counterpart to
`toolkit audit <url>`.

It is for:

- a local repository
- a checked-out source tree
- a local configuration tree

It is not for:

- a running web application
- a deployed URL
- a container image
- a packaged artifact

Those belong to other workflows:

- `toolkit audit <url>` for remote web assessment
- advanced profile-driven image or artifact analysis for Trivy image mode

## Locked Target Shape

The planned command contract is:

```text
toolkit code-audit <path> [--tool semgrep|trivy]
```

Target rules:

- exactly one filesystem path per run
- local source-tree path only
- no repository YAML required
- no app/profile selection flags

The command should build an in-memory source-tree target rather than relying on
`apps.yaml` or `pentest-profiles.yaml`.

## Locked Tool Contract

Default tool set:

- `semgrep`
- `trivy`

Optional narrowing:

- `--tool semgrep`
- `--tool trivy`

Excluded from this command:

- `zap`
- `nuclei`
- `nmap`

Reason:

- `semgrep` and `trivy` are meaningful for `source_tree`
- `zap`, `nuclei`, and `nmap` are meaningful for `remote_web`

The future code-audit implementation must not silently mix those target types.

## Locked Assessment Mode

The built-in code-audit workflow must map to:

- `assessment_mode: source_tree`

It must not act like:

- `remote_web`
- `artifact_image`

Image or artifact analysis may exist later, but it is a separate operator story
from the initial `toolkit code-audit <path>` command.

## Why This Split Matters

The existing toolkit already distinguishes:

- live remote web assessment
- local code or artifact analysis

What is missing is a simple operator entrypoint for source-tree analysis.

This contract keeps the command simple:

- one path
- two tools
- no YAML
- no profile selection

That simplicity is the point of the new UX.

## See Also

- `docs/explanation/pentest-target-model.md`
- `docs/how-to/run-code-and-artifact-checks.md`
- `docs/explanation/implementation-roadmap.md`
