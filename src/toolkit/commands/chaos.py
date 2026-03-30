"""Chaos command implementation."""

from pathlib import Path
from typing import Annotated

import typer

from toolkit.auth.errors import AuthRuntimeError
from toolkit.chaos.runner import run_chaos_fixture_flow
from toolkit.chaos.service import default_fixture_paths
from toolkit.config.loader import ConfigLoadError, load_bootstrap_config
from toolkit.core.exits import ExitCode

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

    project_root = Path.cwd()

    try:
        bundle = load_bootstrap_config(
            project_root,
            app_id=app_id,
            environment=env,
        )
        app_config = bundle.require_app(app_id=app_id, environment=env)
        chaos_profile = bundle.find_chaos_profile(profile)
        if chaos_profile is None:
            raise ConfigLoadError(
                f"Requested chaos profile not found: {profile!r}.",
                path=project_root / "chaos-profiles.yaml",
                section="selection",
            )

        summary = run_chaos_fixture_flow(
            project_root=project_root,
            app=app_config,
            profile=chaos_profile,
            fixture_paths=default_fixture_paths(project_root, profile_name=chaos_profile.name),
        )
    except (
        AuthRuntimeError,
        ConfigLoadError,
        FileExistsError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        typer.echo("Chaos run failed.", err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

    if summary.status == "failed":
        typer.echo("Chaos run failed.", err=True)
        if summary.error_detail is not None:
            typer.echo(summary.error_detail, err=True)
    else:
        typer.echo("Chaos run completed.")

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
