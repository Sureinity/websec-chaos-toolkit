"""High-level auth bootstrap helpers for validated app configs."""

from collections.abc import Mapping

import httpx

from toolkit.auth.api_login import perform_api_login
from toolkit.auth.form_login import perform_form_login
from toolkit.auth.resolver import resolve_supported_env_auth
from toolkit.auth.session import AuthSession, unauthenticated_session
from toolkit.config.models import AppConfig


def resolve_auth_session(
    app_config: AppConfig,
    *,
    environ: Mapping[str, str] | None = None,
    client: httpx.Client | None = None,
) -> AuthSession:
    """Resolve the validated app auth config into the shared runtime session payload."""

    auth_config = app_config.auth

    if auth_config.method == "none":
        return unauthenticated_session()

    if auth_config.method in {"bearer_token", "cookie", "session"}:
        return resolve_supported_env_auth(
            auth_config,
            environ=dict(environ) if environ is not None else None,
        )

    if auth_config.method == "api_login":
        return perform_api_login(
            auth_config,
            environ=dict(environ) if environ is not None else None,
            client=client,
        )

    return perform_form_login(
        auth_config,
        environ=dict(environ) if environ is not None else None,
        client=client,
    )
