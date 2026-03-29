import unittest

from toolkit.adapters.base import (
    AdapterAvailability,
    AdapterRunResult,
    AdapterSkipReason,
    ToolArtifact,
    ToolExecution,
)
from toolkit.results.models import NormalizedResult, ResultTimestamps


def build_result() -> NormalizedResult:
    return NormalizedResult(
        app_id="sample-app",
        environment="local",
        target="http://localhost:8000",
        tool="nuclei",
        category="exposure",
        severity="low",
        confidence="high",
        evidence=["matched template"],
        remediation_summary="Restrict the exposed endpoint.",
        timestamps=ResultTimestamps(),
    )


class AdapterContractTests(unittest.TestCase):
    def test_adapter_availability_can_represent_missing_binary(self) -> None:
        availability = AdapterAvailability(
            available=False,
            reason="nuclei binary was not found on PATH",
            binary="nuclei",
        )

        self.assertFalse(availability.available)
        self.assertEqual(availability.binary, "nuclei")
        self.assertIn("not found", availability.reason)

    def test_tool_execution_captures_safe_command_metadata(self) -> None:
        execution = ToolExecution(
            tool="nuclei",
            command=("nuclei", "-jsonl", "-t", "http/exposures"),
            timeout_seconds=120.0,
            env_overrides={"NUCLEI_DISABLE_UPDATE_CHECK": "true"},
        )

        self.assertEqual(execution.tool, "nuclei")
        self.assertEqual(execution.command[0], "nuclei")
        self.assertEqual(execution.timeout_seconds, 120.0)
        self.assertEqual(
            execution.env_overrides,
            {"NUCLEI_DISABLE_UPDATE_CHECK": "true"},
        )

    def test_adapter_run_result_can_represent_skipped_execution(self) -> None:
        result = AdapterRunResult(
            tool="zap",
            availability=AdapterAvailability(
                available=False,
                reason="zap binary was not found on PATH",
                binary="zap.sh",
            ),
            skip_reason=AdapterSkipReason.MISSING_BINARY,
        )

        self.assertTrue(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.skip_reason, AdapterSkipReason.MISSING_BINARY)
        self.assertEqual(result.findings, ())

    def test_adapter_run_result_can_represent_success_with_artifacts_and_findings(self) -> None:
        result = AdapterRunResult(
            tool="nmap",
            execution=ToolExecution(
                tool="nmap",
                command=("nmap", "-Pn", "-p", "80,443", "localhost"),
            ),
            artifacts=(
                ToolArtifact(
                    tool="nmap",
                    path="/tmp/run/raw/nmap/results.xml",
                    kind="raw_output",
                ),
            ),
            findings=(build_result(),),
        )

        self.assertFalse(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.execution.tool, "nmap")
        self.assertEqual(result.artifacts[0].kind, "raw_output")
        self.assertEqual(result.findings[0].tool, "nuclei")

    def test_adapter_run_result_can_represent_hard_failure(self) -> None:
        result = AdapterRunResult(
            tool="zap",
            execution=ToolExecution(
                tool="zap",
                command=("zap.sh", "-cmd"),
            ),
            error_detail="zap exited with a non-zero status code",
        )

        self.assertFalse(result.skipped)
        self.assertTrue(result.failed)
        self.assertEqual(result.error_detail, "zap exited with a non-zero status code")
