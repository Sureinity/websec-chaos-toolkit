import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from toolkit.adapters.base import AdapterAvailability
from toolkit.codeaudit.selection import (
    CODE_AUDIT_TOOL_BINARIES,
    CodeAuditSelectionError,
    inspect_code_audit_readiness,
    inspect_code_audit_tooling,
    select_code_audit_tools,
)


class CodeAuditSelectionTests(unittest.TestCase):
    def test_select_code_audit_tools_defaults_to_both_tools(self) -> None:
        self.assertEqual(select_code_audit_tools(), ("semgrep", "trivy"))

    def test_select_code_audit_tools_narrows_to_requested_tool(self) -> None:
        self.assertEqual(select_code_audit_tools("semgrep"), ("semgrep",))
        self.assertEqual(select_code_audit_tools("trivy"), ("trivy",))

    def test_select_code_audit_tools_rejects_unknown_tool(self) -> None:
        with self.assertRaisesRegex(CodeAuditSelectionError, "Unsupported code-audit tool"):
            select_code_audit_tools("zap")

    def test_inspect_code_audit_tooling_reports_selected_tool_statuses(self) -> None:
        with patch(
            "toolkit.codeaudit.selection.check_binary_available",
            side_effect=lambda binary: AdapterAvailability(
                available=True,
                binary=f"/usr/bin/{binary}",
            ),
        ):
            readiness = inspect_code_audit_tooling()

        self.assertFalse(readiness.path_checked)
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.selected_tools, ("semgrep", "trivy"))
        self.assertEqual(
            tuple(status.binary for status in readiness.tool_statuses),
            (
                CODE_AUDIT_TOOL_BINARIES["semgrep"],
                CODE_AUDIT_TOOL_BINARIES["trivy"],
            ),
        )

    def test_inspect_code_audit_readiness_marks_valid_path_ready(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.codeaudit.selection.check_binary_available",
                side_effect=lambda binary: AdapterAvailability(
                    available=True,
                    binary=f"/usr/bin/{binary}",
                ),
            ):
                readiness = inspect_code_audit_readiness(source_tree)

        self.assertTrue(readiness.path_checked)
        self.assertTrue(readiness.path_ready)
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.resolved_path, source_tree.resolve())

    def test_inspect_code_audit_readiness_marks_missing_path_not_ready(self) -> None:
        missing = Path("/tmp/definitely-missing-code-audit-target")
        with patch(
            "toolkit.codeaudit.selection.check_binary_available",
            side_effect=lambda binary: AdapterAvailability(
                available=True,
                binary=f"/usr/bin/{binary}",
            ),
        ):
            readiness = inspect_code_audit_readiness(missing)

        self.assertTrue(readiness.path_checked)
        self.assertFalse(readiness.path_ready)
        self.assertFalse(readiness.ready)
        self.assertIn("does not exist", readiness.path_detail)

    def test_inspect_code_audit_readiness_reports_missing_tool(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.codeaudit.selection.check_binary_available",
                side_effect=lambda binary: AdapterAvailability(
                    available=binary != "trivy",
                    reason=None if binary != "trivy" else "trivy binary was not found on PATH",
                    binary=f"/usr/bin/{binary}" if binary != "trivy" else binary,
                ),
            ):
                readiness = inspect_code_audit_readiness(source_tree, preferred_tool="trivy")

        self.assertEqual(readiness.selected_tools, ("trivy",))
        self.assertTrue(readiness.path_ready)
        self.assertFalse(readiness.ready)
        self.assertFalse(readiness.tool_statuses[0].availability.available)


if __name__ == "__main__":
    unittest.main()
