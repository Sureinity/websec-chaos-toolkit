"""Integration tests for the live chaos monitoring and abort evaluation path.

These tests verify that live-sampled observations can feed into the existing
capture_steady_state_baseline() and evaluate_abort_thresholds() functions
without changing the downstream contract (findings, evidence, report shape).
"""

import unittest
from datetime import UTC, datetime

import httpx

from toolkit.chaos.monitoring import (
    ExperimentWindowStatus,
    capture_live_baseline,
    collect_live_experiment_observations,
    evaluate_abort_thresholds,
)
from toolkit.config.models import AppConfig


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
