import unittest
from datetime import UTC, datetime

from toolkit.adapters.base import (
    AdapterAvailability,
    AdapterSkipReason,
    ToolExecution,
    build_failed_result,
    build_skipped_result,
    build_success_result,
)
from toolkit.results.normalizers import (
    build_normalized_result,
    build_result_timestamps,
    normalize_confidence,
    normalize_evidence,
    normalize_severity,
)


class NormalizationHelperTests(unittest.TestCase):
    def test_normalize_severity_uses_mapping_and_defaults(self) -> None:
        self.assertEqual(
            normalize_severity("2", mapping={"2": "medium"}),
            "medium",
        )
        self.assertEqual(normalize_severity("HIGH"), "high")
        self.assertEqual(normalize_severity(None), "info")

    def test_normalize_confidence_uses_mapping_and_defaults(self) -> None:
        self.assertEqual(
            normalize_confidence("3", mapping={"3": "high"}),
            "high",
        )
        self.assertEqual(normalize_confidence("MEDIUM"), "medium")
        self.assertEqual(normalize_confidence(None), "medium")

    def test_normalize_evidence_filters_blank_values(self) -> None:
        evidence = normalize_evidence([" first ", "", "   ", "second"])

        self.assertEqual(evidence, ["first", "second"])

    def test_build_result_timestamps_preserves_explicit_values(self) -> None:
        started_at = datetime(2026, 3, 29, 1, 2, 3, tzinfo=UTC)
        finished_at = datetime(2026, 3, 29, 1, 4, 5, tzinfo=UTC)

        timestamps = build_result_timestamps(
            started_at=started_at,
            finished_at=finished_at,
        )

        self.assertEqual(timestamps.started_at, started_at)
        self.assertEqual(timestamps.finished_at, finished_at)

    def test_build_normalized_result_applies_shared_cleanup(self) -> None:
        result = build_normalized_result(
            app_id="sample-app",
            environment="local",
            target="http://localhost:8000",
            tool="zap",
            category="headers",
            severity="1",
            confidence="2",
            evidence=[" first ", "", "second "],
            remediation_summary=" Fix the header. ",
            severity_mapping={"1": "low"},
            confidence_mapping={"2": "high"},
        )

        self.assertEqual(result.severity, "low")
        self.assertEqual(result.confidence, "high")
        self.assertEqual(result.evidence, ["first", "second"])
        self.assertEqual(result.remediation_summary, "Fix the header.")


class AdapterOutcomeHelperTests(unittest.TestCase):
    def test_build_success_result_preserves_findings_and_artifacts(self) -> None:
        execution = ToolExecution(tool="nuclei", command=("nuclei", "-jsonl"))
        availability = AdapterAvailability(available=True, binary="nuclei")
        result = build_success_result(
            "nuclei",
            execution=execution,
            availability=availability,
        )

        self.assertFalse(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.execution, execution)
        self.assertEqual(result.availability, availability)

    def test_build_skipped_result_marks_skip_reason(self) -> None:
        result = build_skipped_result(
            "zap",
            skip_reason=AdapterSkipReason.MISSING_BINARY,
            availability=AdapterAvailability(
                available=False,
                reason="zap binary was not found on PATH",
                binary="zap-baseline.py",
            ),
        )

        self.assertTrue(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.skip_reason, AdapterSkipReason.MISSING_BINARY)

    def test_build_failed_result_marks_failure_detail(self) -> None:
        result = build_failed_result(
            "nmap",
            error_detail="nmap exited with a non-zero status code",
            execution=ToolExecution(tool="nmap", command=("nmap", "-F")),
        )

        self.assertFalse(result.skipped)
        self.assertTrue(result.failed)
        self.assertEqual(result.error_detail, "nmap exited with a non-zero status code")
