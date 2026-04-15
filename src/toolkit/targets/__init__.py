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
from toolkit.targets.source_tree import (
    SOURCE_TREE_AUDIT_APP_ID_PREFIX,
    SOURCE_TREE_AUDIT_BASE_URL,
    SOURCE_TREE_AUDIT_DEFAULT_ENVIRONMENT,
    SOURCE_TREE_AUDIT_DEFAULT_HEALTH_ENDPOINT,
    SOURCE_TREE_AUDIT_PROFILE_NAME,
    build_source_tree_audit_app,
    build_source_tree_audit_profile,
    derive_source_tree_audit_app_id,
)

__all__ = [
    "SOURCE_TREE_AUDIT_APP_ID_PREFIX",
    "SOURCE_TREE_AUDIT_BASE_URL",
    "SOURCE_TREE_AUDIT_DEFAULT_ENVIRONMENT",
    "SOURCE_TREE_AUDIT_DEFAULT_HEALTH_ENDPOINT",
    "SOURCE_TREE_AUDIT_PROFILE_NAME",
    "URL_AUDIT_DEFAULT_ENVIRONMENT",
    "URL_AUDIT_DEFAULT_HEALTH_ENDPOINT",
    "URL_AUDIT_PROFILE_NAME",
    "build_source_tree_audit_app",
    "build_source_tree_audit_profile",
    "build_url_audit_app",
    "build_url_edge_chaos_app",
    "build_url_audit_profile",
    "derive_source_tree_audit_app_id",
    "derive_url_audit_app_id",
]
