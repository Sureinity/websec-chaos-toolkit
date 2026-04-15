# Code Audit Model

This document describes the implemented `toolkit code-audit` workflow.

Status:

- `Implemented now`

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

## Target Shape

The implemented command contract is:

```text
toolkit code-audit <path> [--tool semgrep|trivy]
```

Target rules:

- exactly one filesystem path per run
- local source-tree path only
- no repository YAML required
- no app/profile selection flags

The command builds an in-memory source-tree target rather than relying on
`apps.yaml` or `pentest-profiles.yaml`.

## Tool Contract

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

The command does not silently mix those target types.

## Assessment Mode

The built-in code-audit workflow maps to:

- `assessment_mode: source_tree`

It must not act like:

- `remote_web`
- `artifact_image`

Image or artifact analysis may exist later, but it remains a separate operator
story from `toolkit code-audit <path>`.

## Why This Split Matters

The existing toolkit already distinguishes:

- live remote web assessment
- local code or artifact analysis

This command keeps the operator path simple:

- one path
- two tools
- no YAML
- no profile selection

That simplicity is the point of the new UX.

## See Also

- `docs/explanation/pentest-target-model.md`
- `docs/how-to/run-code-audit.md`
- `docs/how-to/run-code-and-artifact-checks.md`
- `docs/explanation/implementation-roadmap.md`
