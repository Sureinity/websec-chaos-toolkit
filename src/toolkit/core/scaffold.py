"""Utilities for scaffold-only commands."""

from typing import Final

import typer

from toolkit.core.exits import ExitCode

SCAFFOLD_MESSAGE: Final[str] = (
    "This command is wired into the bootstrap scaffold, but orchestration, "
    "tool adapters, and reporting flow are not implemented yet."
)


def exit_scaffold(command_path: str) -> None:
    """Exit with the contract runtime-error code for scaffold-only commands."""

    typer.echo(f"{command_path} is available as a scaffold only.")
    typer.echo(SCAFFOLD_MESSAGE)
    raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR)
