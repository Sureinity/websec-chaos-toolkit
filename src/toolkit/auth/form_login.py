"""Direct HTTP form-login helpers for username/password auth."""

import os
import re

import httpx

from toolkit.auth.errors import (
    BlankSecretValueError,
    LoginRequestError,
    MissingEnvironmentVariableError,
    MissingSessionMaterialError,
    UnsupportedAuthFlowError,
)
from toolkit.auth.session import AuthSession
from toolkit.config.models import AuthConfig

UNSUPPORTED_LOGIN_MARKERS = ("sso", "mfa", "captcha", "multi-factor")
_WHITESPACE_RE = re.compile(r"\s+")


def perform_form_login(
    auth_config: AuthConfig,
    *,
    environ: dict[str, str] | None = None,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> AuthSession:
    """Resolve credentials from env vars and perform a direct HTTP form login."""

    if auth_config.method != "form":
        raise UnsupportedAuthFlowError(
            method=auth_config.method,
            detail="Expected auth method 'form' for the form-login helper.",
        )

    resolved_environ = os.environ if environ is None else environ
    username = _resolve_required_env_var(
        auth_config.username_env_var,
        method="form",
        environ=resolved_environ,
    )
    password = _resolve_required_env_var(
        auth_config.password_env_var,
        method="form",
        environ=resolved_environ,
    )
    login_url = str(auth_config.login_url)
    secrets = (username, password)

    if client is not None:
        return _perform_login_request(
            client,
            login_url=login_url,
            username=username,
            password=password,
            username_field=auth_config.login_username_field,
            password_field=auth_config.login_password_field,
            username_env_var=auth_config.username_env_var,
            password_env_var=auth_config.password_env_var,
            secrets=secrets,
        )

    with httpx.Client(follow_redirects=True, timeout=timeout) as managed_client:
        return _perform_login_request(
            managed_client,
            login_url=login_url,
            username=username,
            password=password,
            username_field=auth_config.login_username_field,
            password_field=auth_config.login_password_field,
            username_env_var=auth_config.username_env_var,
            password_env_var=auth_config.password_env_var,
            secrets=secrets,
        )


def _perform_login_request(
    client: httpx.Client,
    *,
    login_url: str,
    username: str,
    password: str,
    username_field: str,
    password_field: str,
    username_env_var: str,
    password_env_var: str,
    secrets: tuple[str, ...],
) -> AuthSession:
    try:
        response = client.post(
            login_url,
            data={
                username_field: username,
                password_field: password,
            },
        )
    except httpx.HTTPError as exc:
        raise LoginRequestError(
            login_url,
            detail=str(exc),
            secrets=secrets,
        ) from exc

    response_preview = _preview_text(response.text)
    if _contains_unsupported_flow_marker(response_preview):
        raise UnsupportedAuthFlowError(
            method="form",
            detail=f"Unsupported login flow detected. Response preview: {response_preview}",
        )

    if response.is_error:
        raise LoginRequestError(
            login_url,
            detail=f"HTTP {response.status_code}. Response preview: {response_preview}",
            secrets=secrets,
        )

    cookies = dict(client.cookies.items())
    if not cookies:
        raise MissingSessionMaterialError(
            method="form",
            detail=(
                f"No reusable cookies were returned by {login_url}. "
                f"Response preview: {response_preview}"
            ),
            secrets=secrets,
        )

    return AuthSession(
        method="form",
        cookies=cookies,
        provenance={
            "source": "form_login",
            "login_url": login_url,
            "username_env_var": username_env_var,
            "password_env_var": password_env_var,
            "login_username_field": username_field,
            "login_password_field": password_field,
            "final_url": str(response.url),
            "status_code": str(response.status_code),
        },
    )


def _resolve_required_env_var(
    env_var: str | None,
    *,
    method: str,
    environ: dict[str, str],
) -> str:
    if env_var is None:
        raise MissingEnvironmentVariableError("<unset>", method=method)

    if env_var not in environ:
        raise MissingEnvironmentVariableError(env_var, method=method)

    value = environ[env_var].strip()
    if not value:
        raise BlankSecretValueError(env_var, method=method)

    return value


def _preview_text(value: str, *, limit: int = 200) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", value).strip()
    return collapsed[:limit]


def _contains_unsupported_flow_marker(text: str) -> bool:
    normalized_text = text.lower()
    return any(marker in normalized_text for marker in UNSUPPORTED_LOGIN_MARKERS)
