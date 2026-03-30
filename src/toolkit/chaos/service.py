"""Chaos fixture service helpers and request models."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from toolkit.chaos.contracts import SupportedChaosFaultType
from toolkit.chaos.toxiproxy import (
    ToxiproxyFaultHandle,
    ToxiproxyProxyNotFoundError,
    build_toxiproxy_fault_request,
)

DEFAULT_CHAOS_FIXTURE_SCENARIOS = {
    "dependency-latency-baseline": ("tests", "fixtures", "chaos", "passing-latency"),
}


@dataclass(slots=True, frozen=True)
class ChaosRunRequest:
    """A normalized request to run a chaos profile once."""

    app_id: str
    environment: str
    profile: str


@dataclass(slots=True, frozen=True)
class ChaosFixturePaths:
    """Fixture-backed monitoring observation inputs for one chaos run."""

    baseline_observations_path: Path
    experiment_observations_path: Path


def default_fixture_paths(project_root: Path, *, profile_name: str) -> ChaosFixturePaths:
    """Return the default fixture scenario paths for a supported chaos profile."""

    if profile_name not in DEFAULT_CHAOS_FIXTURE_SCENARIOS:
        raise FileNotFoundError(
            f"No fixture-backed chaos scenario is defined for profile {profile_name!r}."
        )

    scenario_root = project_root.joinpath(*DEFAULT_CHAOS_FIXTURE_SCENARIOS[profile_name])
    return ChaosFixturePaths(
        baseline_observations_path=scenario_root / "baseline-observations.json",
        experiment_observations_path=scenario_root / "experiment-observations.json",
    )


def default_fault_attributes(fault_type: SupportedChaosFaultType) -> dict[str, int | float]:
    """Return conservative default fault attributes for fixture-backed runs."""

    if fault_type == "latency":
        return {"latency_ms": 250, "jitter_ms": 25}
    if fault_type == "bandwidth":
        return {"rate_kbps": 128}
    if fault_type == "timeout":
        return {"timeout_ms": 1000}
    if fault_type == "connection_refused":
        return {}
    if fault_type == "packet_loss":
        return {"rate_percent": 10}
    raise ValueError(f"Unsupported chaos fault type: {fault_type}")


@dataclass(slots=True)
class FixtureToxiproxyController:
    """Non-networked Toxiproxy-like controller for fixture-backed chaos runs."""

    operations: list[dict[str, object]] = field(default_factory=list)
    fail_on_inject: Exception | None = None
    fail_on_rollback: Exception | None = None
    known_proxies: set[str] = field(default_factory=set)

    def inject_fault(
        self,
        *,
        proxy_name: str,
        fault_type: SupportedChaosFaultType,
        attributes: Mapping[str, int | float] | None = None,
    ) -> ToxiproxyFaultHandle:
        """Validate and record a fixture-backed fault injection."""

        if self.known_proxies and proxy_name not in self.known_proxies:
            raise ToxiproxyProxyNotFoundError(proxy_name=proxy_name)
        if self.fail_on_inject is not None:
            raise self.fail_on_inject

        request = build_toxiproxy_fault_request(
            proxy_name=proxy_name,
            fault_type=fault_type,
            attributes=attributes,
        )
        self.operations.append(
            {
                "action": "inject_fault",
                "proxy_name": proxy_name,
                "fault_type": fault_type,
                "operation": request.operation,
                "rollback_action": request.rollback_action,
                "payload": request.payload,
            }
        )
        return ToxiproxyFaultHandle(
            proxy_name=proxy_name,
            fault_type=fault_type,
            rollback_action=request.rollback_action,
            toxic_name=request.toxic_name,
            toxic_type=request.toxic_type,
        )

    def rollback_fault(self, handle: ToxiproxyFaultHandle) -> None:
        """Record a fixture-backed rollback attempt."""

        self.operations.append(
            {
                "action": "rollback_fault",
                "proxy_name": handle.proxy_name,
                "fault_type": handle.fault_type,
                "rollback_action": handle.rollback_action,
                "toxic_name": handle.toxic_name,
            }
        )
        if self.fail_on_rollback is not None:
            raise self.fail_on_rollback
