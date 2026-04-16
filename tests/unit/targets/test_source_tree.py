import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from toolkit.pentest.planner import (
    CORE_PENTEST_TOOL_ORDER,
    OPTIONAL_PENTEST_TOOL_ORDER,
    build_pentest_plan,
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


class SourceTreeTargetBuilderTests(unittest.TestCase):
    def test_derive_source_tree_audit_app_id_is_stable(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name) / "sample-repo"
            source_tree.mkdir()

            derived = derive_source_tree_audit_app_id(source_tree)

        self.assertTrue(derived.startswith(f"{SOURCE_TREE_AUDIT_APP_ID_PREFIX}-sample-repo-"))
        self.assertEqual(len(derived.rsplit("-", 1)[-1]), 8)

    def test_build_source_tree_audit_app_creates_valid_pentest_target(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name) / "repo-root"
            source_tree.mkdir()

            app = build_source_tree_audit_app(source_tree)

        self.assertTrue(app.id.startswith(f"{SOURCE_TREE_AUDIT_APP_ID_PREFIX}-repo-root-"))
        self.assertEqual(app.environment, SOURCE_TREE_AUDIT_DEFAULT_ENVIRONMENT)
        self.assertEqual(str(app.base_url), f"{SOURCE_TREE_AUDIT_BASE_URL}/")
        self.assertEqual(app.host_targets, ["localhost"])
        self.assertEqual(app.target_allowlist, ["localhost"])
        self.assertEqual(app.auth.method, "none")
        self.assertEqual(app.health_endpoint, SOURCE_TREE_AUDIT_DEFAULT_HEALTH_ENDPOINT)
        self.assertEqual(app.enabled_modules, ["pentest"])

    def test_build_source_tree_audit_app_requires_existing_directory(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            missing = Path(temp_dir_name) / "missing-repo"
            file_path = Path(temp_dir_name) / "not-a-directory.txt"
            file_path.write_text("content", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "does not exist"):
                build_source_tree_audit_app(missing)

            with self.assertRaisesRegex(ValueError, "must be a directory"):
                build_source_tree_audit_app(file_path)

    def test_build_source_tree_audit_profile_matches_safe_source_tree_contract(self) -> None:
        profile = build_source_tree_audit_profile()

        self.assertEqual(profile.name, SOURCE_TREE_AUDIT_PROFILE_NAME)
        self.assertEqual(profile.assessment_mode, "source_tree")
        self.assertIsNone(profile.tools.zap)
        self.assertIsNone(profile.tools.nuclei)
        self.assertIsNone(profile.tools.nmap)
        self.assertTrue(profile.tools.trivy.enabled)
        self.assertEqual(
            profile.tools.trivy.allowlisted_rules,
            ["vulnerabilities", "misconfigurations", "secrets"],
        )
        self.assertTrue(profile.tools.semgrep.enabled)
        self.assertEqual(profile.tools.semgrep.allowlisted_rules, ["p/default", "p/secrets"])

    def test_built_source_tree_profile_produces_expected_tool_plan(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name) / "sample-repo"
            source_tree.mkdir()

            app = build_source_tree_audit_app(source_tree)
            profile = build_source_tree_audit_profile()

            plan = build_pentest_plan(
                app_id=app.id,
                environment=app.environment,
                profile=profile,
            )

        self.assertEqual(
            tuple(tool.tool for tool in plan.tools),
            CORE_PENTEST_TOOL_ORDER + OPTIONAL_PENTEST_TOOL_ORDER,
        )
        self.assertFalse(plan.tools[0].enabled)
        self.assertFalse(plan.tools[1].enabled)
        self.assertFalse(plan.tools[2].enabled)
        self.assertTrue(plan.tools[3].enabled)
        self.assertTrue(plan.tools[4].enabled)


if __name__ == "__main__":
    unittest.main()
