import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from toolkit.chaos.contracts import (
    ChaosExperimentPlan,
    ChaosRunStatus,
    ChaosRunSummary,
)
from toolkit.chaos.edge_runtime import EdgeChaosPreparedProxy, EdgeChaosRuntimeError
from toolkit.cli import app
from toolkit.core.exits import ExitCode

RUNNER = CliRunner()


def _plan() -> ChaosExperimentPlan:
    return ChaosExperimentPlan(
        app_id="adhoc-127-0-0-1-8000",
        environment="local",
        profile="adhoc-edge-latency",
        target_service="toolkit-edge-adhoc-127-0-0-1-8000",
        fault_type="latency",
        baseline_duration_seconds=5,
        experiment_duration_seconds=10,
        health_endpoint="/",
        rollback_method="managed_edge_proxy_reset",
        consecutive_health_failures=2,
    )


class EdgeChaosCommandTests(unittest.TestCase):
    def test_edge_chaos_succeeds_without_yaml(self) -> None:
        runtime = Mock()
        runtime.prepare_proxy.return_value = EdgeChaosPreparedProxy(
            proxy_name="toolkit-edge-adhoc-127-0-0-1-8000",
            proxy_origin="http://127.0.0.1:18080",
            upstream_origin="http://127.0.0.1:8000",
            toxiproxy_base_url="http://127.0.0.1:8474",
        )
        summary = ChaosRunSummary(
            run_id="run-1",
            status=ChaosRunStatus.SUCCESS,
            exit_code=ExitCode.SUCCESS,
            experiment_plan=_plan(),
            baseline_captured=True,
            rollback_attempted=True,
            normalized_bundle_path=Path("/tmp/outputs/run-1/normalized/findings.json"),
            report_path=Path("/tmp/outputs/run-1/reports/executive-summary.md"),
        )

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.edge_chaos.ManagedEdgeChaosDockerRuntime",
                return_value=runtime,
            ):
                with patch(
                    "toolkit.commands.edge_chaos.run_chaos_live_flow",
                    return_value=summary,
                ) as run_flow:
                    with chdir(project_root):
                        result = RUNNER.invoke(
                            app,
                            ["edge-chaos", "http://127.0.0.1:8000"],
                            catch_exceptions=False,
                        )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Edge chaos completed.", result.stdout)
        self.assertIn("Target: http://127.0.0.1:8000/", result.stdout)
        self.assertIn("Fault: latency", result.stdout)
        self.assertIn("Proxy: http://127.0.0.1:18080", result.stdout)
        runtime.prepare_proxy.assert_called_once()
        runtime.close.assert_called_once()
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(str(kwargs["app"].base_url), "http://127.0.0.1:8000/")
        self.assertEqual(kwargs["profile"].target_service, "toolkit-edge-adhoc-127-0-0-1-8000")
        self.assertEqual(kwargs["toxiproxy_base_url"], "http://127.0.0.1:8474")
        self.assertIsNotNone(kwargs["monitoring_client"])

    def test_edge_chaos_threshold_breach_exits_1(self) -> None:
        runtime = Mock()
        runtime.prepare_proxy.return_value = EdgeChaosPreparedProxy(
            proxy_name="toolkit-edge-adhoc-127-0-0-1-8000",
            proxy_origin="http://127.0.0.1:18080",
            upstream_origin="http://127.0.0.1:8000",
            toxiproxy_base_url="http://127.0.0.1:8474",
        )
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

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.edge_chaos.ManagedEdgeChaosDockerRuntime",
                return_value=runtime,
            ):
                with patch(
                    "toolkit.commands.edge_chaos.run_chaos_live_flow",
                    return_value=summary,
                ):
                    with chdir(project_root):
                        result = RUNNER.invoke(
                            app,
                            ["edge-chaos", "http://127.0.0.1:8000"],
                            catch_exceptions=False,
                        )

        self.assertEqual(result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Status: resilience_failure", result.stdout)
        self.assertIn("Abort reason:", result.stdout)

    def test_edge_chaos_reports_runtime_failures(self) -> None:
        runtime = Mock()
        runtime.prepare_proxy.side_effect = EdgeChaosRuntimeError(
            "docker failed to start toxiproxy"
        )

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.edge_chaos.ManagedEdgeChaosDockerRuntime",
                return_value=runtime,
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["edge-chaos", "http://127.0.0.1:8000"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Edge chaos failed.", result.stderr)
        runtime.close.assert_called_once()

    def test_edge_chaos_rejects_invalid_url(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["edge-chaos", "not-a-url"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Edge chaos failed.", result.stderr)


if __name__ == "__main__":
    unittest.main()
