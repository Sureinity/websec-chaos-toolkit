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
    AuditDiscoveryError,
    AuditFingerprintError,
    AuditIntensityMode,
    apply_audit_intensity,
    build_audit_intensity_plan,
    build_url_audit_auth_config,
    capture_httpx_fingerprint,
    plan_discovered_audit_scope,
    resolve_audit_intensity,
    run_katana_discovery,
    write_audit_auth_context,
    write_httpx_fingerprint,
)
from toolkit.auth.bootstrap import resolve_auth_session
from toolkit.auth.errors import AuthRuntimeError
from toolkit.core.exits import ExitCode
from toolkit.core.logging import runtime_logging_scope
from toolkit.core.run_context import RunRequest, prepare_run_context, utc_now
from toolkit.pentest.contracts import PentestRunStatus, PentestRunSummary
from toolkit.pentest.runner import run_pentest_live_flow
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.selector import RuntimeSelectionError, select_audit_runtime
from toolkit.targets import build_url_audit_app_with_auth, build_url_audit_profile

_GENERAL_AUDIT_PANEL = "General Audit Options"
_AUTH_MODE_SELECTION_PANEL = "Auth Mode Selection"
_AUTH_BEARER_PANEL = "Auth Mode: bearer_token"
_AUTH_COOKIE_PANEL = "Auth Mode: cookie"
_AUTH_SESSION_PANEL = "Auth Mode: session"
_AUTH_SHARED_LOGIN_PANEL = "Auth Modes: form and api_login"
_AUTH_API_LOGIN_PANEL = "Auth Mode: api_login"


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
                rich_help_panel=_GENERAL_AUDIT_PANEL,
            ),
        ] = None,
        verbose: Annotated[
            int,
            typer.Option(
                "--verbose",
                "-v",
                count=True,
                help="Increase runtime log verbosity (-v, -vv, -vvv).",
                rich_help_panel=_GENERAL_AUDIT_PANEL,
            ),
        ] = 0,
        intensity: Annotated[
            AuditIntensityMode | None,
            typer.Option(
                "--intensity",
                help=(
                    "Audit breadth and budget mode: safe, balanced, or deep. "
                    "Omitted behaves like safe."
                ),
                rich_help_panel=_GENERAL_AUDIT_PANEL,
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
                rich_help_panel=_AUTH_MODE_SELECTION_PANEL,
            ),
        ] = None,
        token_env_var: Annotated[
            str | None,
            typer.Option(
                "--token-env-var",
                help="Required for bearer_token. Env var name that holds the bearer token.",
                rich_help_panel=_AUTH_BEARER_PANEL,
            ),
        ] = None,
        cookie_name: Annotated[
            str | None,
            typer.Option(
                "--cookie-name",
                help="Required for cookie. Cookie name to inject into requests.",
                rich_help_panel=_AUTH_COOKIE_PANEL,
            ),
        ] = None,
        cookie_value_env_var: Annotated[
            str | None,
            typer.Option(
                "--cookie-value-env-var",
                help="Required for cookie. Env var name that holds the cookie value.",
                rich_help_panel=_AUTH_COOKIE_PANEL,
            ),
        ] = None,
        session_header: Annotated[
            str | None,
            typer.Option(
                "--session-header",
                help=(
                    "Required for session. Also required for api_login when "
                    "--auth-result is session_json."
                ),
                rich_help_panel=_AUTH_SESSION_PANEL,
            ),
        ] = None,
        session_value_env_var: Annotated[
            str | None,
            typer.Option(
                "--session-value-env-var",
                help="Required for session. Env var name that holds the session header value.",
                rich_help_panel=_AUTH_SESSION_PANEL,
            ),
        ] = None,
        login_url: Annotated[
            str | None,
            typer.Option(
                "--login-url",
                help="Required for form and api_login. Login endpoint to submit credentials to.",
                rich_help_panel=_AUTH_SHARED_LOGIN_PANEL,
            ),
        ] = None,
        username_env_var: Annotated[
            str | None,
            typer.Option(
                "--username-env-var",
                help="Required for form and api_login. Env var name that holds the login username.",
                rich_help_panel=_AUTH_SHARED_LOGIN_PANEL,
            ),
        ] = None,
        password_env_var: Annotated[
            str | None,
            typer.Option(
                "--password-env-var",
                help="Required for form and api_login. Env var name that holds the login password.",
                rich_help_panel=_AUTH_SHARED_LOGIN_PANEL,
            ),
        ] = None,
        login_content_type: Annotated[
            ApiLoginContentType | None,
            typer.Option(
                "--login-content-type",
                help="Required for api_login. Login request content type.",
                rich_help_panel=_AUTH_API_LOGIN_PANEL,
            ),
        ] = None,
        login_username_field: Annotated[
            str | None,
            typer.Option(
                "--login-username-field",
                help=(
                    "Required for form and api_login. Username field name in the "
                    "submitted form body or JSON payload."
                ),
                rich_help_panel=_AUTH_SHARED_LOGIN_PANEL,
            ),
        ] = None,
        login_password_field: Annotated[
            str | None,
            typer.Option(
                "--login-password-field",
                help=(
                    "Required for form and api_login. Password field name in the "
                    "submitted form body or JSON payload."
                ),
                rich_help_panel=_AUTH_SHARED_LOGIN_PANEL,
            ),
        ] = None,
        auth_result: Annotated[
            ApiLoginAuthResult | None,
            typer.Option(
                "--auth-result",
                help=(
                    "Required for api_login. Reusable auth material to extract "
                    "from the login response."
                ),
                rich_help_panel=_AUTH_API_LOGIN_PANEL,
            ),
        ] = None,
        auth_result_path: Annotated[
            str | None,
            typer.Option(
                "--auth-result-path",
                help=(
                    "Required for api_login when bearer_json or session_json is "
                    "selected. JSON path to the reusable auth value."
                ),
                rich_help_panel=_AUTH_API_LOGIN_PANEL,
            ),
        ] = None,
    ) -> None:
        """Run a safe URL-first audit without YAML config files."""

        project_root = Path.cwd()

        with runtime_logging_scope(verbosity=verbose):
            try:
                selected_intensity = resolve_audit_intensity(intensity)
                intensity_plan = build_audit_intensity_plan(selected_intensity)
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
                audit_profile = apply_audit_intensity(
                    build_url_audit_profile(),
                    mode=selected_intensity,
                )
                resolved_when = utc_now()
                context = prepare_run_context(
                    project_root,
                    RunRequest(
                        app_id=app_config.id,
                        environment=app_config.environment,
                        profile=audit_profile.name,
                        modules=("pentest",),
                    ),
                    when=resolved_when,
                )
                fingerprint = capture_httpx_fingerprint(str(app_config.base_url))
                fingerprint_path = write_httpx_fingerprint(context.raw_dir, fingerprint)
                selection = select_audit_runtime(preferred_mode=runtime)
                auth_session = resolve_auth_session(app_config)
                auth_context_path = write_audit_auth_context(context.raw_dir, auth_session)
                discovery = run_katana_discovery(
                    seed_url=str(app_config.base_url),
                    raw_dir=context.raw_dir,
                    runtime=selection.backend,
                    auth_session=auth_session,
                )
                target_scope = plan_discovered_audit_scope(
                    seed_url=str(app_config.base_url),
                    discovered_routes=discovery.routes,
                    zap_route_limit=intensity_plan.zap_route_limit,
                    nuclei_route_limit=intensity_plan.nuclei_route_limit,
                )
                summary = run_pentest_live_flow(
                    project_root=project_root,
                    app=app_config,
                    profile=audit_profile,
                    when=resolved_when,
                    runtime=selection.backend,
                    context=context,
                    extra_raw_artifact_paths=(
                        fingerprint_path,
                        auth_context_path,
                        discovery.raw_output_path,
                        discovery.route_manifest_path,
                    ),
                    auth_session=auth_session,
                    target_urls={
                        "zap": target_scope.zap_routes,
                        "nuclei": target_scope.nuclei_routes,
                    },
                )
            except (
                AuditDiscoveryError,
                AuditFingerprintError,
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

        if summary.status == PentestRunStatus.FAILED:
            typer.echo("Audit failed.", err=True)
            for detail in _failed_tool_details(summary):
                typer.echo(f"Tool failure: {detail}", err=True)
        else:
            typer.echo("Audit completed.")
        typer.echo(f"Target: {app_config.base_url}")
        typer.echo(f"Run: {summary.run_id}")
        typer.echo(f"Status: {summary.status}")
        typer.echo(f"Runtime: {selection.mode}")
        typer.echo(f"Auth mode: {auth_session.method}")
        typer.echo(f"Auth source: {auth_session.provenance.get('source', 'n/a')}")
        typer.echo(f"Fingerprint final URL: {fingerprint.final_url}")
        typer.echo(f"Fingerprint title: {fingerprint.title or 'n/a'}")
        typer.echo(f"Fingerprint server: {fingerprint.server or 'n/a'}")
        typer.echo(f"Discovery routes: {len(discovery.routes)}")
        typer.echo(f"Findings: {summary.findings_count}")
        typer.echo(f"Actionable findings: {summary.actionable_findings_count}")
        typer.echo(f"Normalized bundle: {summary.normalized_bundle_path}")
        typer.echo(f"Report: {summary.report_path}")
        raise typer.Exit(code=summary.exit_code)


def _failed_tool_details(summary: PentestRunSummary) -> tuple[str, ...]:
    return tuple(
        f"{result.tool}: {result.error_detail}"
        for result in summary.adapter_results
        if result.failed and result.error_detail is not None
    )
