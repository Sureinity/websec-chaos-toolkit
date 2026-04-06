import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from toolkit.cli import app
from toolkit.core.exits import ExitCode
from toolkit.core.run_context import RunRequest, prepare_run_context
from toolkit.reports.builder import executive_summary_path
from toolkit.results.io import write_normalized_results
from toolkit.results.models import NormalizedResult, ResultTimestamps

RUNNER = CliRunner()


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
        timestamps=ResultTimestamps(),
    )


class ReportCommandTests(unittest.TestCase):
    def test_report_build_succeeds_for_existing_run_bundle(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )
            write_normalized_results(
                context,
                [
                    build_result(severity="high"),
                    build_result(tool="nuclei", category="exposure", severity="medium"),
                ],
            )

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["report", "build", "--run-id", context.run_id],
                    catch_exceptions=False,
                )

            summary_path = executive_summary_path(context.run_dir)
            self.assertTrue(summary_path.is_file())
            summary_content = summary_path.read_text(encoding="utf-8")

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Report generated.", result.stdout)
        self.assertIn(f"Run: {context.run_id}", result.stdout)
        self.assertIn(str(summary_path), result.stdout)
        self.assertIn("# Run Summary: 20260328-020304-deadbeef", summary_content)
        self.assertIn("### high (1)", summary_content)
        self.assertIn("### medium (1)", summary_content)

    def test_report_build_fails_for_missing_run_directory(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["report", "build", "--run-id", "missing-run"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Report build failed.", result.stderr)
        self.assertIn("Run directory does not exist", result.stderr)

    def test_report_build_fails_for_missing_normalized_bundle(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["report", "build", "--run-id", context.run_id],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Report build failed.", result.stderr)
        self.assertIn("Normalized results bundle does not exist", result.stderr)
