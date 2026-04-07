"""Chaos orchestration contract types.

This module locks the chaos runner behavior so planner, monitoring, locking,
and CLI wiring all target one contract. Both fixture-backed and live execution
flows must satisfy every contract defined here.

Live execution contract
-----------------------
A live chaos run follows this lifecycle in order:

1. validate app, environment, and chaos profile
2. build one deterministic chaos experiment plan
3. acquire the per-app operator-host lock
4. preflight the Toxiproxy runtime and target proxy
5. capture a live steady-state baseline from health and optional metrics
6. inject exactly one reversible proxy fault via Toxiproxy
7. monitor live observations during the experiment window
8. abort on threshold breach
9. always attempt rollback
10. persist artifacts and rebuild the Markdown summary

Exit-code contract (stable)
----------------------------
- 0: experiment completed and resilience held within thresholds
- 1: abort-threshold breach or resilience failure
- 2: config error, missing Toxiproxy runtime, missing proxy, runtime failure,
     rollback failure, or lock contention

Safety invariants
-----------------
- No fault injection without health monitoring and rollback config.
  ensure_chaos_contract_preconditions() rejects missing health_endpoint
  and missing rollback_method before any experiment starts.
- One active experiment per app at a time. The filesystem lock under
  .toolkit-locks/chaos/ prevents concurrent experiments on the same
  app/environment from the same operator host.
- Rollback always attempted. The runner finally block attempts rollback
  on success, abort, timeout, and general error paths. A failed rollback
  escalates to exit code 2.
- controlled_restart remains rejected. The fault type is schema-reserved
  but ensure_chaos_contract_preconditions() raises ValueError until a
  dedicated safe implementation exists.
- packet_loss stays fail-closed. The Toxiproxy HTTP API does not expose
  a first-party packet-loss toxic. build_toxiproxy_fault_request() raises
  UnsupportedToxiproxyFaultError until a safe live mapping exists.

Fixture-versus-live boundary
------------------------------
- Fixture-backed flow: reads pre-recorded observation files and uses a
  non-networked FixtureToxiproxyController. No Toxiproxy runtime or live
  target required. Used for onboarding, offline testing, and CI.
- Live execution flow: connects to a real Toxiproxy API, captures live
  health/metrics observations, and injects real faults. Requires a running
  Toxiproxy server and a live target behind a configured proxy.
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

LIVE_CHAOS_RUN_LIFECYCLE: tuple[str, ...] = (
    "validate app, environment, and chaos profile",
    "build one deterministic chaos experiment plan",
    "acquire the per-app operator-host lock",
    "preflight the Toxiproxy runtime and target proxy",
    "capture a live steady-state baseline from health and optional metrics",
    "inject exactly one reversible proxy fault via Toxiproxy",
    "monitor live observations during the experiment window",
    "abort on threshold breach",
    "always attempt rollback",
    "persist artifacts and rebuild the Markdown summary",
)

PACKET_LOSS_FAIL_CLOSED_REASON: str = (
    "packet_loss is schema-supported but fail-closed at runtime because the "
    "Toxiproxy HTTP API does not expose a first-party packet-loss toxic. "
    "This fault type will remain rejected until a safe live mapping exists."
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
        raise ValueError("Chaos runs require rollback configuration before any fault can start.")

    if fault_type in RESERVED_UNIMPLEMENTED_CHAOS_FAULT_TYPES:
        raise ValueError(
            "Fault type 'controlled_restart' is reserved but not implemented for chaos runs."
        )

    if fault_type not in SUPPORTED_CHAOS_FAULT_TYPES:
        raise ValueError(f"Unsupported chaos fault type: {fault_type}")
