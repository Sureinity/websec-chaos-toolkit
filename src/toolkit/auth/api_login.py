"""Direct API-login helpers for JSON-based authentication flows."""

from __future__ import annotations

import os

import httpx

from toolkit.auth.errors import (
    BlankSecretValueError,
    LoginRequestError,
    MissingEnvironmentVariableError,
    MissingSessionMaterialError,
    UnsupportedAuthFlowError,
)
from toolkit.auth.session import AuthSession, extract_cookie_material
from toolkit.config.models import AuthConfig


def perform_api_login(
    auth_config: AuthConfig,
    *,
    environ: dict[str, str] | None = None,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> AuthSession:
    """Resolve credentials from env vars and perform a JSON API login."""

    if auth_config.method != "api_login":
        raise UnsupportedAuthFlowError(
            method=auth_config.method,
            detail="Expected auth method 'api_login' for the API-login helper.",
        )

    resolved_environ = os.environ if environ is None else environ
    username = _resolve_required_env_var(
        auth_config.username_env_var,
        method="api_login",
        environ=resolved_environ,
    )
    password = _resolve_required_env_var(
        auth_config.password_env_var,
        method="api_login",
        environ=resolved_environ,
    )
    secrets = (username, password)

    if auth_config.login_content_type != "json":
        raise UnsupportedAuthFlowError(
            method="api_login",
            detail=f"Unsupported login content type: {auth_config.login_content_type!r}.",
        )

    if client is not None:
        return _perform_login_request(
            client,
            auth_config=auth_config,
            username=username,
            password=password,
            secrets=secrets,
        )

    with httpx.Client(follow_redirects=True, timeout=timeout) as managed_client:
        return _perform_login_request(
            managed_client,
            auth_config=auth_config,
            username=username,
            password=password,
            secrets=secrets,
        )


def _perform_login_request(
    client: httpx.Client,
    *,
    auth_config: AuthConfig,
    username: str,
    password: str,
    secrets: tuple[str, ...],
) -> AuthSession:
    login_url = str(auth_config.login_url)

    try:
        response = client.post(
            login_url,
            json={
                auth_config.login_username_field: username,
                auth_config.login_password_field: password,
            },
        )
    except httpx.HTTPError as exc:
        raise LoginRequestError(
            login_url,
            method="api_login",
            detail=str(exc),
            secrets=secrets,
        ) from exc

    if response.is_error:
        raise LoginRequestError(
            login_url,
            method="api_login",
            detail=f"HTTP {response.status_code}.",
            secrets=secrets,
        )

    if auth_config.auth_result == "cookie":
        cookies, cookie_header = extract_cookie_material(client.cookies.jar)
        if not cookies:
            if cookie_header is not None:
                return AuthSession(
                    method="api_login",
                    headers={"Cookie": cookie_header},
                    cookie_header=cookie_header,
                    provenance=_provenance(
                        auth_config,
                        response,
                        cookie_transport="header",
                    ),
                )
            raise MissingSessionMaterialError(
                method="api_login",
                detail="Login response did not produce reusable cookies.",
                secrets=secrets,
            )
        return AuthSession(
            method="api_login",
            cookies=cookies,
            provenance=_provenance(auth_config, response, cookie_transport="mapping"),
        )

    payload = _parse_json_response(response, secrets=secrets)
    extracted_value = _extract_json_path(
        payload,
        path=auth_config.auth_result_path,
        secrets=secrets,
    )

    if auth_config.auth_result == "bearer_json":
        return AuthSession(
            method="api_login",
            headers={"Authorization": f"Bearer {extracted_value}"},
            provenance=_provenance(auth_config, response),
        )

    if auth_config.auth_result == "session_json":
        return AuthSession(
            method="api_login",
            headers={auth_config.session_header: extracted_value},
            provenance=_provenance(auth_config, response),
        )

    raise UnsupportedAuthFlowError(
        method="api_login",
        detail=f"Unsupported auth result mode: {auth_config.auth_result!r}.",
    )


def _parse_json_response(
    response: httpx.Response,
    *,
    secrets: tuple[str, ...],
) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise MissingSessionMaterialError(
            method="api_login",
            detail="Login response could not be parsed as JSON.",
            secrets=secrets,
        ) from exc


def _extract_json_path(
    payload: object,
    *,
    path: str | None,
    secrets: tuple[str, ...],
) -> str:
    if path is None:
        raise MissingSessionMaterialError(
            method="api_login",
            detail="Login response path for reusable auth material was not provided.",
            secrets=secrets,
        )

    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise MissingSessionMaterialError(
            method="api_login",
            detail=f"Login response did not contain reusable auth material at path {path!r}.",
            secrets=secrets,
        )

    if isinstance(current, str):
        value = current.strip()
    else:
        value = str(current).strip()

    if not value:
        raise MissingSessionMaterialError(
            method="api_login",
            detail=f"Login response produced blank auth material at path {path!r}.",
            secrets=secrets,
        )
    return value


def _provenance(
    auth_config: AuthConfig,
    response: httpx.Response,
    *,
    cookie_transport: str | None = None,
) -> dict[str, str]:
    provenance = {
        "source": "api_login",
        "login_url": str(auth_config.login_url),
        "username_env_var": auth_config.username_env_var,
        "password_env_var": auth_config.password_env_var,
        "login_content_type": auth_config.login_content_type,
        "auth_result": auth_config.auth_result,
        "final_url": str(response.url),
        "status_code": str(response.status_code),
    }
    if auth_config.auth_result_path is not None:
        provenance["auth_result_path"] = auth_config.auth_result_path
    if auth_config.session_header is not None:
        provenance["session_header"] = auth_config.session_header
    if cookie_transport is not None:
        provenance["cookie_transport"] = cookie_transport
    return provenance


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
