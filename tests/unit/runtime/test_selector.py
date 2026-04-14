"""Tests for runtime auto-selection used by URL-first audit flows."""

import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.runtime.container import ContainerRuntime
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.host import HostRuntime
from toolkit.runtime.selector import (
    RuntimeSelectionError,
    inspect_audit_readiness,
    inspect_audit_runtime,
    select_audit_runtime,
)


def _binary_path(binary: str) -> Path:
    return Path("/usr/bin") / binary.replace("/", "-")


class AuditRuntimeSelectorTests(unittest.TestCase):
    def test_inspect_audit_runtime_marks_host_ready_when_core_binaries_exist(self) -> None:
        with patch(
            "toolkit.runtime.host.find_binary",
            side_effect=lambda binary: _binary_path(binary),
        ):
            readiness = inspect_audit_runtime(RuntimeMode.HOST)

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.missing_tools, ())
        self.assertEqual(readiness.tool_statuses[0].binary, "zap-baseline.py")
        self.assertEqual(readiness.tool_statuses[0].availability.binary, "/usr/bin/zap-baseline.py")

    def test_inspect_audit_readiness_reports_container_and_host(self) -> None:
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=_binary_path("docker"),
        ):
            with patch(
                "toolkit.runtime.host.find_binary",
                side_effect=lambda binary: _binary_path(binary),
            ):
                report = inspect_audit_readiness()

        self.assertTrue(report.container.ready)
        self.assertTrue(report.host.ready)
        self.assertEqual(report.recommended_mode, RuntimeMode.CONTAINER)

    def test_select_audit_runtime_prefers_container_when_available(self) -> None:
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=_binary_path("docker"),
        ):
            with patch(
                "toolkit.runtime.host.find_binary",
                side_effect=lambda binary: _binary_path(binary),
            ):
                selection = select_audit_runtime()

        self.assertEqual(selection.mode, RuntimeMode.CONTAINER)
        self.assertIsInstance(selection.backend, ContainerRuntime)

    def test_select_audit_runtime_falls_back_to_host(self) -> None:
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=None,
        ):
            with patch(
                "toolkit.runtime.host.find_binary",
                side_effect=lambda binary: _binary_path(binary),
            ):
                selection = select_audit_runtime()

        self.assertEqual(selection.mode, RuntimeMode.HOST)
        self.assertIsInstance(selection.backend, HostRuntime)

    def test_select_audit_runtime_rejects_unavailable_requested_mode(self) -> None:
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=None,
        ):
            with self.assertRaisesRegex(
                RuntimeSelectionError,
                "Requested audit runtime is not ready for use: container",
            ):
                select_audit_runtime(preferred_mode=RuntimeMode.CONTAINER)

    def test_select_audit_runtime_raises_when_no_runtime_is_ready(self) -> None:
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=None,
        ):
            with patch(
                "toolkit.runtime.host.find_binary",
                return_value=None,
            ):
                with self.assertRaisesRegex(
                    RuntimeSelectionError,
                    "No audit runtime is ready",
                ):
                    select_audit_runtime()


if __name__ == "__main__":
    unittest.main()
