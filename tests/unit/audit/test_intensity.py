import unittest

from toolkit.audit.intensity import (
    AuditIntensityMode,
    apply_audit_intensity,
    build_audit_intensity_plan,
    resolve_audit_intensity,
)
from toolkit.targets import build_url_audit_profile


class AuditIntensityContractTests(unittest.TestCase):
    def test_omitted_intensity_defaults_to_safe(self) -> None:
        self.assertEqual(resolve_audit_intensity(None), AuditIntensityMode.SAFE)

    def test_explicit_intensity_modes_are_preserved(self) -> None:
        self.assertEqual(
            resolve_audit_intensity(AuditIntensityMode.SAFE),
            AuditIntensityMode.SAFE,
        )
        self.assertEqual(
            resolve_audit_intensity(AuditIntensityMode.BALANCED),
            AuditIntensityMode.BALANCED,
        )
        self.assertEqual(
            resolve_audit_intensity(AuditIntensityMode.DEEP),
            AuditIntensityMode.DEEP,
        )

    def test_intensity_enum_exposes_locked_values(self) -> None:
        self.assertEqual(
            tuple(mode.value for mode in AuditIntensityMode),
            ("safe", "balanced", "deep"),
        )

    def test_safe_plan_matches_locked_default_values(self) -> None:
        plan = build_audit_intensity_plan(AuditIntensityMode.SAFE)

        self.assertEqual(plan.zap_route_limit, 8)
        self.assertEqual(plan.nuclei_route_limit, 8)
        self.assertEqual(plan.zap_spider_minutes, 1)
        self.assertEqual(plan.nuclei_timeout_seconds, 300.0)
        self.assertEqual(plan.nmap_profile, "top-ports")
        self.assertEqual(plan.nuclei_allowlist, ("http/exposures",))

    def test_balanced_plan_matches_locked_values(self) -> None:
        plan = build_audit_intensity_plan(AuditIntensityMode.BALANCED)

        self.assertEqual(plan.zap_route_limit, 12)
        self.assertEqual(plan.nuclei_route_limit, 16)
        self.assertEqual(plan.zap_spider_minutes, 2)
        self.assertEqual(plan.nuclei_timeout_seconds, 450.0)
        self.assertEqual(plan.nmap_profile, "top-ports")
        self.assertEqual(plan.nuclei_allowlist, ("http/exposures",))

    def test_deep_plan_matches_locked_values(self) -> None:
        plan = build_audit_intensity_plan(AuditIntensityMode.DEEP)

        self.assertEqual(plan.zap_route_limit, 20)
        self.assertEqual(plan.nuclei_route_limit, 32)
        self.assertEqual(plan.zap_spider_minutes, 3)
        self.assertEqual(plan.nuclei_timeout_seconds, 900.0)
        self.assertEqual(plan.nmap_profile, "top-ports")
        self.assertEqual(
            plan.nuclei_allowlist,
            (
                "http/exposures",
                "http/misconfiguration",
                "http/technologies",
            ),
        )

    def test_default_to_safe_equivalence_extends_to_planning(self) -> None:
        self.assertEqual(
            build_audit_intensity_plan(None),
            build_audit_intensity_plan(AuditIntensityMode.SAFE),
        )

    def test_apply_audit_intensity_updates_profile_for_selected_mode(self) -> None:
        profile = build_url_audit_profile()
        adjusted = apply_audit_intensity(profile, mode=AuditIntensityMode.DEEP)

        self.assertEqual(adjusted.tools.zap.profile, "deep")
        self.assertEqual(adjusted.tools.nuclei.profile, "deep")
        self.assertEqual(
            adjusted.tools.nuclei.allowlisted_rules,
            ["http/exposures", "http/misconfiguration", "http/technologies"],
        )
        self.assertEqual(adjusted.tools.nmap.profile, "top-ports")

    def test_apply_audit_intensity_defaults_to_safe_profile_equivalence(self) -> None:
        profile = build_url_audit_profile()
        implicit = apply_audit_intensity(profile, mode=None)
        explicit = apply_audit_intensity(profile, mode=AuditIntensityMode.SAFE)

        self.assertEqual(implicit.model_dump(), explicit.model_dump())
