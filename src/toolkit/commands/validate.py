"""Validation command implementation."""

from pathlib import Path
from typing import Annotated

import typer

from toolkit.config.loader import ConfigLoadError, load_bootstrap_config
from toolkit.core.exits import ExitCode


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

        try:
            bundle = load_bootstrap_config(
                Path.cwd(),
                app_id=app_id,
                environment=env,
            )
            app = bundle.require_app(app_id=app_id, environment=env)
        except ConfigLoadError as exc:
            typer.echo("Configuration validation failed.", err=True)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

        typer.echo("Configuration is valid.")
        typer.echo(f"App: {app.id}")
        typer.echo(f"Environment: {app.environment}")
        typer.echo(f"Enabled modules: {', '.join(app.enabled_modules)}")
        typer.echo(f"Pentest profiles: {len(bundle.pentest_profiles.profiles)}")
        typer.echo(f"Chaos profiles: {len(bundle.chaos_profiles.profiles)}")
