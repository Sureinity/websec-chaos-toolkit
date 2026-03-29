"""Shared helpers for deterministic finding normalization."""

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import cast

from toolkit.results.models import Confidence, NormalizedResult, ResultTimestamps, Severity


def build_result_timestamps(
    *,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ResultTimestamps:
    """Build a stable timestamp payload for normalized results."""

    return ResultTimestamps(
        started_at=started_at or datetime.now(UTC),
        finished_at=finished_at,
    )


def normalize_severity(
    value: object,
    *,
    mapping: Mapping[object, str] | None = None,
    default: str = "info",
) -> Severity:
    """Normalize vendor-specific severity values into the shared severity enum."""

    normalized = _normalize_with_mapping(value, mapping=mapping, default=default)
    return cast(Severity, normalized)


def normalize_confidence(
    value: object,
    *,
    mapping: Mapping[object, str] | None = None,
    default: str = "medium",
) -> Confidence:
    """Normalize vendor-specific confidence values into the shared confidence enum."""

    normalized = _normalize_with_mapping(value, mapping=mapping, default=default)
    return cast(Confidence, normalized)


def normalize_evidence(values: Iterable[str]) -> list[str]:
    """Strip blank evidence entries and preserve stable order."""

    normalized_values: list[str] = []
    for value in values:
        stripped = value.strip()
        if stripped:
            normalized_values.append(stripped)
    return normalized_values


def build_normalized_result(
    *,
    app_id: str,
    environment: str,
    target: str,
    tool: str,
    category: str,
    severity: object,
    confidence: object,
    evidence: Iterable[str],
    remediation_summary: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    severity_mapping: Mapping[object, str] | None = None,
    confidence_mapping: Mapping[object, str] | None = None,
) -> NormalizedResult:
    """Build a normalized finding with shared defaults and cleanup."""

    return NormalizedResult(
        app_id=app_id,
        environment=environment,
        target=target,
        tool=tool,
        category=category,
        severity=normalize_severity(severity, mapping=severity_mapping),
        confidence=normalize_confidence(confidence, mapping=confidence_mapping),
        evidence=normalize_evidence(evidence),
        remediation_summary=remediation_summary.strip(),
        timestamps=build_result_timestamps(
            started_at=started_at,
            finished_at=finished_at,
        ),
    )


def _normalize_with_mapping(
    value: object,
    *,
    mapping: Mapping[object, str] | None,
    default: str,
) -> str:
    if mapping is not None and value in mapping:
        return mapping[value]

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized:
            return normalized

    return default
