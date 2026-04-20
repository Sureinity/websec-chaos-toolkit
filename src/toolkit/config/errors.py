"""Structured error helpers for configuration validation."""

from enum import StrEnum

from pydantic_core import PydanticCustomError


class ConfigValidationCode(StrEnum):
    """Stable validation codes for user-facing configuration errors."""

    AUTH_NONE_FORBIDS_SECRET_REFS = "auth_none_forbids_secret_refs"
    AUTH_API_LOGIN_REQUIRES_LOGIN_URL = "auth_api_login_requires_login_url"
    AUTH_API_LOGIN_REQUIRES_USERNAME_ENV_VAR = "auth_api_login_requires_username_env_var"
    AUTH_API_LOGIN_REQUIRES_PASSWORD_ENV_VAR = "auth_api_login_requires_password_env_var"
    AUTH_API_LOGIN_REQUIRES_LOGIN_CONTENT_TYPE = "auth_api_login_requires_login_content_type"
    AUTH_API_LOGIN_REQUIRES_USERNAME_FIELD = "auth_api_login_requires_username_field"
    AUTH_API_LOGIN_REQUIRES_PASSWORD_FIELD = "auth_api_login_requires_password_field"
    AUTH_API_LOGIN_REQUIRES_AUTH_RESULT = "auth_api_login_requires_auth_result"
    AUTH_API_LOGIN_REQUIRES_AUTH_RESULT_PATH = "auth_api_login_requires_auth_result_path"
    AUTH_API_LOGIN_SESSION_JSON_REQUIRES_SESSION_HEADER = (
        "auth_api_login_session_json_requires_session_header"
    )
    AUTH_BEARER_TOKEN_REQUIRES_TOKEN_ENV_VAR = "auth_bearer_token_requires_token_env_var"
    AUTH_COOKIE_REQUIRES_COOKIE_NAME = "auth_cookie_requires_cookie_name"
    AUTH_COOKIE_REQUIRES_COOKIE_VALUE_ENV_VAR = "auth_cookie_requires_cookie_value_env_var"
    AUTH_SESSION_REQUIRES_SESSION_HEADER = "auth_session_requires_session_header"
    AUTH_SESSION_REQUIRES_SESSION_VALUE_ENV_VAR = "auth_session_requires_session_value_env_var"
    AUTH_FORM_REQUIRES_LOGIN_URL = "auth_form_requires_login_url"
    AUTH_FORM_REQUIRES_USERNAME_ENV_VAR = "auth_form_requires_username_env_var"
    AUTH_FORM_REQUIRES_PASSWORD_ENV_VAR = "auth_form_requires_password_env_var"
    EMPTY_STRING_NOT_ALLOWED = "empty_string_not_allowed"
    HEALTH_ENDPOINT_MUST_BE_ABSOLUTE_PATH = "health_endpoint_must_be_absolute_path"
    BASE_URL_HOST_NOT_ALLOWLISTED = "base_url_host_not_allowlisted"
    ENABLED_TOOL_REQUIRES_ALLOWLIST = "enabled_tool_requires_allowlist"
    CONTROLLED_RESTART_NOT_IMPLEMENTED = "controlled_restart_not_implemented"


def config_error(
    code: ConfigValidationCode,
    message: str,
    /,
    **context: object,
) -> PydanticCustomError:
    """Build a stable Pydantic validation error with a repository-owned code."""

    return PydanticCustomError(str(code), message, context)
