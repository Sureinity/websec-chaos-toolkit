"""URL-first builders for ad hoc pentest targets and profiles."""

from __future__ import annotations

import re

from pydantic import HttpUrl, TypeAdapter

from toolkit.config.models import (
    AppConfig,
    AuthConfig,
    PentestProfile,
    PentestToolsConfig,
    PentestToolSettings,
)

URL_AUDIT_DEFAULT_ENVIRONMENT = "local"
URL_AUDIT_DEFAULT_HEALTH_ENDPOINT = "/"
URL_AUDIT_PROFILE_NAME = "adhoc-safe-web-baseline"

_URL_AUDIT_APP_ID_PREFIX = "adhoc"
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def derive_url_audit_app_id(url: str | HttpUrl) -> str:
    """Return a deterministic app id for a URL-first audit target."""

    resolved_url = _resolve_http_url(url)
    host = resolved_url.host
    slug_input = host.lower()
    if ":" in host:
        slug_input = f"ipv6-{slug_input}"

    slug = _NON_ALNUM_PATTERN.sub("-", slug_input).strip("-") or "target"
    return f"{_URL_AUDIT_APP_ID_PREFIX}-{slug}-{resolved_url.port}"


def build_url_audit_app(url: str | HttpUrl) -> AppConfig:
    """Build a validated AppConfig for a zero-config URL audit run."""

    return _build_url_app(url, enabled_modules=["pentest"])


def build_url_edge_chaos_app(url: str | HttpUrl) -> AppConfig:
    """Build a validated AppConfig for a future URL-first edge-chaos run."""

    return _build_url_app(url, enabled_modules=["chaos"])


def build_url_audit_profile() -> PentestProfile:
    """Build the built-in safe remote-web profile for ad hoc audit runs."""

    return PentestProfile(
        name=URL_AUDIT_PROFILE_NAME,
        assessment_mode="remote_web",
        tools=PentestToolsConfig(
            zap=PentestToolSettings(
                enabled=True,
                safe_mode=True,
                profile="baseline",
                allowlisted_rules=["headers", "tls"],
            ),
            nuclei=PentestToolSettings(
                enabled=True,
                safe_mode=True,
                profile="safe",
                allowlisted_rules=["http/exposures"],
            ),
            nmap=PentestToolSettings(
                enabled=True,
                safe_mode=True,
                profile="top-ports",
                allowlisted_rules=["conservative-tcp"],
            ),
        ),
    )


def _resolve_http_url(url: str | HttpUrl) -> HttpUrl:
    return _HTTP_URL_ADAPTER.validate_python(str(url))


def _build_url_app(url: str | HttpUrl, *, enabled_modules: list[str]) -> AppConfig:
    resolved_url = _resolve_http_url(url)
    host = resolved_url.host

    return AppConfig(
        id=derive_url_audit_app_id(resolved_url),
        environment=URL_AUDIT_DEFAULT_ENVIRONMENT,
        base_url=resolved_url,
        host_targets=[host],
        target_allowlist=[host],
        auth=AuthConfig(method="none"),
        health_endpoint=URL_AUDIT_DEFAULT_HEALTH_ENDPOINT,
        enabled_modules=enabled_modules,
    )
