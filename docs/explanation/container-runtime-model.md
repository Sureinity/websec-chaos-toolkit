# Container Runtime Model

This document explains the runtime abstraction that allows pentest tools to
run either as host subprocesses or inside Docker containers, and why
Docker-first is the preferred portability path.

## Why Two Runtime Modes

The toolkit targets operators in different environments:

- **Development machines** often have scanner binaries installed directly.
  Host-binary mode works naturally here.
- **CI environments, staging servers, and shared infrastructure** may not
  have ZAP, Nuclei, or Nmap installed. Installing scanner binaries on every
  host is a maintenance burden. Docker-backed execution lets operators run
  the same pentest workflow without host-level binary management.

Docker-first is preferred because it reduces the setup surface to one
dependency (Docker) instead of three or more scanner binaries.

## Architecture

```
Adapter (defines execution intent: ToolExecution)
  |
  v
Execution Service (routes through RuntimeBackend)
  |
  +-- RuntimeMode.HOST --> HostRuntime (subprocess)
  |
  +-- RuntimeMode.CONTAINER --> ContainerRuntime (docker run)
  |
  v
RuntimeResult (same shape regardless of backend)
  |
  v
Parse output, normalize findings, build report (unchanged)
```

The adapter does not know which backend will execute it. It builds a
`ToolExecution` (command, timeout, env overrides). The execution service
converts this to a `RuntimeRequest` and delegates to the selected backend.

## RuntimeBackend Protocol

Both `HostRuntime` and `ContainerRuntime` satisfy:

```python
class RuntimeBackend(Protocol):
    def check_tool_available(self, tool: str) -> AdapterAvailability: ...
    def execute(self, request: RuntimeRequest) -> RuntimeResult: ...
```

- `check_tool_available()` — verifies the tool can be executed. For host
  mode, checks binary on PATH. For container mode, checks Docker on PATH
  and image configured.
- `execute()` — runs the tool and returns stdout, stderr, returncode.

## Container Command Translation

The `ContainerRuntime` translates a `RuntimeRequest` into:

```
docker run --rm --network=host \
  -v <output_dir>:<output_dir> \
  -e KEY=VALUE \
  <image> \
  <tool_args_without_binary>
```

Key decisions:

- `--network=host` ensures localhost targets are reachable from the container
- `--rm` cleans up the container after execution
- The output directory is bind-mounted read-write so the tool can write
  its raw output file
- The binary name is omitted from the command because the image entrypoint
  provides it
- Environment overrides (like `NUCLEI_DISABLE_UPDATE_CHECK`) are forwarded
  with `-e`

## Default Images

| Tool | Image | Source |
|------|-------|--------|
| ZAP | `ghcr.io/zaproxy/zaproxy:stable` | OWASP official |
| Nuclei | `projectdiscovery/nuclei:latest` | ProjectDiscovery |
| Nmap | `instrumentisto/nmap:latest` | Community |
| Trivy | `aquasec/trivy:latest` | Aqua Security |
| Semgrep | `semgrep/semgrep:latest` | Semgrep Inc. |

Images can be overridden via `ContainerRuntime(image_overrides={...})`.

## Safety Boundaries

- Containers run read-only outside the mounted output directory
- `--network=host` is the only supported network mode
- The toolkit does not pull images automatically; operators must ensure
  images are available before running
- Missing Docker or missing image is a hard failure (exit code 2), not a
  silent degradation
- Optional adapters (Trivy, Semgrep) skip cleanly if their image is
  unavailable, just as they skip when host binaries are missing
- All adapter-level safety constraints (safe mode, allowlists) still apply
  because the adapter builds the command before the runtime translates it

## What Remains Planned

- **Automatic image pulling**: The toolkit could optionally pull missing
  images before execution. Currently operators must pre-pull.
- **Bridge networking**: For environments where `--network=host` is not
  available (e.g., Docker Desktop on macOS), a bridge mode with explicit
  port mapping may be needed.
- **Custom registries**: Private registries are supported via image
  overrides, but authenticated registry login is not managed.
- **Chaos container runtime**: Container execution is pentest-only. Chaos
  uses Toxiproxy directly on the host.

## See Also

- `docs/how-to/run-pentest-with-docker.md` — operator task guide
- `docs/reference/pentest-run.md` — runtime modes section
- `src/toolkit/runtime/contracts.py` — RuntimeMode and image definitions
- `src/toolkit/runtime/container.py` — container backend implementation
- `src/toolkit/runtime/host.py` — host backend implementation
