"""Audit intensity planning for URL-first audit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from toolkit.config.models import PentestProfile


class AuditIntensityMode(StrEnum):
    """Operator-selectable breadth and budget level for URL-first audit."""

    SAFE = "safe"
    BALANCED = "balanced"
    DEEP = "deep"


def resolve_audit_intensity(mode: AuditIntensityMode | None) -> AuditIntensityMode:
    """Resolve an omitted audit intensity to the safe default."""

    return AuditIntensityMode.SAFE if mode is None else mode


@dataclass(slots=True, frozen=True)
class AuditIntensityPlan:
    """Locked route and scanner budgets for one audit intensity mode."""

    mode: AuditIntensityMode
    zap_route_limit: int
    nuclei_route_limit: int
    zap_spider_minutes: int
    nuclei_timeout_seconds: float
    nmap_profile: str
    nuclei_allowlist: tuple[str, ...]


_AUDIT_INTENSITY_PLANS = {
    AuditIntensityMode.SAFE: AuditIntensityPlan(
        mode=AuditIntensityMode.SAFE,
        zap_route_limit=8,
        nuclei_route_limit=8,
        zap_spider_minutes=1,
        nuclei_timeout_seconds=300.0,
        nmap_profile="top-ports",
        nuclei_allowlist=("http/exposures",),
    ),
    AuditIntensityMode.BALANCED: AuditIntensityPlan(
        mode=AuditIntensityMode.BALANCED,
        zap_route_limit=12,
        nuclei_route_limit=16,
        zap_spider_minutes=2,
        nuclei_timeout_seconds=450.0,
        nmap_profile="top-ports",
        nuclei_allowlist=("http/exposures",),
    ),
    AuditIntensityMode.DEEP: AuditIntensityPlan(
        mode=AuditIntensityMode.DEEP,
        zap_route_limit=20,
        nuclei_route_limit=32,
        zap_spider_minutes=3,
        nuclei_timeout_seconds=900.0,
        nmap_profile="top-ports",
        nuclei_allowlist=(
            "http/exposures",
            "http/misconfiguration",
            "http/technologies",
        ),
    ),
}


def build_audit_intensity_plan(mode: AuditIntensityMode | None) -> AuditIntensityPlan:
    """Return the locked plan for one audit intensity mode."""

    resolved_mode = resolve_audit_intensity(mode)
    return _AUDIT_INTENSITY_PLANS[resolved_mode]


def apply_audit_intensity(
    profile: PentestProfile,
    *,
    mode: AuditIntensityMode | None,
) -> PentestProfile:
    """Return a profile copy adjusted for the selected audit intensity."""

    plan = build_audit_intensity_plan(mode)
    adjusted = profile.model_copy(deep=True)
    if adjusted.tools.zap is not None:
        adjusted.tools.zap = adjusted.tools.zap.model_copy(update={"profile": plan.mode.value})
    if adjusted.tools.nuclei is not None:
        adjusted.tools.nuclei = adjusted.tools.nuclei.model_copy(
            update={
                "profile": plan.mode.value,
                "allowlisted_rules": list(plan.nuclei_allowlist),
            }
        )
    if adjusted.tools.nmap is not None:
        adjusted.tools.nmap = adjusted.tools.nmap.model_copy(update={"profile": plan.nmap_profile})
    return adjusted
