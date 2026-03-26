"""Report command scaffold."""

from typing import Annotated

import typer

from toolkit.core.scaffold import exit_scaffold

app = typer.Typer(help="Build reports from normalized results.", no_args_is_help=True)


@app.command("build")
def build(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run identifier used to locate output artifacts."),
    ],
) -> None:
    """Build a report for an existing run."""

    typer.echo(f"Requested scaffold report build for run_id={run_id!r}.")
    exit_scaffold("toolkit report build")
