import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from toolkit.chaos.monitoring import (
    BaselineCaptureError,
    ExperimentWindowStatus,
    capture_live_baseline,
    capture_steady_state_baseline,
    collect_live_experiment_observations,
    collect_monitoring_observation,
    evaluate_abort_thresholds,
)
from toolkit.config.models import AppConfig

FIXED_TIME = datetime(2026, 3, 30, 4, 0, 0, tzinfo=UTC)
FIXTURE_ROOT = Path("tests/fixtures/chaos/monitoring")


class ChaosMonitoringTests(unittest.TestCase):
    def test_collect_monitoring_observation_health_only_mode_is_deterministic(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if (
                request.method == "GET"
                and str(request.url) == "https://sample.internal.test/healthz"
            ):
                return httpx.Response(
                    status_code=200,
                    text="ok",
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)

        observation = collect_monitoring_observation(
            build_app_config(metrics=None),
            client=client,
            when=FIXED_TIME,
        )

        self.assertEqual(observation.observed_at, FIXED_TIME)
        self.assertEqual(observation.health.url, "https://sample.internal.test/healthz")
        self.assertTrue(observation.health.healthy)
        self.assertEqual(observation.health.status_code, 200)
        self.assertGreaterEqual(observation.health.response_time_ms, 0.0)
        self.assertIsNone(observation.metrics)

    def test_collect_monitoring_observation_parses_metrics_text_endpoint(self) -> None:
        metrics_payload = (FIXTURE_ROOT / "metrics-exposition.txt").read_text(encoding="utf-8")

        def handler(request: httpx.Request) -> httpx.Response:
            if (
                request.method == "GET"
                and str(request.url) == "https://sample.internal.test/healthz"
            ):
                return httpx.Response(status_code=200, text="ok", request=request)
            if (
                request.method == "GET"
                and str(request.url) == "https://metrics.internal.example/metrics"
            ):
                return httpx.Response(status_code=200, text=metrics_payload, request=request)
            return httpx.Response(status_code=500, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)

        observation = collect_monitoring_observation(
            build_app_config(metrics={"endpoint": "https://metrics.internal.example/metrics"}),
            client=client,
            when=FIXED_TIME,
        )

        self.assertIsNotNone(observation.metrics)
        assert observation.metrics is not None
        self.assertEqual(observation.metrics.source, "text")
        self.assertEqual(observation.metrics.error_rate, 0.02)
        self.assertEqual(observation.metrics.query, None)

    def test_collect_monitoring_observation_parses_prometheus_query_metrics(self) -> None:
        metrics_payload = (FIXTURE_ROOT / "prometheus-query-success.json").read_text(
            encoding="utf-8"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if (
                request.method == "GET"
                and str(request.url) == "https://sample.internal.test/healthz"
            ):
                return httpx.Response(status_code=200, text="ok", request=request)
            if (
                request.method == "GET"
                and request.url.path == "/api/v1/query"
                and request.url.params.get("query") == "http_error_rate"
            ):
                return httpx.Response(status_code=200, text=metrics_payload, request=request)
            return httpx.Response(status_code=500, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)

        observation = collect_monitoring_observation(
            build_app_config(
                metrics={
                    "endpoint": "https://prometheus.internal.example/api/v1/query",
                    "query": "http_error_rate",
                }
            ),
            client=client,
            when=FIXED_TIME,
        )

        self.assertIsNotNone(observation.metrics)
        assert observation.metrics is not None
        self.assertEqual(observation.metrics.source, "prometheus_query_api")
        self.assertEqual(observation.metrics.error_rate, 0.07)
        self.assertEqual(observation.metrics.query, "http_error_rate")

    def test_capture_steady_state_baseline_requires_healthy_samples(self) -> None:
        unhealthy_observation = build_observation(
            offset_seconds=0,
            healthy=False,
        )

        with self.assertRaisesRegex(BaselineCaptureError, "healthy"):
            capture_steady_state_baseline(
                app_id="sample-app",
                environment="local",
                observations=(unhealthy_observation,),
            )

    def test_capture_steady_state_baseline_computes_summary_fields(self) -> None:
        observations = (
            build_observation(offset_seconds=0, response_time_ms=120.0, error_rate=0.01),
            build_observation(offset_seconds=10, response_time_ms=180.0, error_rate=0.02),
        )

        baseline = capture_steady_state_baseline(
            app_id="sample-app",
            environment="local",
            observations=observations,
        )

        self.assertEqual(baseline.app_id, "sample-app")
        self.assertEqual(baseline.environment, "local")
        self.assertEqual(baseline.observation_count, 2)
        self.assertEqual(baseline.healthy_observation_count, 2)
        self.assertEqual(baseline.average_response_time_ms, 150.0)
        self.assertEqual(baseline.max_response_time_ms, 180.0)
        self.assertEqual(baseline.max_error_rate, 0.02)
        self.assertEqual(
            baseline.summary,
            "Captured steady-state baseline from 2 healthy observations.",
        )

    def test_evaluate_abort_thresholds_passes_in_health_only_mode(self) -> None:
        baseline = capture_steady_state_baseline(
            app_id="sample-app",
            environment="local",
            observations=(build_observation(offset_seconds=0),),
        )

        assessment = evaluate_abort_thresholds(
            baseline=baseline,
            observations=(
                build_observation(offset_seconds=30, healthy=True),
                build_observation(offset_seconds=60, healthy=True),
            ),
            consecutive_health_failures_threshold=2,
            max_error_rate_threshold=None,
        )

        self.assertEqual(assessment.status, ExperimentWindowStatus.PASSED)
        self.assertFalse(assessment.aborted)
        self.assertFalse(assessment.resilience_failure)
        self.assertEqual(assessment.evidence, ())
        self.assertEqual(assessment.max_consecutive_health_failures, 0)

    def test_evaluate_abort_thresholds_aborts_after_consecutive_health_failures(self) -> None:
        baseline = capture_steady_state_baseline(
            app_id="sample-app",
            environment="local",
            observations=(build_observation(offset_seconds=0),),
        )

        assessment = evaluate_abort_thresholds(
            baseline=baseline,
            observations=(
                build_observation(
                    offset_seconds=30, healthy=False, status_code=503, detail="service unavailable"
                ),
                build_observation(
                    offset_seconds=60, healthy=False, status_code=503, detail="service unavailable"
                ),
            ),
            consecutive_health_failures_threshold=2,
            max_error_rate_threshold=None,
        )

        self.assertEqual(assessment.status, ExperimentWindowStatus.ABORTED)
        self.assertTrue(assessment.aborted)
        self.assertEqual(len(assessment.evidence), 1)
        self.assertEqual(assessment.evidence[0].kind, "health")
        self.assertEqual(assessment.evidence[0].values["consecutive_failures"], 2)
        self.assertEqual(assessment.max_consecutive_health_failures, 2)

    def test_evaluate_abort_thresholds_aborts_on_metrics_breach(self) -> None:
        baseline = capture_steady_state_baseline(
            app_id="sample-app",
            environment="local",
            observations=(build_observation(offset_seconds=0, error_rate=0.01),),
        )

        assessment = evaluate_abort_thresholds(
            baseline=baseline,
            observations=(
                build_observation(offset_seconds=30, error_rate=0.06),
                build_observation(offset_seconds=60, error_rate=0.04),
            ),
            consecutive_health_failures_threshold=2,
            max_error_rate_threshold=0.05,
        )

        self.assertEqual(assessment.status, ExperimentWindowStatus.ABORTED)
        self.assertTrue(assessment.aborted)
        self.assertEqual(len(assessment.evidence), 1)
        self.assertEqual(assessment.evidence[0].kind, "metrics")
        self.assertEqual(assessment.evidence[0].values["error_rate"], 0.06)
        self.assertEqual(assessment.max_observed_error_rate, 0.06)


def build_app_config(*, metrics: dict[str, str] | None = None) -> AppConfig:
    payload: dict[str, object] = {
        "id": "sample-app",
        "environment": "local",
        "base_url": "https://sample.internal.test",
        "host_targets": ["sample.internal.test"],
        "target_allowlist": ["sample.internal.test"],
        "auth": {"method": "none"},
        "health_endpoint": "/healthz",
        "enabled_modules": ["chaos"],
    }
    if metrics is not None:
        payload["metrics"] = metrics
    return AppConfig.model_validate(payload)


def build_observation(
    *,
    offset_seconds: int,
    healthy: bool = True,
    status_code: int = 200,
    response_time_ms: float = 100.0,
    error_rate: float | None = None,
    detail: str | None = None,
):
    observed_at = FIXED_TIME + timedelta(seconds=offset_seconds)
    metrics = None
    if error_rate is not None:
        from toolkit.chaos.monitoring import MetricsObservation

        metrics = MetricsObservation(
            url="https://metrics.internal.example/metrics",
            observed_at=observed_at,
            query=None,
            error_rate=error_rate,
            source="text",
            detail=None,
        )

    from toolkit.chaos.monitoring import HealthObservation, MonitoringObservation

    return MonitoringObservation(
        observed_at=observed_at,
        health=HealthObservation(
            url="https://sample.internal.test/healthz",
            observed_at=observed_at,
            healthy=healthy,
            status_code=status_code,
            response_time_ms=response_time_ms,
            detail=detail,
        ),
        metrics=metrics,
    )


class LiveBaselineTests(unittest.TestCase):
    """Tests for capture_live_baseline using mocked HTTP transport."""

    def test_capture_live_baseline_collects_healthy_observations(self) -> None:
        app = build_app_config()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=200, request=request)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            baseline = capture_live_baseline(
                app=app,
                duration_seconds=2,
                interval_seconds=1.0,
                client=client,
            )

        self.assertGreaterEqual(baseline.observation_count, 2)
        self.assertTrue(baseline.summary.startswith("Captured"))

    def test_capture_live_baseline_rejects_unhealthy_observations(self) -> None:
        app = build_app_config()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=503, request=request)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(BaselineCaptureError):
                capture_live_baseline(
                    app=app,
                    duration_seconds=1,
                    interval_seconds=1.0,
                    client=client,
                )


class LiveExperimentObservationTests(unittest.TestCase):
    """Tests for collect_live_experiment_observations."""

    def test_collects_observations_for_duration(self) -> None:
        app = build_app_config()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=200, request=request)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            observations = collect_live_experiment_observations(
                app=app,
                duration_seconds=3,
                interval_seconds=1.0,
                client=client,
            )

        self.assertGreaterEqual(len(observations), 3)
        self.assertTrue(all(obs.health.healthy for obs in observations))

    def test_collects_unhealthy_observations_without_error(self) -> None:
        app = build_app_config()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=503,
                text="service unavailable",
                request=request,
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            observations = collect_live_experiment_observations(
                app=app,
                duration_seconds=2,
                interval_seconds=1.0,
                client=client,
            )

        self.assertGreaterEqual(len(observations), 2)
        self.assertFalse(any(obs.health.healthy for obs in observations))
