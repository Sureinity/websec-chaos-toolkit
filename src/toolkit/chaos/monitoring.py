"""Health and metrics monitoring helpers for chaos experiments."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import httpx

from toolkit.config.models import AppConfig, MetricsConfig

MonitoringEvidenceKind = Literal["health", "metrics"]


class ExperimentWindowStatus(StrEnum):
    """Outcome states for one monitored experiment window."""

    PASSED = "passed"
    ABORTED = "aborted"


@dataclass(slots=True, frozen=True)
class MonitoringRequestError(RuntimeError):
    """Raised when monitoring data cannot be retrieved safely."""

    operation: str
    detail: str

    def __str__(self) -> str:
        return f"Monitoring request failed during {self.operation}: {self.detail}"


@dataclass(slots=True, frozen=True)
class MetricsParseError(RuntimeError):
    """Raised when a metrics endpoint response cannot be parsed deterministically."""

    detail: str

    def __str__(self) -> str:
        return f"Metrics response could not be parsed: {self.detail}"


@dataclass(slots=True, frozen=True)
class BaselineCaptureError(RuntimeError):
    """Raised when the steady-state baseline cannot be established."""

    detail: str

    def __str__(self) -> str:
        return f"Steady-state baseline capture failed: {self.detail}"


@dataclass(slots=True, frozen=True)
class HealthObservation:
    """One health-check observation sampled during baseline or experiment time."""

    url: str
    observed_at: datetime
    healthy: bool
    status_code: int | None
    response_time_ms: float
    detail: str | None = None


@dataclass(slots=True, frozen=True)
class MetricsObservation:
    """One metrics observation used for abort-threshold evaluation."""

    url: str
    observed_at: datetime
    query: str | None
    error_rate: float
    source: str
    detail: str | None = None


@dataclass(slots=True, frozen=True)
class MonitoringObservation:
    """One combined health and optional metrics observation."""

    observed_at: datetime
    health: HealthObservation
    metrics: MetricsObservation | None = None


@dataclass(slots=True, frozen=True)
class MonitoringEvidence:
    """Structured evidence suitable for later artifacts and reporting."""

    kind: MonitoringEvidenceKind
    observed_at: datetime
    summary: str
    values: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SteadyStateBaseline:
    """Aggregated baseline snapshot captured before fault injection."""

    app_id: str
    environment: str
    started_at: datetime
    finished_at: datetime
    observation_count: int
    healthy_observation_count: int
    average_response_time_ms: float
    max_response_time_ms: float
    max_error_rate: float | None
    summary: str
    observations: tuple[MonitoringObservation, ...]


@dataclass(slots=True, frozen=True)
class ExperimentAssessment:
    """Abort-threshold evaluation for one experiment observation window."""

    status: ExperimentWindowStatus
    aborted: bool
    resilience_failure: bool
    summary: str
    max_consecutive_health_failures: int
    max_observed_error_rate: float | None
    evidence: tuple[MonitoringEvidence, ...]
    observations: tuple[MonitoringObservation, ...]


def collect_monitoring_observation(
    app: AppConfig,
    *,
    client: httpx.Client | None = None,
    headers: Mapping[str, str] | None = None,
    cookies: Mapping[str, str] | None = None,
    when: datetime | None = None,
    timeout: float = 5.0,
) -> MonitoringObservation:
    """Collect one health sample and optional metrics sample for an app."""

    observed_at = when or datetime.now(UTC)
    if client is not None:
        return _collect_monitoring_observation(
            app,
            client=client,
            headers=headers,
            cookies=cookies,
            observed_at=observed_at,
        )

    with httpx.Client(follow_redirects=True, timeout=timeout) as managed_client:
        return _collect_monitoring_observation(
            app,
            client=managed_client,
            headers=headers,
            cookies=cookies,
            observed_at=observed_at,
        )


def capture_steady_state_baseline(
    *,
    app_id: str,
    environment: str,
    observations: Sequence[MonitoringObservation],
) -> SteadyStateBaseline:
    """Build a steady-state baseline from health-first monitoring samples."""

    if not observations:
        raise BaselineCaptureError("at least one monitoring observation is required")

    unhealthy = [observation for observation in observations if not observation.health.healthy]
    if unhealthy:
        raise BaselineCaptureError(
            "all baseline observations must be healthy before fault injection"
        )

    response_times = [observation.health.response_time_ms for observation in observations]
    error_rates = [
        observation.metrics.error_rate
        for observation in observations
        if observation.metrics is not None
    ]
    started_at = observations[0].observed_at
    finished_at = observations[-1].observed_at
    return SteadyStateBaseline(
        app_id=app_id,
        environment=environment,
        started_at=started_at,
        finished_at=finished_at,
        observation_count=len(observations),
        healthy_observation_count=len(observations),
        average_response_time_ms=sum(response_times) / len(response_times),
        max_response_time_ms=max(response_times),
        max_error_rate=max(error_rates) if error_rates else None,
        summary=(
            f"Captured steady-state baseline from {len(observations)} healthy observations."
        ),
        observations=tuple(observations),
    )


def evaluate_abort_thresholds(
    *,
    baseline: SteadyStateBaseline,
    observations: Sequence[MonitoringObservation],
    consecutive_health_failures_threshold: int,
    max_error_rate_threshold: float | None = None,
) -> ExperimentAssessment:
    """Evaluate experiment observations against the configured abort thresholds."""

    evidence: list[MonitoringEvidence] = []
    max_consecutive_health_failures = 0
    current_health_failures = 0
    max_observed_error_rate: float | None = baseline.max_error_rate

    for observation in observations:
        if observation.health.healthy:
            current_health_failures = 0
        else:
            current_health_failures += 1
            max_consecutive_health_failures = max(
                max_consecutive_health_failures,
                current_health_failures,
            )
            if current_health_failures >= consecutive_health_failures_threshold:
                evidence.append(
                    MonitoringEvidence(
                        kind="health",
                        observed_at=observation.observed_at,
                        summary="health checks breached the consecutive-failure threshold",
                        values={
                            "consecutive_failures": current_health_failures,
                            "threshold": consecutive_health_failures_threshold,
                            "status_code": observation.health.status_code,
                            "detail": observation.health.detail,
                        },
                    )
                )

        metrics = observation.metrics
        if metrics is not None:
            max_observed_error_rate = (
                metrics.error_rate
                if max_observed_error_rate is None
                else max(max_observed_error_rate, metrics.error_rate)
            )
            if (
                max_error_rate_threshold is not None
                and metrics.error_rate > max_error_rate_threshold
            ):
                evidence.append(
                    MonitoringEvidence(
                        kind="metrics",
                        observed_at=observation.observed_at,
                        summary="metrics breached the max_error_rate threshold",
                        values={
                            "error_rate": metrics.error_rate,
                            "threshold": max_error_rate_threshold,
                            "query": metrics.query,
                            "source": metrics.source,
                        },
                    )
                )

    aborted = bool(evidence)
    if aborted:
        summary = "Abort thresholds were breached during the experiment window."
        status = ExperimentWindowStatus.ABORTED
    else:
        summary = "No abort thresholds were breached during the experiment window."
        status = ExperimentWindowStatus.PASSED

    return ExperimentAssessment(
        status=status,
        aborted=aborted,
        resilience_failure=aborted,
        summary=summary,
        max_consecutive_health_failures=max_consecutive_health_failures,
        max_observed_error_rate=max_observed_error_rate,
        evidence=tuple(evidence),
        observations=tuple(observations),
    )


def read_monitoring_observations_from_path(path: Path) -> tuple[MonitoringObservation, ...]:
    """Load fixture-backed monitoring observations from stable JSON."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise MonitoringRequestError(
            operation=f"load monitoring observations from {path}",
            detail="fixture payload must be a JSON array",
        )
    return tuple(_parse_monitoring_observation(item) for item in payload)


def monitoring_observations_to_payload(
    observations: Sequence[MonitoringObservation],
) -> list[dict[str, object]]:
    """Serialize monitoring observations into stable JSON-ready payloads."""

    payload: list[dict[str, object]] = []
    for observation in observations:
        metrics_payload = None
        if observation.metrics is not None:
            metrics_payload = {
                "url": observation.metrics.url,
                "observed_at": _format_timestamp(observation.metrics.observed_at),
                "query": observation.metrics.query,
                "error_rate": observation.metrics.error_rate,
                "source": observation.metrics.source,
                "detail": observation.metrics.detail,
            }
        payload.append(
            {
                "observed_at": _format_timestamp(observation.observed_at),
                "health": {
                    "url": observation.health.url,
                    "observed_at": _format_timestamp(observation.health.observed_at),
                    "healthy": observation.health.healthy,
                    "status_code": observation.health.status_code,
                    "response_time_ms": observation.health.response_time_ms,
                    "detail": observation.health.detail,
                },
                "metrics": metrics_payload,
            }
        )
    return payload


def _collect_monitoring_observation(
    app: AppConfig,
    *,
    client: httpx.Client,
    headers: Mapping[str, str] | None,
    cookies: Mapping[str, str] | None,
    observed_at: datetime,
) -> MonitoringObservation:
    health_url = health_check_url(app)
    health = _collect_health_observation(
        health_url,
        client=client,
        headers=headers,
        cookies=cookies,
        observed_at=observed_at,
    )
    metrics = _collect_metrics_observation(
        app.metrics,
        client=client,
        headers=headers,
        cookies=cookies,
        observed_at=observed_at,
    )
    return MonitoringObservation(
        observed_at=observed_at,
        health=health,
        metrics=metrics,
    )


def health_check_url(app: AppConfig) -> str:
    """Return the absolute health-check URL for an app config."""

    return f"{str(app.base_url).rstrip('/')}{app.health_endpoint}"


def _collect_health_observation(
    url: str,
    *,
    client: httpx.Client,
    headers: Mapping[str, str] | None,
    cookies: Mapping[str, str] | None,
    observed_at: datetime,
) -> HealthObservation:
    started = perf_counter()
    try:
        response = client.get(
            url,
            headers=_build_request_headers(headers=headers, cookies=cookies),
        )
    except httpx.HTTPError as exc:
        return HealthObservation(
            url=url,
            observed_at=observed_at,
            healthy=False,
            status_code=None,
            response_time_ms=(perf_counter() - started) * 1000,
            detail=str(exc),
        )

    return HealthObservation(
        url=url,
        observed_at=observed_at,
        healthy=not response.is_error,
        status_code=response.status_code,
        response_time_ms=(perf_counter() - started) * 1000,
        detail=None if not response.is_error else response.text[:200],
    )


def _collect_metrics_observation(
    metrics_config: MetricsConfig | None,
    *,
    client: httpx.Client,
    headers: Mapping[str, str] | None,
    cookies: Mapping[str, str] | None,
    observed_at: datetime,
) -> MetricsObservation | None:
    if metrics_config is None:
        return None
    if metrics_config.endpoint is None:
        raise MonitoringRequestError(
            operation="collect metrics",
            detail="metrics.endpoint is required when metrics monitoring is configured",
        )

    url = str(metrics_config.endpoint)
    params = {"query": metrics_config.query} if metrics_config.query is not None else None

    try:
        response = client.get(
            url,
            params=params,
            headers=_build_request_headers(headers=headers, cookies=cookies),
        )
    except httpx.HTTPError as exc:
        raise MonitoringRequestError(
            operation="collect metrics",
            detail=str(exc),
        ) from exc

    if response.is_error:
        raise MonitoringRequestError(
            operation="collect metrics",
            detail=f"HTTP {response.status_code}",
        )

    error_rate, source = parse_error_rate_response(
        response.text,
        query=metrics_config.query,
    )
    return MetricsObservation(
        url=url,
        observed_at=observed_at,
        query=metrics_config.query,
        error_rate=error_rate,
        source=source,
        detail=None,
    )


def parse_error_rate_response(
    payload: str,
    *,
    query: str | None,
) -> tuple[float, str]:
    """Parse one error-rate response using the configured metrics mode."""

    if query is not None:
        return _parse_prometheus_query_response(payload), "prometheus_query_api"

    try:
        parsed = json.loads(payload)
    except ValueError:
        return _parse_text_error_rate(payload), "text"

    if isinstance(parsed, Mapping):
        try:
            return _parse_json_error_rate(parsed), "json"
        except MetricsParseError:
            return _parse_prometheus_query_payload(parsed), "prometheus_query_api"

    raise MetricsParseError("metrics response must be a JSON object or text exposition")


def _parse_json_error_rate(payload: Mapping[str, Any]) -> float:
    for key in ("error_rate", "value"):
        if key in payload:
            return _coerce_numeric(payload[key], detail=f"JSON field {key!r} must be numeric")
    raise MetricsParseError("JSON payload did not contain an 'error_rate' or 'value' field")


def _parse_prometheus_query_response(payload: str) -> float:
    try:
        parsed = json.loads(payload)
    except ValueError as exc:
        raise MetricsParseError("Prometheus query endpoint did not return valid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise MetricsParseError("Prometheus query response must be a JSON object")
    return _parse_prometheus_query_payload(parsed)


def _parse_prometheus_query_payload(payload: Mapping[str, Any]) -> float:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise MetricsParseError("Prometheus query response missing object field 'data'")
    results = data.get("result")
    if not isinstance(results, list) or not results:
        raise MetricsParseError("Prometheus query response missing vector results")
    first_result = results[0]
    if not isinstance(first_result, Mapping):
        raise MetricsParseError("Prometheus query vector entry must be an object")
    value = first_result.get("value")
    if not isinstance(value, list) or len(value) < 2:
        raise MetricsParseError("Prometheus query vector entry missing a value pair")
    return _coerce_numeric(value[1], detail="Prometheus query value must be numeric")


def _parse_text_error_rate(payload: str) -> float:
    candidates: list[tuple[str, float]] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        metric_name = parts[0].split("{", 1)[0]
        try:
            value = float(parts[-1])
        except ValueError:
            continue
        candidates.append((metric_name, value))

    if not candidates:
        raise MetricsParseError("text exposition did not contain any numeric samples")

    preferred = [
        value
        for name, value in candidates
        if name == "error_rate" or name.endswith("_error_rate")
    ]
    if preferred:
        return preferred[0]
    if len(candidates) == 1:
        return candidates[0][1]

    raise MetricsParseError(
        "text exposition contained multiple samples without an error_rate metric name"
    )


def _coerce_numeric(value: object, *, detail: str) -> float:
    if isinstance(value, bool):
        raise MetricsParseError(detail)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise MetricsParseError(detail) from exc
    raise MetricsParseError(detail)


def _build_request_headers(
    *,
    headers: Mapping[str, str] | None,
    cookies: Mapping[str, str] | None,
) -> dict[str, str]:
    request_headers = dict(headers or {})
    if cookies:
        request_headers["Cookie"] = "; ".join(
            f"{name}={value}" for name, value in cookies.items()
        )
    return request_headers


def _parse_monitoring_observation(payload: object) -> MonitoringObservation:
    if not isinstance(payload, Mapping):
        raise MonitoringRequestError(
            operation="parse monitoring observation",
            detail="each observation must be a JSON object",
        )
    health_payload = payload.get("health")
    if not isinstance(health_payload, Mapping):
        raise MonitoringRequestError(
            operation="parse monitoring observation",
            detail="observation.health must be a JSON object",
        )
    metrics_payload = payload.get("metrics")

    observed_at = _parse_timestamp(payload.get("observed_at"), field_name="observed_at")
    health_observed_at = _parse_timestamp(
        health_payload.get("observed_at"),
        field_name="health.observed_at",
    )
    health_status_code = health_payload.get("status_code")
    if health_status_code is not None and not isinstance(health_status_code, int):
        raise MonitoringRequestError(
            operation="parse monitoring observation",
            detail="health.status_code must be an integer or null",
        )
    health = HealthObservation(
        url=_require_string(health_payload.get("url"), field_name="health.url"),
        observed_at=health_observed_at,
        healthy=_require_bool(health_payload.get("healthy"), field_name="health.healthy"),
        status_code=health_status_code,
        response_time_ms=_coerce_numeric(
            health_payload.get("response_time_ms"),
            detail="health.response_time_ms must be numeric",
        ),
        detail=_optional_string(health_payload.get("detail"), field_name="health.detail"),
    )

    metrics = None
    if metrics_payload is not None:
        if not isinstance(metrics_payload, Mapping):
            raise MonitoringRequestError(
                operation="parse monitoring observation",
                detail="observation.metrics must be a JSON object or null",
            )
        metrics = MetricsObservation(
            url=_require_string(metrics_payload.get("url"), field_name="metrics.url"),
            observed_at=_parse_timestamp(
                metrics_payload.get("observed_at"),
                field_name="metrics.observed_at",
            ),
            query=_optional_string(metrics_payload.get("query"), field_name="metrics.query"),
            error_rate=_coerce_numeric(
                metrics_payload.get("error_rate"),
                detail="metrics.error_rate must be numeric",
            ),
            source=_require_string(metrics_payload.get("source"), field_name="metrics.source"),
            detail=_optional_string(metrics_payload.get("detail"), field_name="metrics.detail"),
        )

    return MonitoringObservation(
        observed_at=observed_at,
        health=health,
        metrics=metrics,
    )


def _parse_timestamp(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise MonitoringRequestError(
            operation="parse monitoring observation",
            detail=f"{field_name} must be a non-empty ISO 8601 string",
        )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise MonitoringRequestError(
            operation="parse monitoring observation",
            detail=f"{field_name} must be a valid ISO 8601 timestamp",
        ) from exc


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise MonitoringRequestError(
            operation="parse monitoring observation",
            detail=f"{field_name} must be a non-empty string",
        )
    return value


def _optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name=field_name)


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise MonitoringRequestError(
            operation="parse monitoring observation",
            detail=f"{field_name} must be a boolean",
        )
    return value
