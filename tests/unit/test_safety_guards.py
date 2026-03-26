import unittest

from toolkit.safety.guards import (
    refuse_production_like_environment,
    require_explicit_allowlist,
)


class SafetyGuardTests(unittest.TestCase):
    def test_allowlist_must_not_be_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlist"):
            require_explicit_allowlist([], "target")

    def test_production_like_environment_is_refused_by_default(self) -> None:
        with self.assertRaisesRegex(ValueError, "Production-like"):
            refuse_production_like_environment("production")

    def test_production_like_environment_can_be_overridden(self) -> None:
        refuse_production_like_environment("production", allow_production=True)
