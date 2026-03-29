"""Direct HTTP form-login helpers for username/password auth."""

from dataclasses import dataclass, field
import os
import re
from typing import Literal

import httpx

from toolkit.auth.errors import (
    BlankSecretValueError,
    LoginRequestError,
    MissingEnvironmentVariableError,
    MissingSessionMaterialError,
    UnsupportedAuthFlowError,
)
from toolkit.config.models import AuthConfig

UNSUPPORTED_LOGIN_MARKERS = ("sso", "mfa", "captcha", "multi-factor")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True, frozen=True)
class FormLoginSession:
    """Reusable authenticated session material produced by a login flow."""

    method: Literal["form"]
    cookies: dict[str, str]
    headers: dict[str, str] = field(default_factory=dict)
    final_url: str | None = None
    status_code: int | None = None


def perform_form_login(
    auth_config: AuthConfig,
    *,
    environ: dict[str, str] | None = None,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> FormLoginSession:
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
            secrets=secrets,
        )

    with httpx.Client(follow_redirects=True, timeout=timeout) as managed_client:
        return _perform_login_request(
            managed_client,
            login_url=login_url,
            username=username,
            password=password,
            secrets=secrets,
        )


def _perform_login_request(
    client: httpx.Client,
    *,
    login_url: str,
    username: str,
    password: str,
    secrets: tuple[str, ...],
) -> FormLoginSession:
    try:
        response = client.post(
            login_url,
            data={
                "username": username,
                "password": password,
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
            detail=f"No reusable cookies were returned by {login_url}. Response preview: {response_preview}",
            secrets=secrets,
        )

    return FormLoginSession(
        method="form",
        cookies=cookies,
        final_url=str(response.url),
        status_code=response.status_code,
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
