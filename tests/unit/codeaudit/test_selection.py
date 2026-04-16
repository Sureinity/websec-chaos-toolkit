import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from toolkit.adapters.base import AdapterAvailability
from toolkit.codeaudit.selection import (
    CODE_AUDIT_TOOL_BINARIES,
    CodeAuditSelectionError,
    inspect_code_audit_readiness,
    inspect_code_audit_runtime,
    inspect_code_audit_runtime_report,
    inspect_code_audit_tooling,
    select_code_audit_runtime,
    select_code_audit_tools,
)
from toolkit.runtime.contracts import RuntimeMode


def _runtime_backend(*, available: bool, binary_prefix: str) -> Mock:
    backend = Mock()
    backend.check_tool_available.side_effect = lambda binary: AdapterAvailability(
        available=available,
        reason=None if available else f"{binary_prefix} backend unavailable",
        binary=f"/usr/bin/{binary}" if available else binary_prefix,
    )
    return backend


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
            "toolkit.codeaudit.selection.build_runtime_backend",
            return_value=_runtime_backend(available=True, binary_prefix="host"),
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
                "toolkit.codeaudit.selection.build_runtime_backend",
                return_value=_runtime_backend(available=True, binary_prefix="host"),
            ):
                readiness = inspect_code_audit_readiness(source_tree)

        self.assertTrue(readiness.path_checked)
        self.assertTrue(readiness.path_ready)
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.resolved_path, source_tree.resolve())

    def test_inspect_code_audit_readiness_marks_missing_path_not_ready(self) -> None:
        missing = Path("/tmp/definitely-missing-code-audit-target")
        with patch(
            "toolkit.codeaudit.selection.build_runtime_backend",
            return_value=_runtime_backend(available=True, binary_prefix="host"),
        ):
            readiness = inspect_code_audit_readiness(missing)

        self.assertTrue(readiness.path_checked)
        self.assertFalse(readiness.path_ready)
        self.assertFalse(readiness.ready)
        self.assertIn("does not exist", readiness.path_detail)

    def test_inspect_code_audit_readiness_reports_missing_tool(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            backend = Mock()
            backend.check_tool_available.side_effect = lambda binary: AdapterAvailability(
                available=binary != "trivy",
                reason=None if binary != "trivy" else "trivy binary was not found on PATH",
                binary=f"/usr/bin/{binary}" if binary != "trivy" else binary,
            )
            with patch(
                "toolkit.codeaudit.selection.build_runtime_backend",
                return_value=backend,
            ):
                readiness = inspect_code_audit_readiness(source_tree, preferred_tool="trivy")

        self.assertEqual(readiness.selected_tools, ("trivy",))
        self.assertTrue(readiness.path_ready)
        self.assertFalse(readiness.ready)
        self.assertFalse(readiness.tool_statuses[0].availability.available)

    def test_inspect_code_audit_runtime_reports_host_readiness(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.runtime.host.find_binary",
                side_effect=lambda binary: Path("/usr/bin") / binary,
            ):
                readiness = inspect_code_audit_runtime(
                    RuntimeMode.HOST,
                    preferred_tool="semgrep",
                    path=source_tree,
                )

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.mode, RuntimeMode.HOST)
        self.assertEqual(readiness.selected_tools, ("semgrep",))

    def test_inspect_code_audit_runtime_reports_container_readiness(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.runtime.container.find_binary",
                return_value=Path("/usr/bin/docker"),
            ):
                readiness = inspect_code_audit_runtime(
                    RuntimeMode.CONTAINER,
                    preferred_tool="trivy",
                    path=source_tree,
                )

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.mode, RuntimeMode.CONTAINER)
        self.assertEqual(readiness.selected_tools, ("trivy",))

    def test_select_code_audit_runtime_prefers_host_when_available(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.runtime.host.find_binary",
                side_effect=lambda binary: Path("/usr/bin") / binary,
            ):
                with patch(
                    "toolkit.runtime.container.find_binary",
                    return_value=Path("/usr/bin/docker"),
                ):
                    selection = select_code_audit_runtime(
                        source_tree,
                        preferred_tool="semgrep",
                    )

        self.assertEqual(selection.mode, RuntimeMode.HOST)

    def test_select_code_audit_runtime_falls_back_to_container(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.runtime.host.find_binary",
                return_value=None,
            ):
                with patch(
                    "toolkit.runtime.container.find_binary",
                    return_value=Path("/usr/bin/docker"),
                ):
                    selection = select_code_audit_runtime(
                        source_tree,
                        preferred_tool="semgrep",
                    )

        self.assertEqual(selection.mode, RuntimeMode.CONTAINER)

    def test_select_code_audit_runtime_rejects_unavailable_requested_mode(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.runtime.container.find_binary",
                return_value=None,
            ):
                with self.assertRaisesRegex(
                    CodeAuditSelectionError,
                    "Requested code-audit runtime is not ready for use: container",
                ):
                    select_code_audit_runtime(
                        source_tree,
                        preferred_tool="trivy",
                        preferred_mode=RuntimeMode.CONTAINER,
                    )

    def test_select_code_audit_runtime_raises_when_no_runtime_is_ready(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.runtime.host.find_binary",
                return_value=None,
            ):
                with patch(
                    "toolkit.runtime.container.find_binary",
                    return_value=None,
                ):
                    with self.assertRaisesRegex(
                        CodeAuditSelectionError,
                        "No code-audit runtime is ready",
                    ):
                        select_code_audit_runtime(source_tree)

    def test_inspect_code_audit_runtime_report_includes_both_modes(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            source_tree = Path(temp_dir_name)
            with patch(
                "toolkit.runtime.host.find_binary",
                side_effect=lambda binary: Path("/usr/bin") / binary,
            ):
                with patch(
                    "toolkit.runtime.container.find_binary",
                    return_value=Path("/usr/bin/docker"),
                ):
                    report = inspect_code_audit_runtime_report(
                        preferred_tool="semgrep",
                        path=source_tree,
                    )

        self.assertEqual(report.recommended_mode, RuntimeMode.HOST)


if __name__ == "__main__":
    unittest.main()
