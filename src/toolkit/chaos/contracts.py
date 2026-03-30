"""Chaos orchestration contract types.

This module locks the chaos runner behavior before the implementation lands, so
planner, monitoring, locking, and CLI wiring all target one contract.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal

from toolkit.core.exits import ExitCode

SupportedChaosFaultType = Literal[
    "latency",
    "bandwidth",
    "packet_loss",
    "timeout",
    "connection_refused",
]
ReservedChaosFaultType = Literal["controlled_restart"]
ChaosFaultType = SupportedChaosFaultType | ReservedChaosFaultType

SUPPORTED_CHAOS_FAULT_TYPES: tuple[SupportedChaosFaultType, ...] = (
    "latency",
    "bandwidth",
    "packet_loss",
    "timeout",
    "connection_refused",
)
RESERVED_UNIMPLEMENTED_CHAOS_FAULT_TYPES: tuple[ReservedChaosFaultType, ...] = (
    "controlled_restart",
)
CHAOS_RUN_LIFECYCLE: tuple[str, ...] = (
    "validate app, environment, and chaos profile",
    "build one deterministic chaos experiment plan",
    "acquire the per-app operator-host lock",
    "capture a steady-state baseline from health monitoring",
    "inject exactly one reversible proxy fault",
    "monitor the experiment window for health and optional metrics",
    "abort on threshold breach",
    "attempt rollback",
    "persist artifacts and rebuild the Markdown summary",
)


class ChaosRunStatus(StrEnum):
    """High-level outcome states for a chaos run."""

    SUCCESS = "success"
    RESILIENCE_FAILURE = "resilience_failure"
    FAILED = "failed"


@dataclass(slots=True, frozen=True)
class ChaosExperimentPlan:
    """Deterministic plan for one reversible chaos experiment."""

    app_id: str
    environment: str
    profile: str
    target_service: str
    fault_type: SupportedChaosFaultType
    baseline_duration_seconds: int
    experiment_duration_seconds: int
    health_endpoint: str
    rollback_method: str
    consecutive_health_failures: int
    max_error_rate: float | None = None


@dataclass(slots=True, frozen=True)
class ChaosRunSummary:
    """Final orchestration summary returned by the future chaos runner."""

    run_id: str
    status: ChaosRunStatus
    exit_code: ExitCode
    experiment_plan: ChaosExperimentPlan
    baseline_captured: bool
    rollback_attempted: bool
    findings_count: int = 0
    aborted: bool = False
    abort_reason: str | None = None
    error_detail: str | None = None
    normalized_bundle_path: Path | None = None
    report_path: Path | None = None
    raw_artifact_paths: tuple[Path, ...] = field(default_factory=tuple)


def determine_chaos_exit_code(*, resilience_failure: bool, failed: bool) -> ExitCode:
    """Map chaos runner outcomes to the stable exit-code contract."""

    if failed:
        return ExitCode.CONFIG_OR_RUNTIME_ERROR
    if resilience_failure:
        return ExitCode.FINDINGS_OR_FAILURE
    return ExitCode.SUCCESS


def ensure_chaos_contract_preconditions(
    *,
    health_endpoint: str | None,
    rollback_method: str | None,
    fault_type: ChaosFaultType,
) -> None:
    """Fail closed when a requested experiment violates the locked contract."""

    normalized_health_endpoint = (health_endpoint or "").strip()
    if not normalized_health_endpoint:
        raise ValueError(
            "Chaos runs require app.health_endpoint so a steady-state baseline can be monitored."
        )

    normalized_rollback_method = (rollback_method or "").strip()
    if not normalized_rollback_method:
        raise ValueError(
            "Chaos runs require rollback configuration before any fault can start."
        )

    if fault_type in RESERVED_UNIMPLEMENTED_CHAOS_FAULT_TYPES:
        raise ValueError(
            "Fault type 'controlled_restart' is reserved but not implemented for chaos runs."
        )

    if fault_type not in SUPPORTED_CHAOS_FAULT_TYPES:
        raise ValueError(f"Unsupported chaos fault type: {fault_type}")
