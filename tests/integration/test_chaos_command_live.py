"""Command-level integration tests for the live chaos execution path.

These tests verify that `toolkit chaos run` correctly maps live execution
outcomes to exit codes and CLI output. The Toxiproxy and monitoring layers
are mocked so no real runtime is required.
"""

import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from toolkit.chaos.contracts import (
    ChaosExperimentPlan,
    ChaosRunStatus,
    ChaosRunSummary,
)
from toolkit.chaos.toxiproxy import (
    ToxiproxyProxyNotFoundError,
    ToxiproxyRequestError,
)
from toolkit.cli import app
from toolkit.core.exits import ExitCode

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
RUNNER = CliRunner()


def _copy_configs(source_dir: Path, target_dir: Path) -> None:
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


def _invoke_chaos_run(project_root: Path):
    with chdir(project_root):
        return RUNNER.invoke(
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


class LiveChaosCommandExitCodeTests(unittest.TestCase):
    def test_passing_experiment_exits_0(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _copy_configs(fixture_dir, project_root)

            summary = ChaosRunSummary(
                run_id="run-1",
                status=ChaosRunStatus.SUCCESS,
                exit_code=ExitCode.SUCCESS,
                experiment_plan=_plan(),
                baseline_captured=True,
                rollback_attempted=True,
            )
            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                return_value=summary,
            ):
                result = _invoke_chaos_run(project_root)

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Chaos run completed.", result.stdout)
        self.assertIn("Status: success", result.stdout)

    def test_threshold_breach_exits_1(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _copy_configs(fixture_dir, project_root)

            summary = ChaosRunSummary(
                run_id="run-1",
                status=ChaosRunStatus.RESILIENCE_FAILURE,
                exit_code=ExitCode.FINDINGS_OR_FAILURE,
                experiment_plan=_plan(),
                baseline_captured=True,
                rollback_attempted=True,
                findings_count=1,
                aborted=True,
                abort_reason="consecutive health failures exceeded threshold",
            )
            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                return_value=summary,
            ):
                result = _invoke_chaos_run(project_root)

        self.assertEqual(result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Status: resilience_failure", result.stdout)
        self.assertIn("Abort reason:", result.stdout)

    def test_missing_toxiproxy_runtime_exits_2(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _copy_configs(fixture_dir, project_root)

            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                side_effect=ToxiproxyRequestError(
                    operation="preflight",
                    detail="Connection refused",
                ),
            ):
                result = _invoke_chaos_run(project_root)

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("Connection refused", result.stderr)

    def test_missing_proxy_exits_2(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _copy_configs(fixture_dir, project_root)

            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                side_effect=ToxiproxyProxyNotFoundError(
                    proxy_name="sample-api",
                ),
            ):
                result = _invoke_chaos_run(project_root)

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("sample-api", result.stderr)

    def test_rollback_failure_exits_2(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _copy_configs(fixture_dir, project_root)

            summary = ChaosRunSummary(
                run_id="run-1",
                status=ChaosRunStatus.FAILED,
                exit_code=ExitCode.CONFIG_OR_RUNTIME_ERROR,
                experiment_plan=_plan(),
                baseline_captured=True,
                rollback_attempted=True,
                error_detail="rollback failed: proxy remained disabled",
            )
            with patch(
                "toolkit.commands.chaos.run_chaos_live_flow",
                return_value=summary,
            ):
                result = _invoke_chaos_run(project_root)

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("rollback failed", result.stderr)
