"""Validation command scaffold."""

from typing import Annotated

import typer

from toolkit.core.scaffold import exit_scaffold


def register(root_app: typer.Typer) -> None:
    """Register the top-level validation command."""

    @root_app.command("validate")
    def validate(
        app_id: Annotated[
            str,
            typer.Option("--app", help="Application identifier declared in apps.yaml."),
        ],
        env: Annotated[
            str,
            typer.Option("--env", help="Target environment, typically local or staging."),
        ],
    ) -> None:
        """Validate the configured application and profile files."""

        typer.echo(f"Requested scaffold validation for app={app_id!r} in env={env!r}.")
        exit_scaffold("toolkit validate")
