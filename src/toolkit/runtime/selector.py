"""Runtime auto-selection and readiness checks for URL-first audit flows."""

from __future__ import annotations

from dataclasses import dataclass

from toolkit.adapters.base import AdapterAvailability
from toolkit.runtime.base import RuntimeBackend
from toolkit.runtime.container import ContainerRuntime
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.host import HostRuntime


@dataclass(slots=True, frozen=True)
class AuditRuntimeTool:
    """One audit tool with its logical name and runtime binary identifier."""

    tool: str
    binary: str


@dataclass(slots=True, frozen=True)
class AuditToolReadiness:
    """Availability result for one audit tool under one runtime mode."""

    tool: str
    binary: str
    availability: AdapterAvailability


@dataclass(slots=True, frozen=True)
class AuditRuntimeReadiness:
    """Availability summary for one runtime mode."""

    mode: RuntimeMode
    tool_statuses: tuple[AuditToolReadiness, ...]

    @property
    def ready(self) -> bool:
        return all(status.availability.available for status in self.tool_statuses)

    @property
    def missing_tools(self) -> tuple[str, ...]:
        return tuple(
            status.tool for status in self.tool_statuses if not status.availability.available
        )

    def failure_details(self) -> tuple[str, ...]:
        return tuple(
            (f"{status.tool} ({status.binary}): " f"{status.availability.reason or 'unavailable'}")
            for status in self.tool_statuses
            if not status.availability.available
        )


@dataclass(slots=True, frozen=True)
class AuditRuntimeReport:
    """Combined readiness view for container and host audit execution."""

    container: AuditRuntimeReadiness
    host: AuditRuntimeReadiness

    def for_mode(self, mode: RuntimeMode) -> AuditRuntimeReadiness:
        if mode == RuntimeMode.CONTAINER:
            return self.container
        return self.host

    @property
    def recommended_mode(self) -> RuntimeMode | None:
        if self.container.ready:
            return RuntimeMode.CONTAINER
        if self.host.ready:
            return RuntimeMode.HOST
        return None


@dataclass(slots=True, frozen=True)
class AuditRuntimeSelection:
    """Resolved runtime backend chosen for a URL-first audit run."""

    mode: RuntimeMode
    backend: RuntimeBackend
    readiness: AuditRuntimeReadiness


class RuntimeSelectionError(RuntimeError):
    """Raised when no viable audit runtime is available."""


AUDIT_RUNTIME_TOOLS: tuple[AuditRuntimeTool, ...] = (
    AuditRuntimeTool(tool="zap", binary="zap-baseline.py"),
    AuditRuntimeTool(tool="nuclei", binary="nuclei"),
    AuditRuntimeTool(tool="nmap", binary="nmap"),
)


def build_runtime_backend(mode: RuntimeMode) -> RuntimeBackend:
    """Return the runtime backend instance for the requested mode."""

    if mode == RuntimeMode.CONTAINER:
        return ContainerRuntime()
    return HostRuntime()


def inspect_audit_runtime(mode: RuntimeMode) -> AuditRuntimeReadiness:
    """Check whether one runtime mode can execute the URL-first audit toolset."""

    backend = build_runtime_backend(mode)
    statuses = tuple(
        AuditToolReadiness(
            tool=tool.tool,
            binary=tool.binary,
            availability=backend.check_tool_available(tool.binary),
        )
        for tool in AUDIT_RUNTIME_TOOLS
    )
    return AuditRuntimeReadiness(
        mode=mode,
        tool_statuses=statuses,
    )


def inspect_audit_readiness() -> AuditRuntimeReport:
    """Inspect both supported runtime modes for URL-first audit execution."""

    return AuditRuntimeReport(
        container=inspect_audit_runtime(RuntimeMode.CONTAINER),
        host=inspect_audit_runtime(RuntimeMode.HOST),
    )


def select_audit_runtime(
    preferred_mode: RuntimeMode | None = None,
) -> AuditRuntimeSelection:
    """Choose the runtime backend for a URL-first audit run."""

    report = inspect_audit_readiness()
    if preferred_mode is not None:
        readiness = report.for_mode(preferred_mode)
        if readiness.ready:
            return AuditRuntimeSelection(
                mode=preferred_mode,
                backend=build_runtime_backend(preferred_mode),
                readiness=readiness,
            )
        raise RuntimeSelectionError(
            "Requested audit runtime is not ready for use: "
            f"{preferred_mode.value}. " + "; ".join(readiness.failure_details())
        )

    if report.container.ready:
        return AuditRuntimeSelection(
            mode=RuntimeMode.CONTAINER,
            backend=build_runtime_backend(RuntimeMode.CONTAINER),
            readiness=report.container,
        )
    if report.host.ready:
        return AuditRuntimeSelection(
            mode=RuntimeMode.HOST,
            backend=build_runtime_backend(RuntimeMode.HOST),
            readiness=report.host,
        )

    raise RuntimeSelectionError(
        "No audit runtime is ready. "
        f"Container: {'; '.join(report.container.failure_details())}. "
        f"Host: {'; '.join(report.host.failure_details())}."
    )
