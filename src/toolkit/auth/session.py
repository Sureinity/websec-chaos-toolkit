"""Shared runtime auth/session payloads for adapter injection."""

from dataclasses import dataclass, field
from http.cookiejar import Cookie, CookieJar
from typing import Literal

AuthSessionMethod = Literal["none", "api_login", "bearer_token", "cookie", "session", "form"]


@dataclass(slots=True, frozen=True)
class AuthSession:
    """Normalized runtime auth material shared across supported auth modes."""

    method: AuthSessionMethod
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    cookie_header: str | None = None
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


def resolve_cookie_header(auth_session: AuthSession | None) -> str | None:
    """Return the effective Cookie header value for one auth session."""

    if auth_session is None:
        return None
    if auth_session.cookie_header:
        return auth_session.cookie_header
    if not auth_session.cookies:
        return None
    return "; ".join(f"{name}={value}" for name, value in auth_session.cookies.items())


def extract_cookie_material(cookie_jar: CookieJar) -> tuple[dict[str, str], str | None]:
    """Extract reusable cookie material without failing on duplicate names.

    `httpx` raises `CookieConflict` when duplicate cookie names exist across
    different paths or domains and the jar is accessed like a simple mapping.
    Preserve those sessions by falling back to a raw Cookie header when names
    are not unique.
    """

    entries = _sorted_cookie_entries(cookie_jar)
    if not entries:
        return {}, None

    duplicate_names = len({cookie.name for cookie in entries}) != len(entries)
    if duplicate_names:
        return {}, "; ".join(f"{cookie.name}={cookie.value}" for cookie in entries)

    return ({cookie.name: cookie.value for cookie in entries}, None)


def _sorted_cookie_entries(cookie_jar: CookieJar) -> tuple[Cookie, ...]:
    return tuple(
        sorted(
            cookie_jar,
            key=lambda cookie: (
                cookie.domain or "",
                -(len(cookie.path or "/")),
                cookie.path or "/",
                cookie.name,
                cookie.value,
            ),
        )
    )
