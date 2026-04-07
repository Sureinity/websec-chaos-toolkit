"""Integration tests for the live chaos run path.

These tests verify that:
- live-sampled observations feed into baseline capture and abort evaluation
- run_chaos_live_flow() produces the expected artifact layout and summary
- the live runner handles Toxiproxy failures cleanly
"""

import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from toolkit.chaos.contracts import ChaosRunStatus
from toolkit.chaos.monitoring import (
    ExperimentWindowStatus,
    capture_live_baseline,
    collect_live_experiment_observations,
    evaluate_abort_thresholds,
)
from toolkit.chaos.runner import run_chaos_live_flow
from toolkit.chaos.toxiproxy import ToxiproxyRequestError
from toolkit.config.models import AppConfig, ChaosProfile, ChaosProfileRegistry
from toolkit.core.exits import ExitCode


def _build_app() -> AppConfig:
    return AppConfig.model_validate(
        {
            "id": "live-test-app",
            "environment": "local",
            "base_url": "http://localhost:9090",
            "host_targets": ["localhost"],
            "target_allowlist": ["localhost"],
            "auth": {"method": "none"},
            "health_endpoint": "/healthz",
            "enabled_modules": ["chaos"],
        }
    )


class LiveMonitoringIntegrationTests(unittest.TestCase):
    def test_live_baseline_feeds_into_abort_evaluation(self) -> None:
        """Verify that a live baseline + live experiment observations
        produce a valid ExperimentAssessment via evaluate_abort_thresholds.
        """
        app = _build_app()

        def healthy_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=200, request=request)

        with httpx.Client(
            transport=httpx.MockTransport(healthy_handler)
        ) as client:
            baseline = capture_live_baseline(
                app=app,
                duration_seconds=2,
                interval_seconds=1.0,
                client=client,
            )
            experiment_observations = collect_live_experiment_observations(
                app=app,
                duration_seconds=2,
                interval_seconds=1.0,
                client=client,
            )

        assessment = evaluate_abort_thresholds(
            baseline=baseline,
            observations=experiment_observations,
            consecutive_health_failures_threshold=3,
        )

        self.assertEqual(assessment.status, ExperimentWindowStatus.PASSED)
        self.assertFalse(assessment.aborted)
        self.assertFalse(assessment.resilience_failure)

    def test_live_experiment_abort_on_health_failure(self) -> None:
        """Verify that live unhealthy observations trigger abort and produce
        structured evidence compatible with the normalized result contract.
        """
        app = _build_app()

        def healthy_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=200, request=request)

        def unhealthy_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=503,
                text="service unavailable",
                request=request,
            )

        with httpx.Client(
            transport=httpx.MockTransport(healthy_handler)
        ) as client:
            baseline = capture_live_baseline(
                app=app,
                duration_seconds=2,
                interval_seconds=1.0,
                client=client,
            )

        with httpx.Client(
            transport=httpx.MockTransport(unhealthy_handler)
        ) as client:
            experiment_observations = collect_live_experiment_observations(
                app=app,
                duration_seconds=2,
                interval_seconds=1.0,
                client=client,
            )

        assessment = evaluate_abort_thresholds(
            baseline=baseline,
            observations=experiment_observations,
            consecutive_health_failures_threshold=2,
        )

        self.assertEqual(assessment.status, ExperimentWindowStatus.ABORTED)
        self.assertTrue(assessment.aborted)
        self.assertTrue(assessment.resilience_failure)
        self.assertGreaterEqual(len(assessment.evidence), 1)
        self.assertEqual(assessment.evidence[0].kind, "health")
        self.assertIn(
            "consecutive_failures",
            assessment.evidence[0].values,
        )


def _build_chaos_profile() -> ChaosProfile:
    registry = ChaosProfileRegistry.model_validate(
        {
            "profiles": [
                {
                    "name": "live-latency-test",
                    "target_service": "payments-api",
                    "fault_type": "latency",
                    "baseline_duration_seconds": 2,
                    "experiment_duration_seconds": 2,
                    "abort_thresholds": {
                        "consecutive_health_failures": 2,
                        "max_error_rate": 0.10,
                    },
                    "rollback": {"method": "immediate"},
                }
            ]
        }
    )
    return registry.profiles[0]


class LiveChaosRunnerIntegrationTests(unittest.TestCase):
    """Verify that run_chaos_live_flow produces the expected artifacts."""

    def test_live_run_writes_all_expected_artifacts(self) -> None:
        app = _build_app()
        profile = _build_chaos_profile()

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.chaos.runner.ChaosExecutionService"
                ) as MockService,
                patch(
                    "toolkit.chaos.runner.capture_live_baseline"
                ) as mock_baseline,
                patch(
                    "toolkit.chaos.runner.collect_live_experiment_observations"
                ) as mock_experiment,
            ):
                # Mock execution service (preflight, inject, rollback).
                service_instance = MockService.return_value
                service_instance.operations = []

                from toolkit.chaos.toxiproxy import ToxiproxyFaultHandle

                service_instance.preflight.return_value = None
                service_instance.inject_fault.return_value = (
                    ToxiproxyFaultHandle(
                        proxy_name="payments-api",
                        fault_type="latency",
                        rollback_action="remove_toxic",
                        toxic_name="toolkit-payments-api-latency",
                    )
                )
                service_instance.rollback_fault.return_value = None
                service_instance.close.return_value = None

                # Mock monitoring: all healthy.
                from toolkit.chaos.monitoring import (
                    HealthObservation,
                    MonitoringObservation,
                    SteadyStateBaseline,
                )

                when = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
                obs = MonitoringObservation(
                    observed_at=when,
                    health=HealthObservation(
                        url="http://localhost:9090/healthz",
                        observed_at=when,
                        healthy=True,
                        status_code=200,
                        response_time_ms=50.0,
                    ),
                )
                mock_baseline.return_value = SteadyStateBaseline(
                    app_id=app.id,
                    environment=app.environment,
                    started_at=when,
                    finished_at=when,
                    observation_count=2,
                    healthy_observation_count=2,
                    average_response_time_ms=50.0,
                    max_response_time_ms=55.0,
                    max_error_rate=None,
                    summary="Captured baseline.",
                    observations=(obs, obs),
                )
                mock_experiment.return_value = (obs, obs)

                summary = run_chaos_live_flow(
                    project_root=project_root,
                    app=app,
                    profile=profile,
                    when=when,
                )

            run_dir = project_root / "outputs" / summary.run_id
            self.assertTrue(
                (run_dir / "manifest.json").is_file()
            )
            self.assertTrue(
                (run_dir / "normalized" / "findings.json").is_file()
            )
            self.assertTrue(
                (run_dir / "reports" / "executive-summary.md").is_file()
            )
            self.assertTrue(
                (run_dir / "raw" / "chaos" / "orchestration-actions.json").is_file()
            )

        self.assertEqual(summary.status, ChaosRunStatus.SUCCESS)
        self.assertEqual(summary.exit_code, ExitCode.SUCCESS)
        self.assertTrue(summary.baseline_captured)
        self.assertTrue(summary.rollback_attempted)
        self.assertFalse(summary.aborted)

    def test_live_run_exits_2_when_toxiproxy_is_unreachable(self) -> None:
        app = _build_app()
        profile = _build_chaos_profile()

        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.chaos.runner.ChaosExecutionService"
            ) as MockService:
                service_instance = MockService.return_value
                service_instance.operations = []
                service_instance.preflight.side_effect = (
                    ToxiproxyRequestError(
                        operation="preflight",
                        detail="connection refused",
                    )
                )
                service_instance.close.return_value = None

                summary = run_chaos_live_flow(
                    project_root=project_root,
                    app=app,
                    profile=profile,
                    when=datetime(2026, 4, 1, tzinfo=UTC),
                )

        self.assertEqual(summary.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertEqual(summary.status, ChaosRunStatus.FAILED)
        self.assertIn("connection refused", summary.error_detail)
