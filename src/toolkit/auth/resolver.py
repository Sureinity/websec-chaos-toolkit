"""Runtime resolution helpers for environment-backed auth modes."""

from dataclasses import dataclass, field
import os
from typing import Literal

from toolkit.auth.errors import (
    BlankSecretValueError,
    MissingEnvironmentVariableError,
    UnsupportedAuthFlowError,
)
from toolkit.config.models import AuthConfig

ResolvedEnvAuthMethod = Literal["bearer_token", "cookie", "session"]


@dataclass(slots=True, frozen=True)
class ResolvedAuthMaterial:
    """Normalized auth material for env-backed injection modes."""

    method: ResolvedEnvAuthMethod
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)


def resolve_supported_env_auth(
    auth_config: AuthConfig,
    *,
    environ: dict[str, str] | None = None,
) -> ResolvedAuthMaterial:
    """Resolve one of the env-backed v1 auth modes into injection material."""

    resolved_environ = os.environ if environ is None else environ

    if auth_config.method == "bearer_token":
        return resolve_bearer_auth(auth_config, environ=resolved_environ)
    if auth_config.method == "cookie":
        return resolve_cookie_auth(auth_config, environ=resolved_environ)
    if auth_config.method == "session":
        return resolve_session_auth(auth_config, environ=resolved_environ)

    raise UnsupportedAuthFlowError(
        method=auth_config.method,
        detail="Only bearer_token, cookie, and session are supported by env-backed auth resolution.",
    )


def resolve_bearer_auth(
    auth_config: AuthConfig,
    *,
    environ: dict[str, str] | None = None,
) -> ResolvedAuthMaterial:
    """Resolve bearer-token auth to a standard authorization header."""

    _ensure_method(auth_config, expected_method="bearer_token")
    resolved_environ = os.environ if environ is None else environ
    token = _resolve_required_env_var(
        auth_config.token_env_var,
        method="bearer_token",
        environ=resolved_environ,
    )

    return ResolvedAuthMaterial(
        method="bearer_token",
        headers={"Authorization": f"Bearer {token}"},
    )


def resolve_cookie_auth(
    auth_config: AuthConfig,
    *,
    environ: dict[str, str] | None = None,
) -> ResolvedAuthMaterial:
    """Resolve cookie auth to a cookie injection mapping."""

    _ensure_method(auth_config, expected_method="cookie")
    resolved_environ = os.environ if environ is None else environ
    cookie_value = _resolve_required_env_var(
        auth_config.cookie_value_env_var,
        method="cookie",
        environ=resolved_environ,
    )

    return ResolvedAuthMaterial(
        method="cookie",
        cookies={auth_config.cookie_name: cookie_value},
    )


def resolve_session_auth(
    auth_config: AuthConfig,
    *,
    environ: dict[str, str] | None = None,
) -> ResolvedAuthMaterial:
    """Resolve session auth to a header injection mapping."""

    _ensure_method(auth_config, expected_method="session")
    resolved_environ = os.environ if environ is None else environ
    session_value = _resolve_required_env_var(
        auth_config.session_value_env_var,
        method="session",
        environ=resolved_environ,
    )

    return ResolvedAuthMaterial(
        method="session",
        headers={auth_config.session_header: session_value},
    )


def _ensure_method(auth_config: AuthConfig, *, expected_method: ResolvedEnvAuthMethod) -> None:
    if auth_config.method != expected_method:
        raise UnsupportedAuthFlowError(
            method=auth_config.method,
            detail=f"Expected auth method {expected_method!r} for this resolver.",
        )


def _resolve_required_env_var(
    env_var: str | None,
    *,
    method: ResolvedEnvAuthMethod,
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
