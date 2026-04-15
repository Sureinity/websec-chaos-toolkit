"""Builders for ad hoc, source-tree-based target configuration."""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

from toolkit.config.models import (
    AppConfig,
    AuthConfig,
    PentestProfile,
    PentestToolsConfig,
    PentestToolSettings,
)

SOURCE_TREE_AUDIT_DEFAULT_ENVIRONMENT = "local"
SOURCE_TREE_AUDIT_DEFAULT_HEALTH_ENDPOINT = "/"
SOURCE_TREE_AUDIT_BASE_URL = "http://localhost"
SOURCE_TREE_AUDIT_PROFILE_NAME = "adhoc-safe-code-audit"
SOURCE_TREE_AUDIT_APP_ID_PREFIX = "adhoc-source-tree"

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def derive_source_tree_audit_app_id(path: str | Path) -> str:
    """Return a deterministic app id for a source-tree audit target."""

    resolved_path = resolve_source_tree_audit_path(path)
    slug_source = resolved_path.name.lower() or "source-tree"
    slug = _NON_ALNUM_PATTERN.sub("-", slug_source).strip("-") or "source-tree"
    short_hash = sha256(str(resolved_path).encode("utf-8")).hexdigest()[:8]
    return f"{SOURCE_TREE_AUDIT_APP_ID_PREFIX}-{slug}-{short_hash}"


def build_source_tree_audit_app(path: str | Path) -> AppConfig:
    """Build a validated AppConfig for a zero-config source-tree audit run."""

    resolved_path = resolve_source_tree_audit_path(path)
    return AppConfig(
        id=derive_source_tree_audit_app_id(resolved_path),
        environment=SOURCE_TREE_AUDIT_DEFAULT_ENVIRONMENT,
        base_url=SOURCE_TREE_AUDIT_BASE_URL,
        host_targets=["localhost"],
        target_allowlist=["localhost"],
        auth=AuthConfig(method="none"),
        health_endpoint=SOURCE_TREE_AUDIT_DEFAULT_HEALTH_ENDPOINT,
        enabled_modules=["pentest"],
    )


def build_source_tree_audit_profile() -> PentestProfile:
    """Build the built-in safe source-tree profile for code audit runs."""

    return PentestProfile(
        name=SOURCE_TREE_AUDIT_PROFILE_NAME,
        assessment_mode="source_tree",
        tools=PentestToolsConfig(
            trivy=PentestToolSettings(
                enabled=True,
                safe_mode=True,
                profile="config-audit",
                allowlisted_rules=["vulnerabilities", "misconfigurations", "secrets"],
            ),
            semgrep=PentestToolSettings(
                enabled=True,
                safe_mode=True,
                profile="default",
                allowlisted_rules=["p/default", "p/secrets"],
            ),
        ),
    )


def resolve_source_tree_audit_path(path: str | Path) -> Path:
    """Resolve and validate a source-tree path for ad hoc code-audit runs."""

    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"source tree path does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"source tree path must be a directory: {resolved}")
    return resolved
