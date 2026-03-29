"""Typed runtime authentication errors with safe, redacted messages."""

from collections.abc import Iterable

from toolkit.auth.redaction import redact_known_secrets


class AuthRuntimeError(RuntimeError):
    """Base class for fail-closed runtime authentication errors."""

    def __init__(
        self,
        message: str,
        *,
        method: str | None = None,
        detail: str | None = None,
        secrets: Iterable[str | None] = (),
    ) -> None:
        self.method = method
        self.detail = redact_known_secrets(detail, secrets) if detail is not None else None

        formatted_message = message
        if method is not None:
            formatted_message = f"{formatted_message} [method={method}]"
        if self.detail is not None:
            formatted_message = f"{formatted_message} Detail: {self.detail}"

        super().__init__(formatted_message)


class MissingEnvironmentVariableError(AuthRuntimeError):
    """Raised when a required auth env var is missing."""

    def __init__(self, env_var: str, *, method: str) -> None:
        self.env_var = env_var
        super().__init__(
            f"Missing required environment variable: {env_var}.",
            method=method,
        )


class BlankSecretValueError(AuthRuntimeError):
    """Raised when a resolved auth env var is blank."""

    def __init__(self, env_var: str, *, method: str) -> None:
        self.env_var = env_var
        super().__init__(
            f"Environment variable resolved to a blank secret value: {env_var}.",
            method=method,
        )


class UnsupportedAuthFlowError(AuthRuntimeError):
    """Raised when a configured auth flow is out of scope for v1."""

    def __init__(self, *, method: str, detail: str | None = None) -> None:
        super().__init__(
            "Unsupported authentication flow.",
            method=method,
            detail=detail,
        )


class LoginRequestError(AuthRuntimeError):
    """Raised when a form-login HTTP request fails."""

    def __init__(
        self,
        login_url: str,
        *,
        method: str = "form",
        detail: str | None = None,
        secrets: Iterable[str | None] = (),
    ) -> None:
        self.login_url = login_url
        super().__init__(
            f"Login request failed for {login_url}.",
            method=method,
            detail=detail,
            secrets=secrets,
        )


class MissingSessionMaterialError(AuthRuntimeError):
    """Raised when login completes without reusable auth state."""

    def __init__(
        self,
        *,
        method: str,
        detail: str | None = None,
        secrets: Iterable[str | None] = (),
    ) -> None:
        super().__init__(
            "Authentication flow completed without reusable session material.",
            method=method,
            detail=detail,
            secrets=secrets,
        )
