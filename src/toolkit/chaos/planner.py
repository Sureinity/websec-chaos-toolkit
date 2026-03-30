"""Deterministic chaos experiment planning from validated config."""

from typing import cast

from toolkit.chaos.contracts import (
    ChaosExperimentPlan,
    SupportedChaosFaultType,
    ensure_chaos_contract_preconditions,
)
from toolkit.config.models import AppConfig, ChaosProfile


def build_chaos_experiment_plan(
    *,
    app: AppConfig,
    profile: ChaosProfile,
) -> ChaosExperimentPlan:
    """Build the deterministic experiment plan for one chaos run."""

    if "chaos" not in app.enabled_modules:
        raise ValueError(f"App {app.id!r} does not enable the chaos module.")

    ensure_chaos_contract_preconditions(
        health_endpoint=app.health_endpoint,
        rollback_method=profile.rollback.method,
        fault_type=profile.fault_type,
    )

    return ChaosExperimentPlan(
        app_id=app.id,
        environment=app.environment,
        profile=profile.name,
        target_service=profile.target_service,
        fault_type=cast(SupportedChaosFaultType, profile.fault_type),
        baseline_duration_seconds=profile.baseline_duration_seconds,
        experiment_duration_seconds=profile.experiment_duration_seconds,
        health_endpoint=app.health_endpoint,
        rollback_method=profile.rollback.method,
        consecutive_health_failures=profile.abort_thresholds.consecutive_health_failures,
        max_error_rate=profile.abort_thresholds.max_error_rate,
    )
