"""Shared runtime auth/session payloads for adapter injection."""

from dataclasses import dataclass, field
from typing import Literal

AuthSessionMethod = Literal["none", "api_login", "bearer_token", "cookie", "session", "form"]


@dataclass(slots=True, frozen=True)
class AuthSession:
    """Normalized runtime auth material shared across supported auth modes."""

    method: AuthSessionMethod
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        """Return whether the session carries active auth material."""

        return self.method != "none"


def unauthenticated_session() -> AuthSession:
    """Return the canonical unauthenticated runtime session payload."""

    return AuthSession(
        method="none",
        provenance={"source": "none"},
    )
