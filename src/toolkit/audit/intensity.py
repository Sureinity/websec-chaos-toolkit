"""Audit intensity contract helpers for URL-first audit."""

from __future__ import annotations

from enum import StrEnum


class AuditIntensityMode(StrEnum):
    """Operator-selectable breadth and budget level for URL-first audit."""

    SAFE = "safe"
    BALANCED = "balanced"
    DEEP = "deep"


def resolve_audit_intensity(mode: AuditIntensityMode | None) -> AuditIntensityMode:
    """Resolve an omitted audit intensity to the safe default."""

    return AuditIntensityMode.SAFE if mode is None else mode
