"""Source-tree code audit command implementation."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from toolkit.auth.errors import AuthRuntimeError
from toolkit.codeaudit.selection import CodeAuditSelectionError, select_code_audit_tools
from toolkit.core.exits import ExitCode
from toolkit.pentest.runner import run_pentest_live_flow
from toolkit.targets import build_source_tree_audit_app, build_source_tree_audit_profile


def register(root_app: typer.Typer) -> None:
    """Register the top-level code-audit command."""

    @root_app.command("code-audit")
    def code_audit(
        path: Annotated[
            Path,
            typer.Argument(help="Local source-tree path for a zero-config code audit run."),
        ],
        tool: Annotated[
            str | None,
            typer.Option(
                "--tool",
                help="Optional code-audit tool to run: semgrep or trivy.",
            ),
        ] = None,
    ) -> None:
        """Run a zero-config source-tree audit with Semgrep and/or Trivy."""

        project_root = Path.cwd()

        try:
            app_config = build_source_tree_audit_app(path)
            code_audit_profile = _profile_for_selected_tools(tool)
            summary = run_pentest_live_flow(
                project_root=project_root,
                app=app_config,
                profile=code_audit_profile,
            )
        except (
            AuthRuntimeError,
            CodeAuditSelectionError,
            FileExistsError,
            FileNotFoundError,
            ValidationError,
            ValueError,
        ) as exc:
            typer.echo("Code audit failed.", err=True)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

        typer.echo("Code audit completed.")
        typer.echo(f"Target path: {path.expanduser().resolve()}")
        typer.echo(f"Run: {summary.run_id}")
        typer.echo(f"Status: {summary.status}")
        typer.echo(f"Findings: {summary.findings_count}")
        typer.echo(f"Actionable findings: {summary.actionable_findings_count}")
        typer.echo(f"Normalized bundle: {summary.normalized_bundle_path}")
        typer.echo(f"Report: {summary.report_path}")
        raise typer.Exit(code=summary.exit_code)


def _profile_for_selected_tools(preferred_tool: str | None):
    """Return the built-in source-tree profile narrowed to the selected tool set."""

    selected_tools = set(select_code_audit_tools(preferred_tool))
    profile = build_source_tree_audit_profile()
    tools = profile.tools

    if "semgrep" not in selected_tools and tools.semgrep is not None:
        tools = tools.model_copy(
            update={"semgrep": tools.semgrep.model_copy(update={"enabled": False})}
        )

    if "trivy" not in selected_tools and tools.trivy is not None:
        tools = tools.model_copy(
            update={"trivy": tools.trivy.model_copy(update={"enabled": False})}
        )

    return profile.model_copy(update={"tools": tools})
