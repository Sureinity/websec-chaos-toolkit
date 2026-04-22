"""Docker Compose workflow contract for the toolkit operator story.

This module locks the Compose-based operator workflow before any YAML lands.
The Compose path is the preferred Docker-first operator story for running
pentest and chaos workflows together. Direct CLI use and host-binary mode
remain supported as fallback paths.

Service topology
----------------
A complete Compose environment defines three named services:

- TOOLKIT_RUNNER_SERVICE ("toolkit-runner"):
  the toolkit CLI container that runs validate/pentest/chaos/report
- APP_SERVICE_DEFAULT ("sample-app"):
  the example target application reachable on the shared Compose network
- TOXIPROXY_SERVICE ("toxiproxy"):
  the optional Toxiproxy server used by live chaos experiments

Operator modes
--------------
- PENTEST_ONLY: requires only the toolkit runner and a target app service
- PENTEST_PLUS_CHAOS: adds the Toxiproxy service for live chaos experiments
- HOST_INDEPENDENT: the same workflow runs on any Linux host with Docker
  Compose installed; no scanner binaries are required on the host

Mount expectations
------------------
- COMPOSE_CONFIG_MOUNT_PATH ("/workspace/config"): config bundle (apps.yaml,
  pentest-profiles.yaml, chaos-profiles.yaml) mounted read-only into the
  toolkit runner container
- COMPOSE_OUTPUTS_MOUNT_PATH ("/workspace/outputs"): outputs/<run-id>/...
  mounted read-write so artifacts persist back to the host
- COMPOSE_WORKDIR ("/workspace"): the toolkit runner's working directory

Network model
-------------
- COMPOSE_NETWORK_NAME ("toolkit-net"): shared bridge network connecting
  all services so they can resolve each other by service name
- The target app's apps.yaml base_url uses the service name as host
  (e.g., http://sample-app:8080) so the toolkit container reaches it on
  the shared network without --network=host hacks
- The Toxiproxy service is reachable at toxiproxy:8474 from the toolkit
  runner when chaos workflows are active

Operator expectations
----------------------
- Compose-first is the preferred portability path
- Direct CLI usage on the host remains supported as a fallback
- Host-binary mode remains supported for environments without Docker
"""

from enum import StrEnum

# Service names — these become DNS hostnames on the Compose network.
TOOLKIT_RUNNER_SERVICE: str = "toolkit-runner"
APP_SERVICE_DEFAULT: str = "sample-app"
TOXIPROXY_SERVICE: str = "toxiproxy"

# Required services per operator mode.
PENTEST_ONLY_SERVICES: frozenset[str] = frozenset(
    {
        TOOLKIT_RUNNER_SERVICE,
        APP_SERVICE_DEFAULT,
    }
)
PENTEST_PLUS_CHAOS_SERVICES: frozenset[str] = frozenset(
    {
        TOOLKIT_RUNNER_SERVICE,
        APP_SERVICE_DEFAULT,
        TOXIPROXY_SERVICE,
    }
)

# Mount paths inside the toolkit runner container.
COMPOSE_CONFIG_MOUNT_PATH: str = "/workspace/config"
COMPOSE_OUTPUTS_MOUNT_PATH: str = "/workspace/outputs"
COMPOSE_WORKDIR: str = "/workspace"

# Network name — services on this network resolve each other by service name.
COMPOSE_NETWORK_NAME: str = "toolkit-net"

# Required configuration files in the mounted config bundle.
REQUIRED_CONFIG_FILES: tuple[str, ...] = (
    "apps.yaml",
    "pentest-profiles.yaml",
    "chaos-profiles.yaml",
)


class ComposeOperatorMode(StrEnum):
    """Operator workflow modes supported by the Compose contract."""

    PENTEST_ONLY = "pentest_only"
    PENTEST_PLUS_CHAOS = "pentest_plus_chaos"


def required_services_for(mode: ComposeOperatorMode) -> frozenset[str]:
    """Return the set of services that must be defined for an operator mode."""
    if mode == ComposeOperatorMode.PENTEST_ONLY:
        return PENTEST_ONLY_SERVICES
    if mode == ComposeOperatorMode.PENTEST_PLUS_CHAOS:
        return PENTEST_PLUS_CHAOS_SERVICES
    raise ValueError(f"Unknown Compose operator mode: {mode}")
