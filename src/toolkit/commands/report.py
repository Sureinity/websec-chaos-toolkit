"""Report command implementation."""

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from toolkit.core.exits import ExitCode
from toolkit.core.run_context import outputs_root
from toolkit.reports.builder import (
    normalized_results_bundle_path,
    write_markdown_summary,
)

app = typer.Typer(help="Build reports from normalized results.", no_args_is_help=True)


@app.command("build")
def build(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run identifier used to locate output artifacts."),
    ],
) -> None:
    """Build a report for an existing run."""

    run_dir = outputs_root(Path.cwd()) / run_id
    findings_path = normalized_results_bundle_path(run_dir)

    if not run_dir.is_dir():
        typer.echo("Report build failed.", err=True)
        typer.echo(f"Run directory does not exist: {run_dir}", err=True)
        raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR)

    if not findings_path.is_file():
        typer.echo("Report build failed.", err=True)
        typer.echo(f"Normalized results bundle does not exist: {findings_path}", err=True)
        raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR)

    try:
        summary_path = write_markdown_summary(run_dir)
    except (json.JSONDecodeError, OSError, ValidationError) as exc:
        typer.echo("Report build failed.", err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

    typer.echo("Report generated.")
    typer.echo(f"Run: {run_id}")
    typer.echo(f"Input bundle: {findings_path}")
    typer.echo(f"Summary: {summary_path}")
