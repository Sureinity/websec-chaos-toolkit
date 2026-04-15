"""Environment readiness diagnostics for simplified operator workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from toolkit.chaos.edge_runtime import inspect_edge_chaos_runtime_readiness
from toolkit.codeaudit.selection import (
    CodeAuditReadiness,
    inspect_code_audit_readiness,
    inspect_code_audit_tooling,
)
from toolkit.core.exits import ExitCode
from toolkit.runtime.selector import (
    AuditRuntimeReadiness,
    inspect_audit_readiness,
)


@dataclass(slots=True, frozen=True)
class FeatureReadiness:
    """Readiness summary for a non-runtime operator feature."""

    name: str
    ready: bool
    detail: str


def register(root_app: typer.Typer) -> None:
    """Register the top-level doctor command."""

    @root_app.command("doctor")
    def doctor(
        code_path: Annotated[
            Path | None,
            typer.Option(
                "--code-path",
                help="Optional local source-tree path to validate for code-audit readiness.",
            ),
        ] = None,
        code_tool: Annotated[
            str | None,
            typer.Option(
                "--code-tool",
                help="Optional code-audit tool to inspect: semgrep or trivy.",
            ),
        ] = None,
    ) -> None:
        """Report environment readiness for simplified audit workflows."""

        try:
            audit_report = inspect_audit_readiness()
            edge_chaos = inspect_edge_chaos_readiness()
            code_audit = (
                inspect_code_audit_readiness(code_path, preferred_tool=code_tool)
                if code_path is not None
                else inspect_code_audit_tooling(preferred_tool=code_tool)
            )
        except RuntimeError as exc:
            typer.echo("Toolkit readiness check failed.", err=True)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

        typer.echo("Toolkit readiness")
        typer.echo("")
        _emit_runtime_readiness(audit_report.container)
        _emit_runtime_readiness(audit_report.host)
        typer.echo("")

        recommended_mode = audit_report.recommended_mode
        if recommended_mode is None:
            typer.echo("Recommended audit runtime: unavailable")
        else:
            typer.echo(f"Recommended audit runtime: {recommended_mode.value}")

        typer.echo("")
        typer.echo(f"Edge chaos: {'ready' if edge_chaos.ready else 'not ready'}")
        typer.echo(f"  - {edge_chaos.detail}")
        typer.echo("")
        _emit_code_audit_readiness(code_audit)


def inspect_edge_chaos_readiness() -> FeatureReadiness:
    """Return the current readiness state for the URL-first edge-chaos path."""

    runtime = inspect_edge_chaos_runtime_readiness()
    return FeatureReadiness(
        name="edge-chaos",
        ready=runtime.ready,
        detail=runtime.detail,
    )


def _emit_runtime_readiness(readiness: AuditRuntimeReadiness) -> None:
    typer.echo(
        f"Audit runtime ({readiness.mode.value}): " f"{'ready' if readiness.ready else 'not ready'}"
    )
    for status in readiness.tool_statuses:
        if status.availability.available:
            location = status.availability.binary or status.binary
            typer.echo(f"  - {status.tool}: ready via {location}")
            continue
        typer.echo(f"  - {status.tool}: " f"{status.availability.reason or 'unavailable'}")


def _emit_code_audit_readiness(readiness: CodeAuditReadiness) -> None:
    label = "Code audit path" if readiness.path_checked else "Code audit tools"
    typer.echo(f"{label}: {'ready' if readiness.ready else 'not ready'}")
    typer.echo(f"  - selected tools: {', '.join(readiness.selected_tools)}")
    for status in readiness.tool_statuses:
        if status.availability.available:
            location = status.availability.binary or status.binary
            typer.echo(f"  - {status.tool}: ready via {location}")
            continue
        typer.echo(f"  - {status.tool}: " f"{status.availability.reason or 'unavailable'}")

    if not readiness.path_checked:
        typer.echo("  - path: not checked")
        return

    if readiness.path_ready and readiness.resolved_path is not None:
        typer.echo(f"  - path: ready ({readiness.resolved_path})")
        return

    typer.echo(f"  - path: {readiness.path_detail or 'unavailable'}")
