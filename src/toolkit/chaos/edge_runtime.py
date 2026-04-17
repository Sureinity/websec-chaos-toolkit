"""Planning and execution helpers for the URL-first edge-chaos path."""

from __future__ import annotations

import subprocess
import tempfile
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from toolkit.adapters.process import find_binary
from toolkit.chaos.service import default_fault_attributes
from toolkit.chaos.toxiproxy import (
    TOXIPROXY_DEFAULT_BASE_URL,
    ToxiproxyClient,
    ToxiproxyFaultHandle,
    ToxiproxyProxyNotFoundError,
)
from toolkit.config.models import (
    AbortThresholds,
    AppConfig,
    ChaosProfile,
    RollbackConfig,
)
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
EDGE_CHAOS_TOXIPROXY_IMAGE: str = "ghcr.io/shopify/toxiproxy:latest"
EDGE_CHAOS_CONTAINER_NAME_PREFIX: str = "toolkit-edge-chaos"
EDGE_CHAOS_DEFAULT_BASELINE_SECONDS: int = 5
EDGE_CHAOS_DEFAULT_EXPERIMENT_SECONDS: int = 10
EDGE_CHAOS_DEFAULT_CONSECUTIVE_FAILURES: int = 2
EDGE_CHAOS_PROFILE_NAME_PREFIX: str = "adhoc-edge"


@dataclass(slots=True, frozen=True)
class EdgeChaosRuntimeError(RuntimeError):
    """Raised when the managed edge-chaos runtime cannot be started safely."""

    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(slots=True, frozen=True)
class EdgeChaosRuntimeReadiness:
    """Readiness summary for the managed local edge-chaos runtime."""

    ready: bool
    backend: str | None
    detail: str
    binary: str | None = None


@dataclass(slots=True, frozen=True)
class EdgeChaosProxyPlan:
    """Deterministic local-proxy plan for one edge-chaos run."""

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
    """Proxy metadata returned by the managed edge-chaos backend."""

    proxy_name: str
    proxy_origin: str
    upstream_origin: str
    toxiproxy_base_url: str


@dataclass(slots=True, frozen=True)
class EdgeChaosFaultHandle:
    """Rollback handle returned by the managed edge-chaos backend."""

    proxy_name: str
    fault_type: EdgeChaosFaultType
    toxiproxy_handle: ToxiproxyFaultHandle


class EdgeChaosRuntimeBackend(Protocol):
    """Execution boundary for the managed local edge-chaos runtime."""

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
    """Inspect the current readiness state of the managed edge-chaos backend."""

    docker_path = find_binary("docker")
    if docker_path is None:
        return EdgeChaosRuntimeReadiness(
            ready=False,
            backend=None,
            detail=(
                "docker binary was not found on PATH; the managed local "
                "edge-chaos runtime requires Docker."
            ),
        )

    return EdgeChaosRuntimeReadiness(
        ready=True,
        backend=EDGE_CHAOS_RUNTIME_BACKEND,
        binary=str(docker_path),
        detail="Docker-backed managed local edge-chaos runtime is ready.",
    )


def build_edge_chaos_proxy_plan(
    url: str,
    *,
    fault_type: EdgeChaosFaultType = "latency",
    proxy_host: str = EDGE_CHAOS_PROXY_HOST,
    proxy_port: int = EDGE_CHAOS_DEFAULT_PROXY_PORT,
) -> EdgeChaosProxyPlan:
    """Build the deterministic local-proxy plan for one edge-chaos run."""

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
        requested_url=_probe_url_from_app(app),
        upstream_origin=upstream_origin,
        proxy_origin=proxy_origin,
        healthcheck_url=f"{proxy_origin}{app.health_endpoint}",
        proxy_host=proxy_host,
        proxy_port=proxy_port,
    )


def build_edge_chaos_monitoring_app(
    plan: EdgeChaosProxyPlan,
    prepared_proxy: EdgeChaosPreparedProxy,
) -> AppConfig:
    """Build the runtime-facing AppConfig that is monitored through the proxy."""

    parsed_proxy = urlsplit(prepared_proxy.proxy_origin)
    return AppConfig.model_validate(
        {
            "id": plan.app.id,
            "environment": plan.app.environment,
            "base_url": prepared_proxy.proxy_origin,
            "host_targets": [parsed_proxy.hostname],
            "target_allowlist": [parsed_proxy.hostname],
            "auth": {"method": "none"},
            "health_endpoint": plan.app.health_endpoint,
            "enabled_modules": ["chaos"],
        }
    )


def build_edge_chaos_profile(
    plan: EdgeChaosProxyPlan,
    *,
    baseline_duration_seconds: int = EDGE_CHAOS_DEFAULT_BASELINE_SECONDS,
    experiment_duration_seconds: int = EDGE_CHAOS_DEFAULT_EXPERIMENT_SECONDS,
) -> ChaosProfile:
    """Build the built-in chaos profile for URL-first edge-chaos runs."""

    return ChaosProfile(
        name=f"{EDGE_CHAOS_PROFILE_NAME_PREFIX}-{plan.fault_type}",
        fault_type=plan.fault_type,
        target_service=plan.proxy_name,
        baseline_duration_seconds=baseline_duration_seconds,
        experiment_duration_seconds=experiment_duration_seconds,
        abort_thresholds=AbortThresholds(
            consecutive_health_failures=EDGE_CHAOS_DEFAULT_CONSECUTIVE_FAILURES
        ),
        rollback=RollbackConfig(
            method="managed_edge_proxy_reset",
            description="Remove injected toxics and clean up the managed edge proxy.",
        ),
    )


class ManagedEdgeChaosDockerRuntime:
    """Manage a temporary host-networked Toxiproxy container for one run."""

    def __init__(
        self,
        *,
        toxiproxy_base_url: str = TOXIPROXY_DEFAULT_BASE_URL,
        container_image: str = EDGE_CHAOS_TOXIPROXY_IMAGE,
        startup_timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.25,
        client: ToxiproxyClient | None = None,
    ) -> None:
        self.toxiproxy_base_url = toxiproxy_base_url.rstrip("/")
        self.container_image = container_image
        self.startup_timeout_seconds = startup_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._client = client or ToxiproxyClient(base_url=self.toxiproxy_base_url)
        self._owns_client = client is None
        self._container_name: str | None = None
        self._prepared_proxy: EdgeChaosPreparedProxy | None = None

    def prepare_proxy(self, plan: EdgeChaosProxyPlan) -> EdgeChaosPreparedProxy:
        """Start the managed Toxiproxy container and create one proxy."""

        docker_path = find_binary("docker")
        if docker_path is None:
            raise EdgeChaosRuntimeError(
                "docker binary was not found on PATH; edge-chaos requires Docker."
            )

        self._container_name = f"{EDGE_CHAOS_CONTAINER_NAME_PREFIX}-{uuid.uuid4().hex[:8]}"
        _run_docker_command(
            docker_path,
            "run",
            "-d",
            "--rm",
            "--name",
            self._container_name,
            "--network",
            "host",
            self.container_image,
        )
        wait_for_toxiproxy_api(
            self.toxiproxy_base_url,
            timeout_seconds=self.startup_timeout_seconds,
            interval_seconds=self.poll_interval_seconds,
        )

        proxy = self._client.create_proxy(
            proxy_name=plan.proxy_name,
            listen=f"{plan.proxy_host}:{plan.proxy_port}",
            upstream=_upstream_from_origin(plan.upstream_origin),
        )
        prepared = EdgeChaosPreparedProxy(
            proxy_name=proxy.name,
            proxy_origin=f"{plan.app.base_url.scheme}://{proxy.listen}",
            upstream_origin=plan.upstream_origin,
            toxiproxy_base_url=self.toxiproxy_base_url,
        )
        self._prepared_proxy = prepared
        return prepared

    def inject_fault(
        self,
        prepared_proxy: EdgeChaosPreparedProxy,
        *,
        fault_type: EdgeChaosFaultType,
    ) -> EdgeChaosFaultHandle:
        """Inject one reversible fault through the managed proxy."""

        handle = self._client.inject_fault(
            proxy_name=prepared_proxy.proxy_name,
            fault_type=fault_type,
            attributes=default_fault_attributes(fault_type),
        )
        return EdgeChaosFaultHandle(
            proxy_name=prepared_proxy.proxy_name,
            fault_type=fault_type,
            toxiproxy_handle=handle,
        )

    def rollback_fault(self, handle: EdgeChaosFaultHandle) -> None:
        """Rollback one previously injected edge-chaos fault."""

        self._client.rollback_fault(handle.toxiproxy_handle)

    def close(self) -> None:
        """Delete the managed proxy and stop the temporary Toxiproxy container."""

        cleanup_errors: list[str] = []

        if self._prepared_proxy is not None:
            try:
                self._client.delete_proxy(self._prepared_proxy.proxy_name)
            except ToxiproxyProxyNotFoundError:
                pass
            except RuntimeError as exc:
                cleanup_errors.append(str(exc))
            finally:
                self._prepared_proxy = None

        if self._container_name is not None:
            docker_path = find_binary("docker")
            if docker_path is None:
                cleanup_errors.append(
                    "docker binary disappeared before the managed edge-chaos "
                    "runtime could be stopped."
                )
            else:
                try:
                    _run_docker_command(docker_path, "stop", self._container_name)
                except EdgeChaosRuntimeError as exc:
                    cleanup_errors.append(str(exc))
            self._container_name = None

        if self._owns_client:
            self._client.close()

        if cleanup_errors:
            raise EdgeChaosRuntimeError("; ".join(cleanup_errors))


def wait_for_toxiproxy_api(
    base_url: str,
    *,
    timeout_seconds: float,
    interval_seconds: float,
) -> None:
    """Wait until the managed Toxiproxy admin API starts responding."""

    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() <= deadline:
            try:
                response = client.get(f"{base_url}/version")
                if response.status_code == httpx.codes.OK:
                    return
                last_error = f"HTTP {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(interval_seconds)

    detail = last_error or "timed out waiting for Toxiproxy to start"
    raise EdgeChaosRuntimeError(f"Managed edge-chaos runtime did not become ready: {detail}")


def _origin_from_app(app: AppConfig) -> str:
    return f"{app.base_url.scheme}://{app.base_url.host}:{app.base_url.port}"


def _probe_url_from_app(app: AppConfig) -> str:
    return f"{str(app.base_url).rstrip('/')}{app.health_endpoint}"


class EdgeChaosMonitoringClient:
    """HTTP client that preserves the target hostname while connecting to the proxy."""

    def __init__(
        self,
        *,
        proxy_host: str,
        proxy_port: int,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.timeout_seconds = timeout_seconds

    def close(self) -> None:
        """Provide parity with httpx.Client for callers that close managed clients."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Fetch one URL through the managed proxy while preserving Host and SNI."""

        request_url = _url_with_params(url, params=params)
        parsed = urlsplit(request_url)
        request = httpx.Request("GET", request_url, headers=headers)

        if parsed.hostname is None:
            raise httpx.ConnectError(
                "URL hostname is required for edge-chaos monitoring", request=request
            )

        connect_to_rule = (
            f"{parsed.hostname}:{parsed.port or _default_port_for_scheme(parsed.scheme)}:"
            f"{self.proxy_host}:{self.proxy_port}"
        )
        command: list[str] = [
            "curl",
            "--silent",
            "--show-error",
            "--location",
            "--max-time",
            str(int(self.timeout_seconds)),
            "--output",
        ]

        with tempfile.TemporaryDirectory(prefix="toolkit-edge-chaos-") as temp_dir_name:
            body_path = Path(temp_dir_name) / "response-body.txt"
            command.extend(
                [
                    str(body_path),
                    "--write-out",
                    "%{http_code}",
                    "--connect-to",
                    connect_to_rule,
                ]
            )
            for key, value in (headers or {}).items():
                command.extend(["-H", f"{key}: {value}"])
            command.append(request_url)

            completed = subprocess.run(
                tuple(command),
                capture_output=True,
                text=True,
                check=False,
            )

            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise httpx.ConnectError(
                    detail or "curl connect-to request failed", request=request
                )

            status_code = int((completed.stdout or "0").strip())
            body = body_path.read_text(encoding="utf-8", errors="replace")

        return httpx.Response(status_code=status_code, text=body, request=request)


def _upstream_from_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    if parsed.hostname is None or parsed.port is None:
        raise EdgeChaosRuntimeError(f"Invalid upstream origin for edge-chaos: {origin!r}")
    return f"{parsed.hostname}:{parsed.port}"


def _run_docker_command(docker_path: Path, *args: str) -> None:
    completed = subprocess.run(
        (str(docker_path), *args),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return

    detail = completed.stderr.strip() or completed.stdout.strip()
    raise EdgeChaosRuntimeError(
        f"docker {' '.join(args)} failed with exit code {completed.returncode}: {detail}"
    )


def _default_port_for_scheme(scheme: str) -> int:
    if scheme == "https":
        return 443
    return 80


def _url_with_params(
    url: str,
    *,
    params: Mapping[str, str] | None,
) -> str:
    if not params:
        return url

    parsed = urlsplit(url)
    query = urlencode(params)
    if parsed.query:
        query = f"{parsed.query}&{query}"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
