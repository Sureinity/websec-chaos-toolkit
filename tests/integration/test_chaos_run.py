from datetime import UTC, datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from toolkit.chaos.contracts import ChaosRunStatus
from toolkit.chaos.runner import run_chaos_fixture_flow
from toolkit.chaos.service import ChaosFixturePaths, FixtureToxiproxyController
from toolkit.config.models import AppRegistry, ChaosProfileRegistry
from toolkit.core.exits import ExitCode

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def load_valid_app_and_profile():
    apps = AppRegistry.model_validate(
        yaml.safe_load(
            (FIXTURE_ROOT / "configs" / "valid" / "auth-method-matrix" / "apps.yaml").read_text(
                encoding="utf-8"
            )
        )
    )
    profiles = ChaosProfileRegistry.model_validate(
        yaml.safe_load(
            (
                FIXTURE_ROOT
                / "configs"
                / "valid"
                / "auth-method-matrix"
                / "chaos-profiles.yaml"
            ).read_text(encoding="utf-8")
        )
    )
    return apps.apps[0], profiles.profiles[0]


class ChaosRunIntegrationTests(unittest.TestCase):
    def test_chaos_fixture_run_writes_artifacts_for_passing_experiment(self) -> None:
        app, profile = load_valid_app_and_profile()
        when = datetime(2026, 3, 30, 6, 0, 0, tzinfo=UTC)

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            controller = FixtureToxiproxyController()
            summary = run_chaos_fixture_flow(
                project_root=project_root,
                app=app,
                profile=profile,
                fixture_paths=fixture_paths("passing-latency"),
                toxiproxy_controller=controller,
                when=when,
            )

            run_dir = project_root / "outputs" / summary.run_id
            manifest_path = run_dir / "manifest.json"
            normalized_path = run_dir / "normalized" / "findings.json"
            report_path = run_dir / "reports" / "executive-summary.md"
            baseline_path = run_dir / "raw" / "chaos" / "baseline-observations.json"
            experiment_path = run_dir / "raw" / "chaos" / "experiment-observations.json"
            actions_path = run_dir / "raw" / "chaos" / "orchestration-actions.json"

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            normalized_findings = json.loads(normalized_path.read_text(encoding="utf-8"))
            report = report_path.read_text(encoding="utf-8")
            actions = json.loads(actions_path.read_text(encoding="utf-8"))

            self.assertTrue(manifest_path.is_file())
            self.assertTrue(normalized_path.is_file())
            self.assertTrue(report_path.is_file())
            self.assertTrue(baseline_path.is_file())
            self.assertTrue(experiment_path.is_file())
            self.assertTrue(actions_path.is_file())

        self.assertEqual(summary.status, ChaosRunStatus.SUCCESS)
        self.assertEqual(summary.exit_code, ExitCode.SUCCESS)
        self.assertEqual(summary.findings_count, 0)
        self.assertTrue(summary.baseline_captured)
        self.assertTrue(summary.rollback_attempted)
        self.assertFalse(summary.aborted)
        self.assertIsNone(summary.error_detail)
        self.assertEqual(len(summary.raw_artifact_paths), 3)

        self.assertEqual(manifest["run_id"], summary.run_id)
        self.assertEqual(manifest["app_id"], "local-no-auth-app")
        self.assertEqual(manifest["environment"], "local")
        self.assertEqual(manifest["profile"], "dependency-latency-baseline")
        self.assertEqual(manifest["modules"], ["chaos"])
        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["exit_code"], 0)
        self.assertEqual(manifest["start_time"], "2026-03-30T06:00:00Z")
        self.assertEqual(manifest["end_time"], "2026-03-30T06:01:30Z")
        self.assertEqual(normalized_findings, [])
        self.assertIn("No findings were normalized for this run.", report)
        self.assertEqual(actions["fault_type"], "latency")
        self.assertTrue(actions["rollback_attempted"])
        self.assertFalse(actions["rollback_failed"])
        self.assertEqual(len(controller.operations), 2)

    def test_chaos_fixture_run_creates_resilience_finding_on_threshold_breach(self) -> None:
        app, profile = load_valid_app_and_profile()

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            summary = run_chaos_fixture_flow(
                project_root=project_root,
                app=app,
                profile=profile,
                fixture_paths=fixture_paths("abort-health"),
                toxiproxy_controller=FixtureToxiproxyController(),
                when=datetime(2026, 3, 30, 6, 0, 0, tzinfo=UTC),
            )

            run_dir = project_root / "outputs" / summary.run_id
            normalized_findings = json.loads(
                (run_dir / "normalized" / "findings.json").read_text(encoding="utf-8")
            )
            report = (run_dir / "reports" / "executive-summary.md").read_text(encoding="utf-8")

        self.assertEqual(summary.status, ChaosRunStatus.RESILIENCE_FAILURE)
        self.assertEqual(summary.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertEqual(summary.findings_count, 1)
        self.assertTrue(summary.baseline_captured)
        self.assertTrue(summary.rollback_attempted)
        self.assertTrue(summary.aborted)
        self.assertEqual(
            summary.abort_reason,
            "health checks breached the consecutive-failure threshold",
        )
        self.assertEqual(len(normalized_findings), 1)
        self.assertEqual(normalized_findings[0]["tool"], "chaos")
        self.assertEqual(normalized_findings[0]["severity"], "high")
        self.assertEqual(
            normalized_findings[0]["category"],
            "resilience_abort_threshold_breach",
        )
        self.assertIn("### high (1)", report)

    def test_chaos_fixture_run_attempts_rollback_on_timeout(self) -> None:
        app, profile = load_valid_app_and_profile()
        controller = FixtureToxiproxyController()

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)

            def loader(path: Path):
                if path.name == "experiment-observations.json":
                    raise TimeoutError("experiment window timed out")
                from toolkit.chaos.monitoring import read_monitoring_observations_from_path

                return read_monitoring_observations_from_path(path)

            summary = run_chaos_fixture_flow(
                project_root=project_root,
                app=app,
                profile=profile,
                fixture_paths=fixture_paths("passing-latency"),
                toxiproxy_controller=controller,
                load_observations=loader,
                when=datetime(2026, 3, 30, 6, 0, 0, tzinfo=UTC),
            )

            run_dir = project_root / "outputs" / summary.run_id
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            actions = json.loads(
                (run_dir / "raw" / "chaos" / "orchestration-actions.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(summary.status, ChaosRunStatus.FAILED)
        self.assertEqual(summary.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertTrue(summary.baseline_captured)
        self.assertTrue(summary.rollback_attempted)
        self.assertEqual(summary.error_detail, "experiment window timed out")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["exit_code"], 2)
        self.assertFalse((run_dir / "raw" / "chaos" / "experiment-observations.json").exists())
        self.assertEqual(len(controller.operations), 2)
        self.assertTrue(actions["rollback_attempted"])

    def test_chaos_fixture_run_attempts_rollback_on_general_error(self) -> None:
        app, profile = load_valid_app_and_profile()
        controller = FixtureToxiproxyController()

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)

            def loader(path: Path):
                if path.name == "experiment-observations.json":
                    raise RuntimeError("monitoring stream failed")
                from toolkit.chaos.monitoring import read_monitoring_observations_from_path

                return read_monitoring_observations_from_path(path)

            summary = run_chaos_fixture_flow(
                project_root=project_root,
                app=app,
                profile=profile,
                fixture_paths=fixture_paths("passing-latency"),
                toxiproxy_controller=controller,
                load_observations=loader,
                when=datetime(2026, 3, 30, 6, 0, 0, tzinfo=UTC),
            )

            run_dir = project_root / "outputs" / summary.run_id
            normalized_findings = json.loads(
                (run_dir / "normalized" / "findings.json").read_text(encoding="utf-8")
            )

        self.assertEqual(summary.status, ChaosRunStatus.FAILED)
        self.assertEqual(summary.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertTrue(summary.rollback_attempted)
        self.assertEqual(summary.error_detail, "monitoring stream failed")
        self.assertEqual(normalized_findings, [])
        self.assertEqual(len(controller.operations), 2)


def fixture_paths(name: str) -> ChaosFixturePaths:
    scenario_root = FIXTURE_ROOT / "chaos" / name
    return ChaosFixturePaths(
        baseline_observations_path=scenario_root / "baseline-observations.json",
        experiment_observations_path=scenario_root / "experiment-observations.json",
    )
