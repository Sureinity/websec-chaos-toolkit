import re
import shutil
import unittest
from contextlib import chdir
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from toolkit.adapters.base import (
    AdapterAvailability,
    AdapterSkipReason,
    build_skipped_result,
    build_success_result,
)
from toolkit.chaos.contracts import (
    ChaosExperimentPlan,
    ChaosRunStatus,
    ChaosRunSummary,
)
from toolkit.cli import app
from toolkit.core.exits import ExitCode
from toolkit.results.normalizers import build_normalized_result

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "examples" / "configs"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
RUNNER = CliRunner()


def stage_example_config_pack(source_dir: Path, target_dir: Path) -> None:
    for name in ("apps.yaml", "pentest-profiles.yaml", "chaos-profiles.yaml"):
        shutil.copy2(source_dir / name, target_dir / name)


def copy_adapter_fixtures(target_dir: Path) -> None:
    tests_root = target_dir / "tests" / "fixtures"
    for tool_name in ("zap", "nuclei", "nmap"):
        destination_dir = tests_root / tool_name
        destination_dir.mkdir(parents=True, exist_ok=True)
        source_dir = FIXTURE_ROOT / tool_name
        for path in source_dir.iterdir():
            shutil.copy2(path, destination_dir / path.name)


def copy_chaos_fixture_scenario(
    target_dir: Path,
    *,
    source_name: str,
    destination_name: str = "passing-latency",
) -> None:
    destination_dir = target_dir / "tests" / "fixtures" / "chaos" / destination_name
    destination_dir.mkdir(parents=True, exist_ok=True)
    source_dir = FIXTURE_ROOT / "chaos" / source_name
    for path in source_dir.iterdir():
        shutil.copy2(path, destination_dir / path.name)


def extract_run_id(output: str) -> str:
    match = re.search(r"Run: (\S+)", output)
    if match is None:
        raise AssertionError(f"Command output did not include a run id:\n{output}")
    return match.group(1)


def _sample_pentest_results_with_findings(app_id: str):
    """Return mock execution results that produce findings for smoke tests."""
    _when = datetime(2026, 4, 1, tzinfo=UTC)
    finding = build_normalized_result(
        app_id=app_id,
        environment="local",
        target="http://localhost:8000/",
        tool="zap",
        category="headers",
        severity="medium",
        confidence="high",
        evidence=["Content-Security-Policy header missing"],
        remediation_summary="Add a Content-Security-Policy header.",
        started_at=_when,
    )
    return (
        build_success_result("zap", findings=(finding,)),
        build_success_result("nuclei"),
        build_success_result("nmap"),
        build_skipped_result(
            "trivy",
            skip_reason=AdapterSkipReason.DISABLED,
            availability=AdapterAvailability(
                available=False, reason="disabled in profile", binary="trivy"
            ),
        ),
        build_skipped_result(
            "semgrep",
            skip_reason=AdapterSkipReason.DISABLED,
            availability=AdapterAvailability(
                available=False, reason="disabled in profile", binary="semgrep"
            ),
        ),
    )


class ExampleConfigSmokeTests(unittest.TestCase):
    def test_sample_webapp_pack_supports_validate_pentest_chaos_and_report(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            stage_example_config_pack(EXAMPLES_ROOT / "sample-webapp", project_root)
            copy_adapter_fixtures(project_root)
            copy_chaos_fixture_scenario(project_root, source_name="passing-latency")

            with chdir(project_root):
                validate_result = RUNNER.invoke(
                    app,
                    ["validate", "--app", "sample-internal-app", "--env", "local"],
                    catch_exceptions=False,
                )
                with patch(
                    "toolkit.pentest.runner.execute_pentest_plan",
                    return_value=_sample_pentest_results_with_findings("sample-internal-app"),
                ):
                    pentest_result = RUNNER.invoke(
                        app,
                        [
                            "pentest",
                            "run",
                            "--app",
                            "sample-internal-app",
                            "--env",
                            "local",
                            "--profile",
                            "safe-web-baseline",
                        ],
                        catch_exceptions=False,
                    )
                pentest_run_id = extract_run_id(pentest_result.stdout)
                report_result = RUNNER.invoke(
                    app,
                    ["report", "build", "--run-id", pentest_run_id],
                    catch_exceptions=False,
                )
                chaos_mock_summary = ChaosRunSummary(
                    run_id="20260401-100000-chaostest",
                    status=ChaosRunStatus.SUCCESS,
                    exit_code=ExitCode.SUCCESS,
                    experiment_plan=ChaosExperimentPlan(
                        app_id="sample-internal-app",
                        environment="local",
                        profile="dependency-latency-baseline",
                        target_service="database",
                        fault_type="latency",
                        baseline_duration_seconds=30,
                        experiment_duration_seconds=60,
                        health_endpoint="/health",
                        rollback_method="immediate",
                        consecutive_health_failures=3,
                    ),
                    baseline_captured=True,
                    rollback_attempted=True,
                )
                with patch(
                    "toolkit.commands.chaos.run_chaos_live_flow",
                    return_value=chaos_mock_summary,
                ):
                    chaos_result = RUNNER.invoke(
                        app,
                        [
                            "chaos",
                            "run",
                            "--app",
                            "sample-internal-app",
                            "--env",
                            "local",
                            "--profile",
                            "dependency-latency-baseline",
                        ],
                        catch_exceptions=False,
                    )

            pentest_run_dir = project_root / "outputs" / pentest_run_id

            self.assertTrue((pentest_run_dir / "manifest.json").is_file())
            self.assertTrue((pentest_run_dir / "normalized" / "findings.json").is_file())
            self.assertTrue((pentest_run_dir / "reports" / "executive-summary.md").is_file())

        self.assertEqual(validate_result.exit_code, ExitCode.SUCCESS)
        self.assertEqual(pentest_result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertEqual(report_result.exit_code, ExitCode.SUCCESS)
        self.assertEqual(chaos_result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Configuration is valid.", validate_result.stdout)
        self.assertIn("Pentest run completed.", pentest_result.stdout)
        self.assertIn("Status: findings", pentest_result.stdout)
        self.assertIn("Report generated.", report_result.stdout)
        self.assertIn("Chaos run completed.", chaos_result.stdout)
        self.assertIn("Status: success", chaos_result.stdout)

    def test_sample_api_pack_supports_validate_and_authenticated_pentest(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            stage_example_config_pack(EXAMPLES_ROOT / "sample-api", project_root)
            copy_adapter_fixtures(project_root)

            with chdir(project_root):
                validate_result = RUNNER.invoke(
                    app,
                    ["validate", "--app", "sample-api-bearer-app", "--env", "staging"],
                    catch_exceptions=False,
                )
                with patch(
                    "toolkit.pentest.runner.execute_pentest_plan",
                    return_value=_sample_pentest_results_with_findings("sample-api-bearer-app"),
                ):
                    pentest_result = RUNNER.invoke(
                        app,
                        [
                            "pentest",
                            "run",
                            "--app",
                            "sample-api-bearer-app",
                            "--env",
                            "staging",
                            "--profile",
                            "safe-api-baseline",
                        ],
                        env={"SAMPLE_API_BEARER_TOKEN": "placeholder-token"},
                        catch_exceptions=False,
                    )
                pentest_run_id = extract_run_id(pentest_result.stdout)

            pentest_run_dir = project_root / "outputs" / pentest_run_id
            self.assertTrue((pentest_run_dir / "manifest.json").is_file())
            self.assertTrue((pentest_run_dir / "normalized" / "findings.json").is_file())
            self.assertTrue((pentest_run_dir / "reports" / "executive-summary.md").is_file())

        self.assertEqual(validate_result.exit_code, ExitCode.SUCCESS)
        self.assertEqual(pentest_result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Configuration is valid.", validate_result.stdout)
        self.assertIn("App: sample-api-bearer-app", validate_result.stdout)
        self.assertIn("Pentest run completed.", pentest_result.stdout)
        self.assertIn("Status: findings", pentest_result.stdout)
