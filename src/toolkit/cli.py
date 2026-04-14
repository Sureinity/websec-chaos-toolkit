"""Typer application bootstrap."""

from typing import Annotated

import typer

from toolkit import __version__
from toolkit.commands.audit import register as register_audit
from toolkit.commands.chaos import app as chaos_app
from toolkit.commands.doctor import register as register_doctor
from toolkit.commands.pentest import app as pentest_app
from toolkit.commands.report import app as report_app
from toolkit.commands.validate import register as register_validate

app = typer.Typer(
    help="Safe internal testing toolkit scaffold.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the package version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Expose the top-level CLI namespace."""


register_audit(app)
register_validate(app)
register_doctor(app)
app.add_typer(pentest_app, name="pentest")
app.add_typer(chaos_app, name="chaos")
app.add_typer(report_app, name="report")
