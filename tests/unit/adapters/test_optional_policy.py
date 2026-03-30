import unittest

from toolkit.adapters.base import (
    AdapterAvailability,
    AdapterSkipReason,
    ToolExecution,
    build_skipped_result,
)


class OptionalAdapterPolicyTests(unittest.TestCase):
    def test_optional_missing_binary_skips_cleanly_by_default(self) -> None:
        result = build_skipped_result(
            "trivy",
            skip_reason=AdapterSkipReason.MISSING_BINARY,
            availability=AdapterAvailability(
                available=False,
                reason="trivy binary was not found on PATH",
                binary="trivy",
            ),
        )

        self.assertTrue(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.skip_reason, AdapterSkipReason.MISSING_BINARY)
        self.assertEqual(result.tool, "trivy")

    def test_optional_adapter_execution_can_remain_read_only(self) -> None:
        execution = ToolExecution(
            tool="semgrep",
            command=("semgrep", "--config", "p/default", "--json", "."),
            timeout_seconds=120.0,
        )

        self.assertEqual(execution.tool, "semgrep")
        self.assertEqual(execution.command[0], "semgrep")
        self.assertIn("--json", execution.command)
        self.assertNotIn("--autofix", execution.command)

    def test_optional_adapters_do_not_change_core_skip_contract(self) -> None:
        trivy_result = build_skipped_result(
            "trivy",
            skip_reason=AdapterSkipReason.DISABLED,
        )
        semgrep_result = build_skipped_result(
            "semgrep",
            skip_reason=AdapterSkipReason.DISABLED,
        )

        self.assertEqual(trivy_result.skip_reason, AdapterSkipReason.DISABLED)
        self.assertEqual(semgrep_result.skip_reason, AdapterSkipReason.DISABLED)
        self.assertFalse(trivy_result.failed)
        self.assertFalse(semgrep_result.failed)
