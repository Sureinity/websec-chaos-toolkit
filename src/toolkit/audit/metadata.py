"""Audit metadata artifacts used for report enrichment."""

from __future__ import annotations

import json
from pathlib import Path

from toolkit.auth.session import AuthSession


def write_audit_auth_context(raw_dir: Path, auth_session: AuthSession) -> Path:
    """Persist secret-safe auth provenance for one URL-first audit run."""

    path = raw_dir / "audit" / "auth-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "auth_mode": auth_session.method,
        "is_authenticated": auth_session.is_authenticated,
        "provenance": auth_session.provenance,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_audit_auth_context(run_dir: Path) -> dict[str, object] | None:
    """Load secret-safe auth provenance when present for one audit run."""

    path = run_dir / "raw" / "audit" / "auth-context.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
