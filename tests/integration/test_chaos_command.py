from contextlib import chdir
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
import unittest

from typer.testing import CliRunner

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


class ChaosCommandTests(unittest.TestCase):
    def test_chaos_run_succeeds_against_fixture_backed_repository(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)
            copy_chaos_fixture_scenario(project_root, source_name="passing-latency")

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

            run_id_match = re.search(r"Run: (\S+)", result.stdout)
            self.assertIsNotNone(run_id_match)
            run_id = run_id_match.group(1)
            run_dir = project_root / "outputs" / run_id

            self.assertTrue((run_dir / "manifest.json").is_file())
            self.assertTrue((run_dir / "normalized" / "findings.json").is_file())
            self.assertTrue((run_dir / "reports" / "executive-summary.md").is_file())
            self.assertTrue((run_dir / "raw" / "chaos" / "baseline-observations.json").is_file())
            self.assertTrue((run_dir / "raw" / "chaos" / "experiment-observations.json").is_file())

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
            copy_chaos_fixture_scenario(project_root, source_name="abort-health")

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
            copy_chaos_fixture_scenario(project_root, source_name="passing-latency")

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

    def test_chaos_run_reports_missing_fixture_observations(self) -> None:
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
                        "dependency-latency-baseline",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Chaos run failed.", result.stderr)
        self.assertIn("baseline-observations.json", result.stderr)

    def test_chaos_run_reports_lock_contention(self) -> None:
        fixture_dir = FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            copy_config_fixture_tree(fixture_dir, project_root)
            copy_chaos_fixture_scenario(project_root, source_name="passing-latency")
            lock = acquire_chaos_lock(
                project_root,
                app_id="local-no-auth-app",
                environment="local",
            )
            self.addCleanup(release_chaos_lock, lock)

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
