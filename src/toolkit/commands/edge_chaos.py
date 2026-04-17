"""URL-first edge-chaos command implementation."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from toolkit.auth.errors import AuthRuntimeError
from toolkit.chaos.contracts import ChaosRunStatus
from toolkit.chaos.edge_runtime import (
    EDGE_CHAOS_RUNTIME_BACKEND,
    EDGE_CHAOS_SUPPORTED_FAULT_TYPES,
    EdgeChaosMonitoringClient,
    EdgeChaosRuntimeError,
    ManagedEdgeChaosDockerRuntime,
    build_edge_chaos_profile,
    build_edge_chaos_proxy_plan,
)
from toolkit.chaos.monitoring import health_check_url
from toolkit.chaos.runner import run_chaos_live_flow
from toolkit.chaos.service import default_fault_attributes
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
        monitoring_client: EdgeChaosMonitoringClient | None = None

        try:
            plan = build_edge_chaos_proxy_plan(url, fault_type=fault)  # type: ignore[arg-type]
            prepared_proxy = runtime.prepare_proxy(plan)
            profile = build_edge_chaos_profile(plan)
            monitoring_client = EdgeChaosMonitoringClient(
                proxy_host=plan.proxy_host,
                proxy_port=plan.proxy_port,
            )
            summary = run_chaos_live_flow(
                project_root=project_root,
                app=plan.app,
                profile=profile,
                monitoring_client=monitoring_client,
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
            if monitoring_client is not None:
                monitoring_client.close()
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

        typer.echo(f"Run: {summary.run_id}")
        typer.echo(f"Target URL: {plan.requested_url}")
        typer.echo(f"Probe URL: {health_check_url(plan.app)}")
        typer.echo(f"Upstream origin: {plan.upstream_origin}")
        typer.echo(f"Proxy URL: {prepared_proxy.proxy_origin}")
        typer.echo(f"Runtime: {EDGE_CHAOS_RUNTIME_BACKEND}")
        typer.echo(f"Probe mode: {_probe_mode(plan.app.metrics is not None)}")
        typer.echo(f"Fault: {plan.fault_type}")
        typer.echo(f"Fault attributes: {_format_fault_attributes(plan.fault_type)}")
        typer.echo(f"Baseline window: {summary.experiment_plan.baseline_duration_seconds}s")
        typer.echo(f"Experiment window: {summary.experiment_plan.experiment_duration_seconds}s")
        typer.echo(
            "Abort threshold: "
            f"{summary.experiment_plan.consecutive_health_failures} consecutive health failures"
        )
        typer.echo(f"Status: {summary.status}")
        typer.echo(f"Result: {_result_summary(summary.status, summary.recovery_verified)}")
        typer.echo(f"Resilience findings: {summary.findings_count}")
        typer.echo(f"Baseline captured: {_format_state(summary.baseline_captured)}")
        typer.echo(f"Rollback attempted: {_format_state(summary.rollback_attempted)}")
        typer.echo(f"Recovery verified: {_format_state(summary.recovery_verified)}")
        if summary.abort_reason is not None:
            typer.echo(f"Abort reason: {summary.abort_reason}")
        typer.echo(f"Normalized bundle: {summary.normalized_bundle_path}")
        typer.echo(f"Report: {summary.report_path}")
        raise typer.Exit(code=summary.exit_code)


def _format_fault_attributes(fault_type: str) -> str:
    attributes = default_fault_attributes(fault_type)  # type: ignore[arg-type]
    if not attributes:
        return "none"

    formatted: list[str] = []
    for key, value in attributes.items():
        if key == "latency_ms":
            formatted.append(f"latency={value}ms")
        elif key == "jitter_ms":
            formatted.append(f"jitter={value}ms")
        elif key == "timeout_ms":
            formatted.append(f"timeout={value}ms")
        elif key == "rate_kbps":
            formatted.append(f"rate={value}kbps")
        elif key == "rate_percent":
            formatted.append(f"rate={value}%")
        else:
            formatted.append(f"{key}={value}")
    return ", ".join(formatted)


def _probe_mode(has_metrics: bool) -> str:
    if has_metrics:
        return "health-and-metrics"
    return "health-only"


def _format_state(value: bool | None) -> str:
    if value is None:
        return "not checked"
    if value:
        return "yes"
    return "no"


def _result_summary(status: ChaosRunStatus, recovery_verified: bool | None) -> str:
    if status == ChaosRunStatus.FAILED:
        return "experiment failed before completion"
    if status == ChaosRunStatus.RESILIENCE_FAILURE:
        if recovery_verified is False:
            return (
                "resilience threshold breached during experiment and "
                "recovery could not be verified"
            )
        if recovery_verified is True:
            return (
                "resilience threshold breached during experiment and "
                "service recovered after rollback"
            )
        return "resilience threshold breached during experiment"
    if recovery_verified is False:
        return "no resilience threshold breach observed, but recovery could not be verified"
    if recovery_verified is True:
        return "no resilience threshold breach observed and service recovered after rollback"
    return "no resilience threshold breach observed"
