# Run Code And Artifact Checks

Use this guide when the target is not a running web server, but a **local
source tree**, **filesystem path**, or **image or artifact**.

This is the correct operator path for tools such as:

- `trivy`
- `semgrep`

Status note:

- `toolkit code-audit <path>` is now implemented as the simpler source-tree path
- this guide remains the advanced profile-driven workflow for source-tree,
  image, and artifact analysis beyond the simple path

Do not use this workflow as a substitute for a live remote-web pentest.

## When To Use This Guide

Use this guide for:

- repository or source-tree analysis
- configuration and filesystem analysis
- image or artifact analysis

Do not use this guide for:

- a running Django app
- a deployed web service
- an HTTP endpoint you want to probe over the network

For those cases, use:

- `docs/how-to/run-live-pentest.md`
- `docs/how-to/run-code-audit.md` for the zero-config source-tree path

## Tool Roles

### Trivy

Use Trivy for:

- filesystem analysis
- image analysis
- artifact analysis

Current operator hooks:

- `TOOLKIT_TRIVY_TARGET_PATH`
  - required for filesystem analysis
- `TOOLKIT_TRIVY_IMAGE_REF`
  - required for image analysis when the profile uses `profile: image-audit`

### Semgrep

Use Semgrep for:

- source tree analysis

Semgrep is only meaningful in an explicit `source_tree` profile. It should not
be treated as a remote-web scanner.

## Example Profile Shape

Example source-tree profile:

```yaml
profiles:
  - name: safe-code-scan
    assessment_mode: source_tree
    tools:
      trivy:
        enabled: true
        safe_mode: true
        profile: config-audit
        allowlisted_rules:
          - vulnerabilities
          - misconfigurations
      semgrep:
        enabled: true
        safe_mode: true
        profile: default
        allowlisted_rules:
          - p/default
          - p/secrets
```

Example image-analysis profile:

```yaml
profiles:
  - name: safe-image-audit
    assessment_mode: artifact_image
    tools:
      trivy:
        enabled: true
        safe_mode: true
        profile: image-audit
        allowlisted_rules:
          - vulnerabilities
```

## Filesystem Analysis With Trivy

Export the target path:

```bash
export TOOLKIT_TRIVY_TARGET_PATH=/path/to/source-or-config-tree
```

Run a profile that enables Trivy under `assessment_mode: source_tree`.

Current note:

- Trivy is the primary filesystem or artifact analysis tool
- Semgrep remains reserved for explicit code-scan profiles

## Image Analysis With Trivy

Export the image reference:

```bash
export TOOLKIT_TRIVY_IMAGE_REF=my-image:latest
```

Run a profile that enables Trivy with:

- `assessment_mode: artifact_image`
- `profile: image-audit`

## Current Limits

- remote-web profiles should not enable Trivy or Semgrep by default
- Semgrep belongs to explicit code-scan workflows only
- code and artifact analysis are intentionally separated from live remote-web
  pentest runs

## See Also

- `docs/explanation/pentest-target-model.md`
- `docs/how-to/run-live-pentest.md`
- `docs/reference/pentest-run.md`
- `docs/reference/pentest-adapters.md`
