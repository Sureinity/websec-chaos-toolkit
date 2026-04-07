import re
import unittest
from contextlib import chdir
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from toolkit.chaos.contracts import (
    ChaosExperimentPlan,
    ChaosRunStatus,
    ChaosRunSummary,
)
from toolkit.chaos.locking import acquire_chaos_lock, release_chaos_lock
from toolkit.cli import app
from toolkit.core.exits import ExitCode

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
RUNNER = CliRunner()


def copy_config_fixture_tree(source_dir: Path, target_dir: Path) -> None:
    for name in ("apps.yaml", "pentest-profiles.yaml", "chaos-profiles.yaml"):
        (target_dir / name).write_text(
            (source_dir / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def _plan() -> ChaosExperimentPlan:
    return ChaosExperimentPlan(
        app_id="local-no-auth-app",
        environment="local",
        profile="dependency-latency-baseline",
        target_service="sample-api",
        fault_type="latency",
        baseline_duration_seconds=30,
        experiment_duration_seconds=60,
        health_endpoint="/health",
        rollback_method="immediate",
        consecutive_health_failures=3,
    )


def _success_summary(run_id: str, *, project_root: Path) -> ChaosRunSummary:
    run_dir = project_root / "outputs" / run_id
    return ChaosRunSummary(
        run_id=run_id,
        status=ChaosRunStatus.SUCCESS,
        exit_code=ExitCode.SUCCESS,
        experiment_plan=_plan(),
        baseline_captured=True,
        rollback_attempted=True,
        findings_count=0,
        normalized_bundle_path=run_dir / "normalized" / "findings.json",
        report_path=run_dir / "reports" / "executive-summary.md",
    )


def _resilience_failure_summary(run_id: str, *, project_root: Path) -> ChaosRunSummary:
    run_dir = project_root / "outputs" / run_id
    return ChaosRunSummary(
        run_id=run_id,
        status=ChaosRunStatus.RESILIENCE_FAILURE,
        exit_code=ExitCode.FINDINGS_OR_FAILURE,
        experiment_plan=_plan(),
        baseline_captured=True,
        rollback_attempted=True,
        findings_count=1,
        aborted=True,
        abort_reason="health checks breached the consecutive-failure threshold",
        normalized_bundle_path=run_dir / "normalized" / "findings.json",
        report_path=run_dir / "reports" / "executive-summary.md",
    )


class ChaosCommandTests(unittest.TestCase):
    def test_chaos_run_succeeds_against_fixture_backed_repository(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)

            run_id = "20260401-100000-aabbccdd"

            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                return_value=_success_summary(run_id, project_root=project_root),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        [
                            "chaos",
                            "run",
                            "--app",
                            "local-no-auth-app",
                            "--env",
                            "local",
                            "--profile",
                            "dependency-latency-baseline",
                        ],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Chaos run completed.", result.stdout)
        self.assertIn("Status: success", result.stdout)
        self.assertIn("Findings: 0", result.stdout)
        self.assertIn("Baseline captured: True", result.stdout)
        self.assertIn("Rollback attempted: True", result.stdout)

    def test_chaos_run_reports_resilience_failure(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)

            run_id = "20260401-100000-aabbccdd"

            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                return_value=_resilience_failure_summary(
                    run_id, project_root=project_root
                ),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        [
                            "chaos",
                            "run",
                            "--app",
                            "local-no-auth-app",
                            "--env",
                            "local",
                            "--profile",
                            "dependency-latency-baseline",
                        ],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Chaos run completed.", result.stdout)
        self.assertIn("Status: resilience_failure", result.stdout)
        self.assertIn("Findings: 1", result.stdout)
        self.assertIn(
            "Abort reason: health checks breached the consecutive-failure threshold",
            result.stdout,
        )

    def test_chaos_run_reports_missing_profile(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    [
                        "chaos",
                        "run",
                        "--app",
                        "local-no-auth-app",
                        "--env",
                        "local",
                        "--profile",
                        "missing-profile",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("Requested chaos profile not found", result.stderr)

    def test_chaos_run_reports_missing_toxiproxy_as_runtime_failure(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)

            from toolkit.chaos.toxiproxy import ToxiproxyRequestError

            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                side_effect=ToxiproxyRequestError(
                    operation="preflight",
                    detail="Connection refused",
                ),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        [
                            "chaos",
                            "run",
                            "--app",
                            "local-no-auth-app",
                            "--env",
                            "local",
                            "--profile",
                            "dependency-latency-baseline",
                        ],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("Connection refused", result.stderr)

    def test_chaos_run_reports_lock_contention(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)
            lock = acquire_chaos_lock(
                project_root,
                app_id="local-no-auth-app",
                environment="local",
            )
            self.addCleanup(release_chaos_lock, lock)

            run_id = "20260401-100000-aabbccdd"
            failed_summary = ChaosRunSummary(
                run_id=run_id,
                status=ChaosRunStatus.FAILED,
                exit_code=ExitCode.CONFIG_OR_RUNTIME_ERROR,
                experiment_plan=_plan(),
                baseline_captured=False,
                rollback_attempted=False,
                error_detail="already active",
            )

            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                return_value=failed_summary,
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        [
                            "chaos",
                            "run",
                            "--app",
                            "local-no-auth-app",
                            "--env",
                            "local",
                            "--profile",
                            "dependency-latency-baseline",
                        ],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("already active", result.stderr)
        self.assertIn("Status: failed", result.stdout)

    def test_chaos_run_reports_invalid_missing_health_configuration(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "invalid" / "missing-health-endpoint"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    [
                        "chaos",
                        "run",
                        "--app",
                        "missing-health-endpoint",
                        "--env",
                        "local",
                        "--profile",
                        "dependency-latency-baseline",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("health_endpoint", result.stderr)

    def test_chaos_run_reports_invalid_missing_rollback_configuration(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "invalid" / "chaos-missing-rollback"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    [
                        "chaos",
                        "run",
                        "--app",
                        "chaos-missing-rollback",
                        "--env",
                        "local",
                        "--profile",
                        "dependency-latency-baseline",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("rollback", result.stderr)

    def test_chaos_run_reports_invalid_controlled_restart_profile(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "invalid" / "controlled-restart-fault"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    [
                        "chaos",
                        "run",
                        "--app",
                        "controlled-restart-fault",
                        "--env",
                        "local",
                        "--profile",
                        "restart-attempt",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("controlled_restart", result.stderr)
