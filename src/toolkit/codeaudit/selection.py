"""Tool selection and readiness inspection for the code-audit path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from toolkit.adapters.base import AdapterAvailability
from toolkit.codeaudit.contracts import CODE_AUDIT_DEFAULT_TOOLS, CodeAuditToolName
from toolkit.runtime.base import RuntimeBackend
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.selector import build_runtime_backend
from toolkit.targets import resolve_source_tree_audit_path

CODE_AUDIT_TOOL_BINARIES: dict[CodeAuditToolName, str] = {
    "semgrep": "semgrep",
    "trivy": "trivy",
}


class CodeAuditSelectionError(RuntimeError):
    """Raised when code-audit selection input is invalid."""


@dataclass(slots=True, frozen=True)
class CodeAuditToolReadiness:
    """Availability result for one selected code-audit tool."""

    tool: CodeAuditToolName
    binary: str
    availability: AdapterAvailability


@dataclass(slots=True, frozen=True)
class CodeAuditReadiness:
    """Combined tool and optional path readiness for code-audit execution."""

    selected_tools: tuple[CodeAuditToolName, ...]
    tool_statuses: tuple[CodeAuditToolReadiness, ...]
    path_checked: bool
    resolved_path: Path | None = None
    path_detail: str | None = None

    @property
    def tools_ready(self) -> bool:
        return all(status.availability.available for status in self.tool_statuses)

    @property
    def path_ready(self) -> bool:
        return self.resolved_path is not None

    @property
    def ready(self) -> bool:
        if self.path_checked:
            return self.tools_ready and self.path_ready
        return self.tools_ready

    def failure_details(self) -> tuple[str, ...]:
        """Return human-readable readiness failures for the selected path and tools."""

        details: list[str] = []
        if self.path_checked and not self.path_ready and self.path_detail is not None:
            details.append(f"path: {self.path_detail}")
        details.extend(
            (f"{status.tool} ({status.binary}): " f"{status.availability.reason or 'unavailable'}")
            for status in self.tool_statuses
            if not status.availability.available
        )
        return tuple(details)


def select_code_audit_tools(
    preferred_tool: str | None = None,
) -> tuple[CodeAuditToolName, ...]:
    """Return the selected code-audit tools in deterministic execution order."""

    if preferred_tool is None:
        return CODE_AUDIT_DEFAULT_TOOLS

    normalized = preferred_tool.strip().lower()
    if normalized not in CODE_AUDIT_TOOL_BINARIES:
        supported = ", ".join(CODE_AUDIT_DEFAULT_TOOLS)
        raise CodeAuditSelectionError(
            f"Unsupported code-audit tool: {preferred_tool!r}. " f"Supported values: {supported}."
        )
    return (normalized,)  # type: ignore[return-value]


def inspect_code_audit_tooling(
    preferred_tool: str | None = None,
) -> CodeAuditReadiness:
    """Inspect the selected code-audit tools without validating a path."""

    selected_tools = select_code_audit_tools(preferred_tool)
    return CodeAuditReadiness(
        selected_tools=selected_tools,
        tool_statuses=_tool_statuses(
            selected_tools,
            backend=build_runtime_backend(RuntimeMode.HOST),
        ),
        path_checked=False,
    )


def inspect_code_audit_readiness(
    path: str | Path,
    *,
    preferred_tool: str | None = None,
) -> CodeAuditReadiness:
    """Inspect both tool availability and the selected source-tree path."""

    selected_tools = select_code_audit_tools(preferred_tool)
    try:
        resolved_path = resolve_source_tree_audit_path(path)
        path_detail = str(resolved_path)
    except ValueError as exc:
        return CodeAuditReadiness(
            selected_tools=selected_tools,
            tool_statuses=_tool_statuses(
                selected_tools,
                backend=build_runtime_backend(RuntimeMode.HOST),
            ),
            path_checked=True,
            resolved_path=None,
            path_detail=str(exc),
        )

    return CodeAuditReadiness(
        selected_tools=selected_tools,
        tool_statuses=_tool_statuses(
            selected_tools,
            backend=build_runtime_backend(RuntimeMode.HOST),
        ),
        path_checked=True,
        resolved_path=resolved_path,
        path_detail=path_detail,
    )


@dataclass(slots=True, frozen=True)
class CodeAuditRuntimeReadiness:
    """Availability summary for one runtime mode under the code-audit flow."""

    mode: RuntimeMode
    selected_tools: tuple[CodeAuditToolName, ...]
    tool_statuses: tuple[CodeAuditToolReadiness, ...]
    path_checked: bool
    resolved_path: Path | None = None
    path_detail: str | None = None

    @property
    def tools_ready(self) -> bool:
        return all(status.availability.available for status in self.tool_statuses)

    @property
    def path_ready(self) -> bool:
        return self.resolved_path is not None

    @property
    def ready(self) -> bool:
        if self.path_checked:
            return self.tools_ready and self.path_ready
        return self.tools_ready

    def failure_details(self) -> tuple[str, ...]:
        details: list[str] = []
        if self.path_checked and not self.path_ready and self.path_detail is not None:
            details.append(f"path: {self.path_detail}")
        details.extend(
            (f"{status.tool} ({status.binary}): " f"{status.availability.reason or 'unavailable'}")
            for status in self.tool_statuses
            if not status.availability.available
        )
        return tuple(details)


@dataclass(slots=True, frozen=True)
class CodeAuditRuntimeReport:
    """Combined host/container readiness for the selected code-audit tools."""

    host: CodeAuditRuntimeReadiness
    container: CodeAuditRuntimeReadiness

    def for_mode(self, mode: RuntimeMode) -> CodeAuditRuntimeReadiness:
        if mode == RuntimeMode.CONTAINER:
            return self.container
        return self.host

    @property
    def recommended_mode(self) -> RuntimeMode | None:
        if self.host.ready:
            return RuntimeMode.HOST
        if self.container.ready:
            return RuntimeMode.CONTAINER
        return None


@dataclass(slots=True, frozen=True)
class CodeAuditRuntimeSelection:
    """Resolved runtime backend chosen for a code-audit run."""

    mode: RuntimeMode
    backend: RuntimeBackend
    readiness: CodeAuditRuntimeReadiness


def inspect_code_audit_runtime(
    mode: RuntimeMode,
    *,
    preferred_tool: str | None = None,
    path: str | Path | None = None,
) -> CodeAuditRuntimeReadiness:
    """Inspect one runtime mode for the selected code-audit toolset."""

    selected_tools = select_code_audit_tools(preferred_tool)
    backend = build_runtime_backend(mode)
    if path is None:
        resolved_path: Path | None = None
        path_detail: str | None = None
        path_checked = False
    else:
        path_checked = True
        try:
            resolved_path = resolve_source_tree_audit_path(path)
            path_detail = str(resolved_path)
        except ValueError as exc:
            resolved_path = None
            path_detail = str(exc)

    return CodeAuditRuntimeReadiness(
        mode=mode,
        selected_tools=selected_tools,
        tool_statuses=_tool_statuses(selected_tools, backend=backend),
        path_checked=path_checked,
        resolved_path=resolved_path,
        path_detail=path_detail,
    )


def inspect_code_audit_runtime_report(
    *,
    preferred_tool: str | None = None,
    path: str | Path | None = None,
) -> CodeAuditRuntimeReport:
    """Inspect both host and container runtime modes for code-audit execution."""

    return CodeAuditRuntimeReport(
        host=inspect_code_audit_runtime(
            RuntimeMode.HOST,
            preferred_tool=preferred_tool,
            path=path,
        ),
        container=inspect_code_audit_runtime(
            RuntimeMode.CONTAINER,
            preferred_tool=preferred_tool,
            path=path,
        ),
    )


def select_code_audit_runtime(
    path: str | Path,
    *,
    preferred_tool: str | None = None,
    preferred_mode: RuntimeMode | None = None,
) -> CodeAuditRuntimeSelection:
    """Choose the runtime backend for a code-audit run."""

    report = inspect_code_audit_runtime_report(
        preferred_tool=preferred_tool,
        path=path,
    )

    if preferred_mode is not None:
        readiness = report.for_mode(preferred_mode)
        if readiness.ready:
            return CodeAuditRuntimeSelection(
                mode=preferred_mode,
                backend=build_runtime_backend(preferred_mode),
                readiness=readiness,
            )
        raise CodeAuditSelectionError(
            "Requested code-audit runtime is not ready for use: "
            f"{preferred_mode.value}. " + "; ".join(readiness.failure_details())
        )

    recommended_mode = report.recommended_mode
    if recommended_mode is None:
        raise CodeAuditSelectionError(
            "No code-audit runtime is ready. "
            f"Host: {'; '.join(report.host.failure_details())}. "
            f"Container: {'; '.join(report.container.failure_details())}."
        )

    return CodeAuditRuntimeSelection(
        mode=recommended_mode,
        backend=build_runtime_backend(recommended_mode),
        readiness=report.for_mode(recommended_mode),
    )


def _tool_statuses(
    selected_tools: tuple[CodeAuditToolName, ...],
    *,
    backend: RuntimeBackend,
) -> tuple[CodeAuditToolReadiness, ...]:
    return tuple(
        CodeAuditToolReadiness(
            tool=tool,
            binary=CODE_AUDIT_TOOL_BINARIES[tool],
            availability=backend.check_tool_available(CODE_AUDIT_TOOL_BINARIES[tool]),
        )
        for tool in selected_tools
    )
