"""URL-first audit command implementation."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from toolkit.auth.errors import AuthRuntimeError
from toolkit.core.exits import ExitCode
from toolkit.pentest.runner import run_pentest_live_flow
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.selector import RuntimeSelectionError, select_audit_runtime
from toolkit.targets import build_url_audit_app, build_url_audit_profile


def register(root_app: typer.Typer) -> None:
    """Register the top-level URL-first audit command."""

    @root_app.command("audit")
    def audit(
        url: Annotated[
            str,
            typer.Argument(help="Target web URL for a zero-config audit run."),
        ],
        runtime: Annotated[
            RuntimeMode | None,
            typer.Option(
                "--runtime",
                help="Execution backend: container or host. Auto-select when omitted.",
            ),
        ] = None,
    ) -> None:
        """Run a safe URL-first audit without YAML config files."""

        project_root = Path.cwd()

        try:
            app_config = build_url_audit_app(url)
            audit_profile = build_url_audit_profile()
            selection = select_audit_runtime(preferred_mode=runtime)
            summary = run_pentest_live_flow(
                project_root=project_root,
                app=app_config,
                profile=audit_profile,
                runtime=selection.backend,
            )
        except (
            AuthRuntimeError,
            FileExistsError,
            FileNotFoundError,
            RuntimeSelectionError,
            ValidationError,
            ValueError,
        ) as exc:
            typer.echo("Audit failed.", err=True)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

        typer.echo("Audit completed.")
        typer.echo(f"Target: {app_config.base_url}")
        typer.echo(f"Run: {summary.run_id}")
        typer.echo(f"Status: {summary.status}")
        typer.echo(f"Runtime: {selection.mode}")
        typer.echo(f"Findings: {summary.findings_count}")
        typer.echo(f"Actionable findings: {summary.actionable_findings_count}")
        typer.echo(f"Normalized bundle: {summary.normalized_bundle_path}")
        typer.echo(f"Report: {summary.report_path}")
        raise typer.Exit(code=summary.exit_code)
