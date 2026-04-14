import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from toolkit.adapters.base import AdapterAvailability
from toolkit.cli import app
from toolkit.commands.doctor import FeatureReadiness
from toolkit.core.exits import ExitCode
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.selector import (
    AuditRuntimeReadiness,
    AuditRuntimeReport,
    AuditToolReadiness,
)

RUNNER = CliRunner()


def _tool_status(
    *,
    tool: str,
    binary: str,
    available: bool,
    reason: str | None = None,
) -> AuditToolReadiness:
    return AuditToolReadiness(
        tool=tool,
        binary=binary,
        availability=AdapterAvailability(
            available=available,
            reason=reason,
            binary=f"/usr/bin/{binary}" if available else binary,
        ),
    )


class DoctorCommandTests(unittest.TestCase):
    def test_doctor_reports_audit_and_edge_chaos_readiness(self) -> None:
        report = AuditRuntimeReport(
            container=AuditRuntimeReadiness(
                mode=RuntimeMode.CONTAINER,
                tool_statuses=(
                    _tool_status(tool="zap", binary="zap-baseline.py", available=True),
                    _tool_status(tool="nuclei", binary="nuclei", available=True),
                    _tool_status(tool="nmap", binary="nmap", available=True),
                ),
            ),
            host=AuditRuntimeReadiness(
                mode=RuntimeMode.HOST,
                tool_statuses=(
                    _tool_status(
                        tool="zap",
                        binary="zap-baseline.py",
                        available=False,
                        reason="zap-baseline.py binary was not found on PATH",
                    ),
                    _tool_status(tool="nuclei", binary="nuclei", available=True),
                    _tool_status(tool="nmap", binary="nmap", available=True),
                ),
            ),
        )

        with patch(
            "toolkit.commands.doctor.inspect_audit_readiness",
            return_value=report,
        ):
            with patch(
                "toolkit.commands.doctor.inspect_edge_chaos_readiness",
                return_value=FeatureReadiness(
                    name="edge-chaos",
                    ready=False,
                    detail="Managed local edge-chaos runtime is not implemented yet.",
                ),
            ):
                result = RUNNER.invoke(
                    app,
                    ["doctor"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Toolkit readiness", result.stdout)
        self.assertIn("Audit runtime (container): ready", result.stdout)
        self.assertIn("Audit runtime (host): not ready", result.stdout)
        self.assertIn("Recommended audit runtime: container", result.stdout)
        self.assertIn("Edge chaos: not ready", result.stdout)

    def test_doctor_handles_no_available_audit_runtime(self) -> None:
        report = AuditRuntimeReport(
            container=AuditRuntimeReadiness(
                mode=RuntimeMode.CONTAINER,
                tool_statuses=(
                    _tool_status(
                        tool="zap",
                        binary="zap-baseline.py",
                        available=False,
                        reason="docker binary was not found on PATH",
                    ),
                    _tool_status(
                        tool="nuclei",
                        binary="nuclei",
                        available=False,
                        reason="docker binary was not found on PATH",
                    ),
                    _tool_status(
                        tool="nmap",
                        binary="nmap",
                        available=False,
                        reason="docker binary was not found on PATH",
                    ),
                ),
            ),
            host=AuditRuntimeReadiness(
                mode=RuntimeMode.HOST,
                tool_statuses=(
                    _tool_status(
                        tool="zap",
                        binary="zap-baseline.py",
                        available=False,
                        reason="zap-baseline.py binary was not found on PATH",
                    ),
                    _tool_status(
                        tool="nuclei",
                        binary="nuclei",
                        available=False,
                        reason="nuclei binary was not found on PATH",
                    ),
                    _tool_status(
                        tool="nmap",
                        binary="nmap",
                        available=False,
                        reason="nmap binary was not found on PATH",
                    ),
                ),
            ),
        )

        with patch(
            "toolkit.commands.doctor.inspect_audit_readiness",
            return_value=report,
        ):
            result = RUNNER.invoke(
                app,
                ["doctor"],
                catch_exceptions=False,
            )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Recommended audit runtime: unavailable", result.stdout)


if __name__ == "__main__":
    unittest.main()
