import unittest

from toolkit.codeaudit.contracts import (
    CODE_AUDIT_ALLOWED_TOOLS,
    CODE_AUDIT_CONTRACT,
    CODE_AUDIT_DEFAULT_TOOLS,
    CODE_AUDIT_EXCLUDED_TOOLS,
    code_audit_contract_matches_pentest_modes,
    code_audit_supports_tool,
)
from toolkit.pentest.contracts import PentestAssessmentMode


class CodeAuditContractTests(unittest.TestCase):
    def test_contract_locks_source_tree_only_path(self) -> None:
        self.assertEqual(
            CODE_AUDIT_CONTRACT.assessment_mode,
            PentestAssessmentMode.SOURCE_TREE,
        )
        self.assertEqual(CODE_AUDIT_CONTRACT.target_kind, "source_tree_path")
        self.assertFalse(CODE_AUDIT_CONTRACT.requires_yaml_config)
        self.assertFalse(CODE_AUDIT_CONTRACT.supports_multiple_paths)
        self.assertFalse(CODE_AUDIT_CONTRACT.supports_image_targets)

    def test_contract_defaults_to_semgrep_and_trivy(self) -> None:
        self.assertEqual(CODE_AUDIT_DEFAULT_TOOLS, ("semgrep", "trivy"))
        self.assertEqual(CODE_AUDIT_CONTRACT.default_tools, CODE_AUDIT_DEFAULT_TOOLS)
        self.assertEqual(CODE_AUDIT_ALLOWED_TOOLS, frozenset({"semgrep", "trivy"}))
        self.assertEqual(CODE_AUDIT_CONTRACT.allowed_tools, CODE_AUDIT_ALLOWED_TOOLS)

    def test_contract_excludes_remote_web_tools(self) -> None:
        self.assertEqual(CODE_AUDIT_EXCLUDED_TOOLS, frozenset({"zap", "nuclei", "nmap"}))
        self.assertEqual(CODE_AUDIT_CONTRACT.excluded_tools, CODE_AUDIT_EXCLUDED_TOOLS)

    def test_code_audit_supports_tool_only_accepts_semgrep_and_trivy(self) -> None:
        self.assertTrue(code_audit_supports_tool("semgrep"))
        self.assertTrue(code_audit_supports_tool("trivy"))
        self.assertFalse(code_audit_supports_tool("zap"))
        self.assertFalse(code_audit_supports_tool("nuclei"))
        self.assertFalse(code_audit_supports_tool("nmap"))

    def test_contract_matches_existing_pentest_target_modes(self) -> None:
        self.assertTrue(code_audit_contract_matches_pentest_modes())


if __name__ == "__main__":
    unittest.main()
