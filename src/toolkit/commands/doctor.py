"""Environment readiness diagnostics for simplified operator workflows."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from toolkit.chaos.edge_runtime import inspect_edge_chaos_runtime_readiness
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
    def doctor() -> None:
        """Report environment readiness for simplified audit workflows."""

        try:
            audit_report = inspect_audit_readiness()
            edge_chaos = inspect_edge_chaos_readiness()
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
