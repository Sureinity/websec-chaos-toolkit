import unittest

from toolkit.audit.intensity import AuditIntensityMode, resolve_audit_intensity


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
