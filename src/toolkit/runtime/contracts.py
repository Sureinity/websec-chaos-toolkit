"""Container runtime contract types and execution mode definitions.

This module locks the portability model before Docker-backed execution is
introduced into the pentest path. Both runtime modes must satisfy the same
adapter, artifact, normalization, and exit-code contracts.

Runtime modes
-------------
- HOST: the adapter command runs as a direct subprocess on the operator host.
  Requires the scanner binary installed on PATH. This is the original and
  fallback execution path.
- CONTAINER: the adapter command runs inside a Docker container. The runtime
  backend translates the adapter's ToolExecution into a docker run invocation
  with bind mounts for config inputs and raw outputs. Does not require the
  scanner binary on the host.

Execution contract
-------------------
- Adapters define execution intent (ToolExecution) without knowing the backend.
- The runtime backend decides whether intent becomes a host subprocess or a
  containerized command.
- Artifact layout (outputs/<run-id>/raw/<tool>/...), normalization, report
  generation, and exit-code contracts remain unchanged across modes.
- The backend returns a RuntimeResult with the same shape regardless of mode.

Safety expectations
--------------------
- Containerized tools must remain read-only and explicitly allowlisted.
  The container runtime does not grant write access outside the mounted
  output directory.
- Optional adapters remain explicitly enabled in profiles. Container mode
  does not implicitly enable additional tools.
- Missing container runtime (docker not on PATH) is a hard runtime failure
  (exit code 2), not a silent skip.
- Missing container image is a hard runtime failure (exit code 2).

Operator expectations
----------------------
- Docker-first is the preferred portability path for environments without
  pre-installed scanner binaries.
- Host-binary mode remains a fully supported fallback.
- Both modes are selectable per-run; the choice does not affect adapter
  configuration or profile content.
"""

from enum import StrEnum


class RuntimeMode(StrEnum):
    """Execution backend mode for scanner tool invocation."""

    HOST = "host"
    CONTAINER = "container"


# Default Docker images for scanner tools.
# These are the official or community-standard images used by the
# container runtime backend when no explicit override is configured.
CONTAINER_TOOL_IMAGES: dict[str, str] = {
    "zap": "ghcr.io/zaproxy/zaproxy:stable",
    "nuclei": "projectdiscovery/nuclei:latest",
    "nmap": "instrumentisto/nmap:latest",
    "trivy": "aquasec/trivy:latest",
    "semgrep": "semgrep/semgrep:latest",
}

# Tools that are required to be available in the container runtime.
# Missing images for these tools are hard failures (exit 2).
CONTAINER_CORE_TOOLS: frozenset[str] = frozenset({"zap", "nuclei", "nmap"})
