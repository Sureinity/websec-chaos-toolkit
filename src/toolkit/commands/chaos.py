"""Chaos command scaffold."""

from typing import Annotated

import typer

from toolkit.core.scaffold import exit_scaffold

app = typer.Typer(help="Run chaos workflows.", no_args_is_help=True)


@app.command("run")
def run(
    app_id: Annotated[
        str,
        typer.Option("--app", help="Application identifier declared in apps.yaml."),
    ],
    env: Annotated[
        str,
        typer.Option("--env", help="Target environment, typically local or staging."),
    ],
    profile: Annotated[
        str,
        typer.Option("--profile", help="Chaos profile name."),
    ],
) -> None:
    """Run a single chaos workflow."""

    typer.echo(
        f"Requested scaffold chaos run for app={app_id!r}, env={env!r}, profile={profile!r}."
    )
    exit_scaffold("toolkit chaos run")
