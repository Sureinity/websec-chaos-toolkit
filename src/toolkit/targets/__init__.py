"""Builders for ad hoc, URL-derived target configuration."""

from toolkit.targets.adhoc import (
    URL_AUDIT_DEFAULT_ENVIRONMENT,
    URL_AUDIT_DEFAULT_HEALTH_ENDPOINT,
    URL_AUDIT_PROFILE_NAME,
    build_url_audit_app,
    build_url_audit_profile,
    build_url_edge_chaos_app,
    derive_url_audit_app_id,
)

__all__ = [
    "URL_AUDIT_DEFAULT_ENVIRONMENT",
    "URL_AUDIT_DEFAULT_HEALTH_ENDPOINT",
    "URL_AUDIT_PROFILE_NAME",
    "build_url_audit_app",
    "build_url_edge_chaos_app",
    "build_url_audit_profile",
    "derive_url_audit_app_id",
]
