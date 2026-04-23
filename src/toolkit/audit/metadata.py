"""Audit metadata artifacts used for report enrichment."""

from __future__ import annotations

import json
from pathlib import Path

from toolkit.audit.intensity import AuditIntensityPlan
from toolkit.auth.session import AuthSession

_SAFE_PROVENANCE_KEYS = frozenset(
    {
        "source",
        "login_url",
        "login_content_type",
        "auth_result",
        "auth_result_path",
        "session_header",
        "token_env_var",
        "cookie_name",
        "cookie_value_env_var",
        "username_env_var",
        "password_env_var",
        "login_username_field",
        "login_password_field",
        "final_url",
        "status_code",
        "cookie_transport",
    }
)


def write_audit_auth_context(raw_dir: Path, auth_session: AuthSession) -> Path:
    """Persist secret-safe auth provenance for one URL-first audit run."""

    path = raw_dir / "audit" / "auth-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "auth_mode": auth_session.method,
        "is_authenticated": auth_session.is_authenticated,
        "provenance": _safe_provenance(auth_session.provenance),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_audit_auth_context(run_dir: Path) -> dict[str, object] | None:
    """Load secret-safe auth provenance when present for one audit run."""

    path = run_dir / "raw" / "audit" / "auth-context.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_provenance(provenance: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in provenance.items()
        if key in _SAFE_PROVENANCE_KEYS and value is not None
    }


def write_audit_intensity_context(
    raw_dir: Path,
    *,
    intensity: str,
    plan: AuditIntensityPlan,
    selected_zap_routes: int,
    selected_nuclei_routes: int,
) -> Path:
    """Persist bounded intensity metadata for one URL-first audit run."""

    path = raw_dir / "audit" / "intensity-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "intensity": intensity,
        "bounded_scope": True,
        "zap_route_limit": plan.zap_route_limit,
        "nuclei_route_limit": plan.nuclei_route_limit,
        "zap_spider_minutes": plan.zap_spider_minutes,
        "nuclei_timeout_seconds": plan.nuclei_timeout_seconds,
        "nmap_profile": plan.nmap_profile,
        "nuclei_allowlist": list(plan.nuclei_allowlist),
        "selected_zap_routes": selected_zap_routes,
        "selected_nuclei_routes": selected_nuclei_routes,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_audit_intensity_context(run_dir: Path) -> dict[str, object] | None:
    """Load persisted intensity metadata when present for one audit run."""

    path = run_dir / "raw" / "audit" / "intensity-context.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
