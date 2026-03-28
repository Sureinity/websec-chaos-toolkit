from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import unittest

from toolkit.core.run_context import RunRequest, prepare_run_context
from toolkit.results.io import (
    read_normalized_results,
    read_normalized_results_from_path,
    write_normalized_results,
)
from toolkit.results.models import NormalizedResult, ResultTimestamps


def build_result(
    *,
    app_id: str = "sample-app",
    environment: str = "local",
    target: str = "http://localhost:8000",
    tool: str = "zap",
    category: str = "headers",
    severity: str = "low",
    confidence: str = "high",
    remediation_summary: str = "Set the missing security header.",
) -> NormalizedResult:
    return NormalizedResult(
        app_id=app_id,
        environment=environment,
        target=target,
        tool=tool,
        category=category,
        severity=severity,
        confidence=confidence,
        evidence=["missing x-frame-options"],
        remediation_summary=remediation_summary,
        timestamps=ResultTimestamps(
            started_at=datetime(2026, 3, 28, 2, 3, 4, tzinfo=UTC),
            finished_at=datetime(2026, 3, 28, 2, 5, 6, tzinfo=UTC),
        ),
    )


class NormalizedResultsIoTests(unittest.TestCase):
    def test_write_and_read_normalized_results_round_trip(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [
            build_result(),
            build_result(
                tool="nuclei",
                category="exposure",
                severity="medium",
                confidence="medium",
                remediation_summary="Restrict the exposed endpoint.",
            ),
        ]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            bundle_path = write_normalized_results(context, results)
            loaded_results = read_normalized_results(context)

        self.assertEqual(bundle_path.name, "findings.json")
        self.assertEqual(len(loaded_results), 2)
        self.assertEqual(loaded_results[0].tool, "zap")
        self.assertEqual(loaded_results[1].tool, "nuclei")
        self.assertEqual(loaded_results[1].severity, "medium")

    def test_write_normalized_results_uses_deterministic_json_format(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [build_result()]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            bundle_path = write_normalized_results(context, results)
            content = bundle_path.read_text(encoding="utf-8")

        self.assertTrue(content.endswith("\n"))
        self.assertIn('"app_id": "sample-app"', content)
        self.assertIn('"started_at": "2026-03-28T02:03:04Z"', content)
        self.assertIn('"tool": "zap"', content)

    def test_read_normalized_results_from_path_supports_explicit_bundle_path(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [build_result()]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            bundle_path = write_normalized_results(context, results)
            loaded_results = read_normalized_results_from_path(bundle_path)

        self.assertEqual(len(loaded_results), 1)
        self.assertEqual(loaded_results[0].remediation_summary, "Set the missing security header.")
