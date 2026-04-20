"""URL-first audit command implementation."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from toolkit.audit import (
    ApiLoginAuthResult,
    ApiLoginContentType,
    AuditAuthMode,
    AuditAuthValidationError,
    build_url_audit_auth_config,
)
from toolkit.auth.errors import AuthRuntimeError
from toolkit.core.exits import ExitCode
from toolkit.pentest.runner import run_pentest_live_flow
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.selector import RuntimeSelectionError, select_audit_runtime
from toolkit.targets import build_url_audit_app_with_auth, build_url_audit_profile


def register(root_app: typer.Typer) -> None:
    """Register the top-level URL-first audit command."""

    @root_app.command("audit")
    def audit(
        url: Annotated[
            str,
            typer.Argument(help="Target web URL for a zero-config audit run."),
        ],
        runtime: Annotated[
            RuntimeMode | None,
            typer.Option(
                "--runtime",
                help="Execution backend: container or host. Auto-select when omitted.",
            ),
        ] = None,
        auth_mode: Annotated[
            AuditAuthMode | None,
            typer.Option(
                "--auth-mode",
                help=(
                    "Optional auth mode for URL-first audit: "
                    "none, api_login, bearer_token, cookie, session, or form."
                ),
            ),
        ] = None,
        token_env_var: Annotated[
            str | None,
            typer.Option("--token-env-var", help="Env var name for bearer_token auth."),
        ] = None,
        cookie_name: Annotated[
            str | None,
            typer.Option("--cookie-name", help="Cookie name for cookie auth."),
        ] = None,
        cookie_value_env_var: Annotated[
            str | None,
            typer.Option("--cookie-value-env-var", help="Env var name for cookie auth."),
        ] = None,
        session_header: Annotated[
            str | None,
            typer.Option("--session-header", help="Header name for session or session_json auth."),
        ] = None,
        session_value_env_var: Annotated[
            str | None,
            typer.Option("--session-value-env-var", help="Env var name for session auth."),
        ] = None,
        login_url: Annotated[
            str | None,
            typer.Option("--login-url", help="Login endpoint used by form or api_login auth."),
        ] = None,
        username_env_var: Annotated[
            str | None,
            typer.Option("--username-env-var", help="Env var name for login username."),
        ] = None,
        password_env_var: Annotated[
            str | None,
            typer.Option("--password-env-var", help="Env var name for login password."),
        ] = None,
        login_content_type: Annotated[
            ApiLoginContentType | None,
            typer.Option("--login-content-type", help="Login request content type for api_login."),
        ] = None,
        login_username_field: Annotated[
            str | None,
            typer.Option("--login-username-field", help="Username field name for api_login."),
        ] = None,
        login_password_field: Annotated[
            str | None,
            typer.Option("--login-password-field", help="Password field name for api_login."),
        ] = None,
        auth_result: Annotated[
            ApiLoginAuthResult | None,
            typer.Option(
                "--auth-result",
                help="Reusable auth material to extract for api_login.",
            ),
        ] = None,
        auth_result_path: Annotated[
            str | None,
            typer.Option(
                "--auth-result-path",
                help="JSON path for bearer_json or session_json extraction modes.",
            ),
        ] = None,
    ) -> None:
        """Run a safe URL-first audit without YAML config files."""

        project_root = Path.cwd()

        try:
            auth_config = build_url_audit_auth_config(
                auth_mode=auth_mode,
                token_env_var=token_env_var,
                cookie_name=cookie_name,
                cookie_value_env_var=cookie_value_env_var,
                session_header=session_header,
                session_value_env_var=session_value_env_var,
                login_url=login_url,
                username_env_var=username_env_var,
                password_env_var=password_env_var,
                login_content_type=login_content_type,
                login_username_field=login_username_field,
                login_password_field=login_password_field,
                auth_result=auth_result,
                auth_result_path=auth_result_path,
            )
            app_config = build_url_audit_app_with_auth(url, auth=auth_config)
            audit_profile = build_url_audit_profile()
            selection = select_audit_runtime(preferred_mode=runtime)
            summary = run_pentest_live_flow(
                project_root=project_root,
                app=app_config,
                profile=audit_profile,
                runtime=selection.backend,
            )
        except (
            AuditAuthValidationError,
            AuthRuntimeError,
            FileExistsError,
            FileNotFoundError,
            RuntimeSelectionError,
            ValidationError,
            ValueError,
        ) as exc:
            typer.echo("Audit failed.", err=True)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=ExitCode.CONFIG_OR_RUNTIME_ERROR) from exc

        typer.echo("Audit completed.")
        typer.echo(f"Target: {app_config.base_url}")
        typer.echo(f"Run: {summary.run_id}")
        typer.echo(f"Status: {summary.status}")
        typer.echo(f"Runtime: {selection.mode}")
        typer.echo(f"Findings: {summary.findings_count}")
        typer.echo(f"Actionable findings: {summary.actionable_findings_count}")
        typer.echo(f"Normalized bundle: {summary.normalized_bundle_path}")
        typer.echo(f"Report: {summary.report_path}")
        raise typer.Exit(code=summary.exit_code)
