"""URL-first auth option parsing and validation for toolkit audit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from toolkit.config.models import AuthConfig


class AuditAuthMode(StrEnum):
    """Supported auth modes for URL-first audit."""

    NONE = "none"
    API_LOGIN = "api_login"
    BEARER_TOKEN = "bearer_token"
    COOKIE = "cookie"
    SESSION = "session"
    FORM = "form"


class ApiLoginContentType(StrEnum):
    """Supported login payload content types for api_login."""

    JSON = "json"


class ApiLoginAuthResult(StrEnum):
    """Supported reusable auth material extraction modes for api_login."""

    BEARER_JSON = "bearer_json"
    COOKIE = "cookie"
    SESSION_JSON = "session_json"


class AuditAuthValidationError(RuntimeError):
    """Raised when URL-first audit auth flags are invalid."""


@dataclass(slots=True, frozen=True)
class AuditAuthOptions:
    """All auth-related option values accepted by toolkit audit."""

    auth_mode: AuditAuthMode | None = None
    token_env_var: str | None = None
    cookie_name: str | None = None
    cookie_value_env_var: str | None = None
    session_header: str | None = None
    session_value_env_var: str | None = None
    login_url: str | None = None
    username_env_var: str | None = None
    password_env_var: str | None = None
    login_content_type: ApiLoginContentType | None = None
    login_username_field: str | None = None
    login_password_field: str | None = None
    auth_result: ApiLoginAuthResult | None = None
    auth_result_path: str | None = None


def build_url_audit_auth_config(
    *,
    auth_mode: AuditAuthMode | None = None,
    token_env_var: str | None = None,
    cookie_name: str | None = None,
    cookie_value_env_var: str | None = None,
    session_header: str | None = None,
    session_value_env_var: str | None = None,
    login_url: str | None = None,
    username_env_var: str | None = None,
    password_env_var: str | None = None,
    login_content_type: ApiLoginContentType | None = None,
    login_username_field: str | None = None,
    login_password_field: str | None = None,
    auth_result: ApiLoginAuthResult | None = None,
    auth_result_path: str | None = None,
) -> AuthConfig:
    """Return a validated AuthConfig for URL-first audit CLI inputs."""

    options = AuditAuthOptions(
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
    _validate_auth_options(options)
    return _build_auth_config(options)


def _validate_auth_options(options: AuditAuthOptions) -> None:
    present = {
        "token_env_var": options.token_env_var,
        "cookie_name": options.cookie_name,
        "cookie_value_env_var": options.cookie_value_env_var,
        "session_header": options.session_header,
        "session_value_env_var": options.session_value_env_var,
        "login_url": options.login_url,
        "username_env_var": options.username_env_var,
        "password_env_var": options.password_env_var,
        "login_content_type": options.login_content_type,
        "login_username_field": options.login_username_field,
        "login_password_field": options.login_password_field,
        "auth_result": options.auth_result,
        "auth_result_path": options.auth_result_path,
    }
    provided_flags = {name for name, value in present.items() if value is not None}

    if options.auth_mode is None:
        if provided_flags:
            raise AuditAuthValidationError(
                "Auth-specific flags require --auth-mode. "
                f"Received: {', '.join(sorted(provided_flags))}."
            )
        return

    mode_name = options.auth_mode.value
    allowed: set[str]
    required: set[str]

    if options.auth_mode == AuditAuthMode.NONE:
        allowed = set()
        required = set()
    elif options.auth_mode == AuditAuthMode.BEARER_TOKEN:
        allowed = {"token_env_var"}
        required = {"token_env_var"}
    elif options.auth_mode == AuditAuthMode.COOKIE:
        allowed = {"cookie_name", "cookie_value_env_var"}
        required = {"cookie_name", "cookie_value_env_var"}
    elif options.auth_mode == AuditAuthMode.SESSION:
        allowed = {"session_header", "session_value_env_var"}
        required = {"session_header", "session_value_env_var"}
    elif options.auth_mode == AuditAuthMode.FORM:
        allowed = {
            "login_url",
            "username_env_var",
            "password_env_var",
            "login_username_field",
            "login_password_field",
        }
        required = allowed
    else:
        allowed = {
            "login_url",
            "username_env_var",
            "password_env_var",
            "login_content_type",
            "login_username_field",
            "login_password_field",
            "auth_result",
            "auth_result_path",
            "session_header",
        }
        required = {
            "login_url",
            "username_env_var",
            "password_env_var",
            "login_content_type",
            "login_username_field",
            "login_password_field",
            "auth_result",
        }
        if options.auth_result in {
            ApiLoginAuthResult.BEARER_JSON,
            ApiLoginAuthResult.SESSION_JSON,
        }:
            required.add("auth_result_path")
        if options.auth_result == ApiLoginAuthResult.SESSION_JSON:
            required.add("session_header")

    disallowed = provided_flags - allowed
    if disallowed:
        raise AuditAuthValidationError(
            f"Auth mode {mode_name!r} does not allow: {', '.join(sorted(disallowed))}."
        )

    missing = sorted(required - provided_flags)
    if missing:
        raise AuditAuthValidationError(f"Auth mode {mode_name!r} requires: {', '.join(missing)}.")


def _build_auth_config(options: AuditAuthOptions) -> AuthConfig:
    if options.auth_mode is None or options.auth_mode == AuditAuthMode.NONE:
        return AuthConfig(method="none")

    if options.auth_mode == AuditAuthMode.BEARER_TOKEN:
        return AuthConfig(
            method="bearer_token",
            token_env_var=options.token_env_var,
        )
    if options.auth_mode == AuditAuthMode.COOKIE:
        return AuthConfig(
            method="cookie",
            cookie_name=options.cookie_name,
            cookie_value_env_var=options.cookie_value_env_var,
        )
    if options.auth_mode == AuditAuthMode.SESSION:
        return AuthConfig(
            method="session",
            session_header=options.session_header,
            session_value_env_var=options.session_value_env_var,
        )
    if options.auth_mode == AuditAuthMode.FORM:
        return AuthConfig(
            method="form",
            login_url=options.login_url,
            username_env_var=options.username_env_var,
            password_env_var=options.password_env_var,
            login_username_field=options.login_username_field,
            login_password_field=options.login_password_field,
        )
    return AuthConfig(
        method="api_login",
        login_url=options.login_url,
        username_env_var=options.username_env_var,
        password_env_var=options.password_env_var,
        login_content_type=(
            None if options.login_content_type is None else options.login_content_type.value
        ),
        login_username_field=options.login_username_field,
        login_password_field=options.login_password_field,
        auth_result=None if options.auth_result is None else options.auth_result.value,
        auth_result_path=options.auth_result_path,
        session_header=options.session_header,
    )
