"""Source-tree code audit command implementation."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from toolkit.auth.errors import AuthRuntimeError
from toolkit.codeaudit.selection import (
    CodeAuditSelectionError,
    inspect_code_audit_readiness,
    select_code_audit_tools,
)
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
            resolved_path = path.expanduser().resolve()
            readiness = inspect_code_audit_readiness(resolved_path, preferred_tool=tool)
            if not readiness.ready:
                raise RuntimeError(
                    "Code audit tools are not ready: " + "; ".join(readiness.failure_details())
                )
            app_config = build_source_tree_audit_app(resolved_path)
            code_audit_profile = _profile_for_selected_tools(tool)
            target_paths = {
                selected_tool: resolved_path for selected_tool in select_code_audit_tools(tool)
            }
            summary = run_pentest_live_flow(
                project_root=project_root,
                app=app_config,
                profile=code_audit_profile,
                target_paths=target_paths,
            )
        except (
            AuthRuntimeError,
            CodeAuditSelectionError,
            FileExistsError,
            FileNotFoundError,
            RuntimeError,
            ValidationError,
            ValueError,
        ) as exc:
            typer.echo("Code audit failed.", err=True)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

        typer.echo("Code audit completed.")
        typer.echo(f"Target path: {resolved_path}")
        typer.echo(f"Run: {summary.run_id}")
        typer.echo(f"Status: {summary.status}")
        typer.echo(f"Findings: {summary.findings_count}")
        typer.echo(f"Actionable findings: {summary.actionable_findings_count}")
        typer.echo(f"Normalized bundle: {summary.normalized_bundle_path}")
        typer.echo(f"Report: {summary.report_path}")
        raise typer.Exit(code=summary.exit_code)


def _profile_for_selected_tools(preferred_tool: str | None):
    """Return the built-in source-tree profile narrowed to the selected tool set."""

    selected_tools = tuple(select_code_audit_tools(preferred_tool))
    selected_tool_set = set(selected_tools)
    profile = build_source_tree_audit_profile()
    tools = profile.tools

    if "semgrep" not in selected_tool_set and tools.semgrep is not None:
        tools = tools.model_copy(
            update={"semgrep": tools.semgrep.model_copy(update={"enabled": False})}
        )

    if "trivy" not in selected_tool_set and tools.trivy is not None:
        tools = tools.model_copy(
            update={"trivy": tools.trivy.model_copy(update={"enabled": False})}
        )

    profile_name = profile.name
    if len(selected_tools) == 1:
        profile_name = f"{profile_name}-{selected_tools[0]}"

    return profile.model_copy(update={"name": profile_name, "tools": tools})
