import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from toolkit.core.run_context import RunRequest, prepare_run_context
from toolkit.reports.builder import (
    build_markdown_summary,
    build_markdown_summary_from_run_dir,
    executive_summary_path,
    write_markdown_summary,
)
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


class ReportBuilderTests(unittest.TestCase):
    def test_build_markdown_summary_groups_by_app_and_severity(self) -> None:
        results = [
            build_result(severity="medium", tool="nuclei", category="exposure"),
            build_result(severity="high", tool="zap", category="headers"),
            build_result(
                app_id="sample-api",
                target="https://staging.internal.example",
                severity="low",
                tool="nmap",
                category="ports",
                remediation_summary="Close the exposed port.",
            ),
        ]

        summary = build_markdown_summary("20260328-020304-deadbeef", results)

        self.assertIn("# Run Summary: 20260328-020304-deadbeef", summary)
        self.assertIn("## sample-api", summary)
        self.assertIn("## sample-app", summary)
        self.assertIn("### high (1)", summary)
        self.assertIn("### medium (1)", summary)
        self.assertIn("### low (1)", summary)
        self.assertIn("- Tool: zap", summary)
        self.assertIn("- Tool: nuclei", summary)
        self.assertIn("- Tool: nmap", summary)

    def test_build_markdown_summary_handles_empty_runs(self) -> None:
        summary = build_markdown_summary("20260328-020304-deadbeef", [])

        self.assertIn("Total findings: 0", summary)
        self.assertIn("No findings were normalized for this run.", summary)

    def test_write_markdown_summary_rebuilds_from_stored_bundle(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [
            build_result(severity="high", tool="zap", category="headers"),
            build_result(tool="nuclei", category="exposure", severity="medium"),
        ]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )
            write_normalized_results(context, results)

            rebuilt_summary = build_markdown_summary_from_run_dir(context.run_dir)
            summary_path = write_markdown_summary(context.run_dir)
            written_summary = summary_path.read_text(encoding="utf-8")

        self.assertEqual(summary_path, executive_summary_path(context.run_dir))
        self.assertTrue(written_summary.endswith("\n"))
        self.assertEqual(written_summary.rstrip("\n"), rebuilt_summary)
        self.assertIn("## sample-app", rebuilt_summary)
        self.assertIn("### high (1)", rebuilt_summary)
        self.assertIn("### medium (1)", rebuilt_summary)
