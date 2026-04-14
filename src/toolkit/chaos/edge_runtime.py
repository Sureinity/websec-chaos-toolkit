"""Planning and readiness helpers for the future URL-first edge-chaos path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from toolkit.adapters.process import find_binary
from toolkit.config.models import AppConfig
from toolkit.targets import build_url_edge_chaos_app

EdgeChaosFaultType = Literal[
    "latency",
    "bandwidth",
    "timeout",
    "connection_refused",
]

EDGE_CHAOS_SUPPORTED_FAULT_TYPES: tuple[EdgeChaosFaultType, ...] = (
    "latency",
    "bandwidth",
    "timeout",
    "connection_refused",
)
EDGE_CHAOS_PROXY_HOST: str = "127.0.0.1"
EDGE_CHAOS_DEFAULT_PROXY_PORT: int = 18080
EDGE_CHAOS_PROXY_NAME_PREFIX: str = "toolkit-edge"
EDGE_CHAOS_RUNTIME_BACKEND: str = "container"


@dataclass(slots=True, frozen=True)
class EdgeChaosRuntimeReadiness:
    """Readiness summary for the future managed local edge-chaos runtime."""

    ready: bool
    backend: str | None
    detail: str
    binary: str | None = None


@dataclass(slots=True, frozen=True)
class EdgeChaosProxyPlan:
    """Deterministic local-proxy plan for a future edge-chaos run."""

    app: AppConfig
    fault_type: EdgeChaosFaultType
    proxy_name: str
    requested_url: str
    upstream_origin: str
    proxy_origin: str
    healthcheck_url: str
    proxy_host: str
    proxy_port: int


@dataclass(slots=True, frozen=True)
class EdgeChaosPreparedProxy:
    """Proxy metadata returned by a future managed edge-chaos backend."""

    proxy_name: str
    proxy_origin: str
    upstream_origin: str


@dataclass(slots=True, frozen=True)
class EdgeChaosFaultHandle:
    """Rollback handle returned by a future managed edge-chaos backend."""

    proxy_name: str
    fault_type: EdgeChaosFaultType


class EdgeChaosRuntimeBackend(Protocol):
    """Execution boundary for the future managed local edge-chaos runtime."""

    def prepare_proxy(self, plan: EdgeChaosProxyPlan) -> EdgeChaosPreparedProxy:
        """Start or configure the local proxy for one edge-chaos run."""

    def inject_fault(
        self,
        prepared_proxy: EdgeChaosPreparedProxy,
        *,
        fault_type: EdgeChaosFaultType,
    ) -> EdgeChaosFaultHandle:
        """Inject exactly one reversible fault into the prepared proxy."""

    def rollback_fault(self, handle: EdgeChaosFaultHandle) -> None:
        """Rollback a previously injected edge-chaos fault."""

    def close(self) -> None:
        """Release any runtime resources held by the backend."""


def inspect_edge_chaos_runtime_readiness() -> EdgeChaosRuntimeReadiness:
    """Inspect the current readiness state of the future edge-chaos backend."""

    docker_path = find_binary("docker")
    if docker_path is None:
        return EdgeChaosRuntimeReadiness(
            ready=False,
            backend=None,
            detail=(
                "docker binary was not found on PATH; the managed local "
                "edge-chaos runtime is planned to use Docker."
            ),
        )

    return EdgeChaosRuntimeReadiness(
        ready=False,
        backend=EDGE_CHAOS_RUNTIME_BACKEND,
        binary=str(docker_path),
        detail=(
            "Docker is available, but the managed local edge-chaos runtime "
            "is not implemented yet."
        ),
    )


def build_edge_chaos_proxy_plan(
    url: str,
    *,
    fault_type: EdgeChaosFaultType = "latency",
    proxy_host: str = EDGE_CHAOS_PROXY_HOST,
    proxy_port: int = EDGE_CHAOS_DEFAULT_PROXY_PORT,
) -> EdgeChaosProxyPlan:
    """Build the deterministic local-proxy plan for a future edge-chaos run."""

    if fault_type not in EDGE_CHAOS_SUPPORTED_FAULT_TYPES:
        supported = ", ".join(EDGE_CHAOS_SUPPORTED_FAULT_TYPES)
        raise ValueError(
            f"Unsupported edge-chaos fault type: {fault_type!r}. " f"Supported values: {supported}."
        )
    if not (1 <= proxy_port <= 65535):
        raise ValueError("proxy_port must be between 1 and 65535.")

    app = build_url_edge_chaos_app(url)
    upstream_origin = _origin_from_app(app)
    proxy_origin = f"{app.base_url.scheme}://{proxy_host}:{proxy_port}"

    return EdgeChaosProxyPlan(
        app=app,
        fault_type=fault_type,
        proxy_name=f"{EDGE_CHAOS_PROXY_NAME_PREFIX}-{app.id}",
        requested_url=str(app.base_url),
        upstream_origin=upstream_origin,
        proxy_origin=proxy_origin,
        healthcheck_url=f"{proxy_origin}{app.health_endpoint}",
        proxy_host=proxy_host,
        proxy_port=proxy_port,
    )


def _origin_from_app(app: AppConfig) -> str:
    return f"{app.base_url.scheme}://{app.base_url.host}:{app.base_url.port}"
