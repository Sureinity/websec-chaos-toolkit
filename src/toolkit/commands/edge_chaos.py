"""URL-first edge-chaos command implementation."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from toolkit.auth.errors import AuthRuntimeError
from toolkit.chaos.contracts import ChaosRunStatus
from toolkit.chaos.edge_runtime import (
    EDGE_CHAOS_SUPPORTED_FAULT_TYPES,
    EdgeChaosRuntimeError,
    ManagedEdgeChaosDockerRuntime,
    build_edge_chaos_monitoring_app,
    build_edge_chaos_profile,
    build_edge_chaos_proxy_plan,
)
from toolkit.chaos.runner import run_chaos_live_flow
from toolkit.core.exits import ExitCode


def register(root_app: typer.Typer) -> None:
    """Register the top-level edge-chaos command."""

    @root_app.command("edge-chaos")
    def edge_chaos(
        url: Annotated[
            str,
            typer.Argument(help="Target web URL for a managed URL-first edge-chaos run."),
        ],
        fault: Annotated[
            str,
            typer.Option(
                "--fault",
                help=(
                    "Safe reversible fault to inject: "
                    + ", ".join(EDGE_CHAOS_SUPPORTED_FAULT_TYPES)
                ),
            ),
        ] = "latency",
    ) -> None:
        """Run one managed edge-chaos experiment against a single URL."""

        project_root = Path.cwd()
        runtime = ManagedEdgeChaosDockerRuntime()

        try:
            plan = build_edge_chaos_proxy_plan(url, fault_type=fault)  # type: ignore[arg-type]
            prepared_proxy = runtime.prepare_proxy(plan)
            app_config = build_edge_chaos_monitoring_app(plan, prepared_proxy)
            profile = build_edge_chaos_profile(plan)
            summary = run_chaos_live_flow(
                project_root=project_root,
                app=app_config,
                profile=profile,
                toxiproxy_base_url=prepared_proxy.toxiproxy_base_url,
            )
        except (
            AuthRuntimeError,
            EdgeChaosRuntimeError,
            FileExistsError,
            FileNotFoundError,
            ValidationError,
            ValueError,
        ) as exc:
            typer.echo("Edge chaos failed.", err=True)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc
        finally:
            try:
                runtime.close()
            except EdgeChaosRuntimeError as exc:
                typer.echo("Edge chaos failed.", err=True)
                typer.echo(str(exc), err=True)
                raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

        if summary.status == ChaosRunStatus.FAILED:
            typer.echo("Edge chaos failed.", err=True)
            if summary.error_detail is not None:
                typer.echo(summary.error_detail, err=True)
        else:
            typer.echo("Edge chaos completed.")

        typer.echo(f"Target: {plan.requested_url}")
        typer.echo(f"Fault: {plan.fault_type}")
        typer.echo(f"Proxy: {prepared_proxy.proxy_origin}")
        typer.echo(f"Run: {summary.run_id}")
        typer.echo(f"Status: {summary.status}")
        typer.echo(f"Findings: {summary.findings_count}")
        typer.echo(f"Baseline captured: {summary.baseline_captured}")
        typer.echo(f"Rollback attempted: {summary.rollback_attempted}")
        if summary.abort_reason is not None:
            typer.echo(f"Abort reason: {summary.abort_reason}")
        typer.echo(f"Normalized bundle: {summary.normalized_bundle_path}")
        typer.echo(f"Report: {summary.report_path}")
        raise typer.Exit(code=summary.exit_code)
