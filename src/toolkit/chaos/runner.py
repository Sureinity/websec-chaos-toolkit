"""Chaos orchestration runner.

Two execution modes are provided:

- run_chaos_fixture_flow: reads pre-recorded observation files and uses a
  non-networked FixtureToxiproxyController. No Toxiproxy runtime or live
  target required. Used for onboarding, offline testing, and CI.

- run_chaos_live_flow: connects to a real Toxiproxy API, captures live
  health/metrics observations, and injects real faults. Requires a running
  Toxiproxy server and a live target behind a configured proxy.

Both flows preserve the same artifact layout, normalized result contract,
manifest schema, and exit-code contract.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx

from toolkit.auth.bootstrap import resolve_auth_session
from toolkit.chaos.contracts import (
    ChaosExperimentPlan,
    ChaosRunStatus,
    ChaosRunSummary,
    SupportedChaosFaultType,
    determine_chaos_exit_code,
)
from toolkit.chaos.execution import ChaosExecutionService
from toolkit.chaos.locking import (
    ChaosLockAcquisitionError,
    ChaosRunLock,
    acquire_chaos_lock,
    release_chaos_lock,
)
from toolkit.chaos.monitoring import (
    ExperimentAssessment,
    MonitoringObservation,
    capture_live_baseline,
    capture_steady_state_baseline,
    collect_live_experiment_observations,
    evaluate_abort_thresholds,
    monitoring_observations_to_payload,
    read_monitoring_observations_from_path,
)
from toolkit.chaos.planner import build_chaos_experiment_plan
from toolkit.chaos.service import (
    ChaosFixturePaths,
    FixtureToxiproxyController,
    default_fault_attributes,
)
from toolkit.chaos.toxiproxy import ToxiproxyFaultHandle
from toolkit.config.models import AppConfig, ChaosProfile
from toolkit.core.exits import ExitCode
from toolkit.core.run_context import (
    RunRequest,
    RunStatus,
    prepare_run_context,
    write_run_manifest,
)
from toolkit.reports.builder import write_markdown_summary
from toolkit.results.io import write_normalized_results
from toolkit.results.models import NormalizedResult, ResultTimestamps


class ChaosFaultController(Protocol):
    """Runtime-facing fault controller used by the fixture-backed runner."""

    operations: list[dict[str, object]]

    def inject_fault(
        self,
        *,
        proxy_name: str,
        fault_type: SupportedChaosFaultType,
        attributes: Mapping[str, int | float] | None = None,
    ) -> ToxiproxyFaultHandle: ...

    def rollback_fault(self, handle: ToxiproxyFaultHandle) -> None: ...


ObservationLoader = Callable[[Path], tuple[MonitoringObservation, ...]]


def run_chaos_fixture_flow(
    *,
    project_root: Path,
    app: AppConfig,
    profile: ChaosProfile,
    fixture_paths: ChaosFixturePaths,
    environ: Mapping[str, str] | None = None,
    auth_client: httpx.Client | None = None,
    when: datetime | None = None,
    toxiproxy_controller: ChaosFaultController | None = None,
    load_observations: ObservationLoader = read_monitoring_observations_from_path,
) -> ChaosRunSummary:
    """Run the current fixture-backed chaos orchestration flow."""

    resolved_when = when or datetime.now(UTC)
    plan = build_chaos_experiment_plan(
        app=app,
        profile=profile,
    )
    context = prepare_run_context(
        project_root,
        RunRequest(
            app_id=app.id,
            environment=app.environment,
            profile=profile.name,
            modules=("chaos",),
        ),
        when=resolved_when,
    )

    resolve_auth_session(
        app,
        environ=environ,
        client=auth_client,
    )
    controller = toxiproxy_controller or FixtureToxiproxyController()
    raw_artifact_paths: list[Path] = []
    baseline_captured = False
    rollback_attempted = False
    findings: list[NormalizedResult] = []
    status = ChaosRunStatus.FAILED
    exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    aborted = False
    abort_reason: str | None = None
    error_detail: str | None = None
    injected_fault: ToxiproxyFaultHandle | None = None
    lock: ChaosRunLock | None = None
    experiment_assessment: ExperimentAssessment | None = None
    lock_key: str | None = None

    try:
        lock = acquire_chaos_lock(
            project_root,
            app_id=app.id,
            environment=app.environment,
        )
        lock_key = lock.key

        baseline_observations = load_observations(fixture_paths.baseline_observations_path)
        baseline_path = _write_json_artifact(
            context.raw_dir / "chaos" / "baseline-observations.json",
            monitoring_observations_to_payload(baseline_observations),
        )
        raw_artifact_paths.append(baseline_path)
        baseline = capture_steady_state_baseline(
            app_id=app.id,
            environment=app.environment,
            observations=baseline_observations,
        )
        baseline_captured = True

        injected_fault = controller.inject_fault(
            proxy_name=plan.target_service,
            fault_type=plan.fault_type,
            attributes=default_fault_attributes(plan.fault_type),
        )

        experiment_observations = load_observations(fixture_paths.experiment_observations_path)
        experiment_path = _write_json_artifact(
            context.raw_dir / "chaos" / "experiment-observations.json",
            monitoring_observations_to_payload(experiment_observations),
        )
        raw_artifact_paths.append(experiment_path)

        experiment_assessment = evaluate_abort_thresholds(
            baseline=baseline,
            observations=experiment_observations,
            consecutive_health_failures_threshold=plan.consecutive_health_failures,
            max_error_rate_threshold=plan.max_error_rate,
        )
        findings = _build_findings(
            app=app,
            plan=plan,
            assessment=experiment_assessment,
            default_started_at=baseline.started_at,
            default_finished_at=experiment_observations[-1].observed_at
            if experiment_observations
            else baseline.finished_at,
        )
        aborted = experiment_assessment.aborted
        abort_reason = _abort_reason(experiment_assessment)
        exit_code = determine_chaos_exit_code(
            resilience_failure=experiment_assessment.resilience_failure,
            failed=False,
        )
        status = (
            ChaosRunStatus.RESILIENCE_FAILURE
            if experiment_assessment.resilience_failure
            else ChaosRunStatus.SUCCESS
        )
    except ChaosLockAcquisitionError as exc:
        error_detail = str(exc)
        status = ChaosRunStatus.FAILED
        exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    except TimeoutError as exc:
        error_detail = str(exc) or "Chaos experiment monitoring timed out."
        status = ChaosRunStatus.FAILED
        exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    except Exception as exc:
        error_detail = str(exc)
        status = ChaosRunStatus.FAILED
        exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    finally:
        rollback_error: Exception | None = None
        if injected_fault is not None:
            rollback_attempted = True
            try:
                controller.rollback_fault(injected_fault)
            except Exception as exc:
                rollback_error = exc
                status = ChaosRunStatus.FAILED
                exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
                if error_detail is None:
                    error_detail = str(exc)
                else:
                    error_detail = f"{error_detail}; rollback failed: {exc}"

        if lock is not None:
            release_chaos_lock(lock)

        actions_artifact = _write_json_artifact(
            context.raw_dir / "chaos" / "orchestration-actions.json",
            _build_action_payload(
                plan=plan,
                lock_key=lock_key,
                rollback_attempted=rollback_attempted,
                rollback_failed=rollback_error is not None,
                controller_operations=getattr(controller, "operations", []),
                error_detail=error_detail,
            ),
        )
        raw_artifact_paths.append(actions_artifact)

        normalized_bundle_path = write_normalized_results(context, findings)
        report_path = write_markdown_summary(context.run_dir)
        write_run_manifest(
            context,
            start_time=resolved_when,
            end_time=_end_time(
                resolved_when=resolved_when,
                assessment=experiment_assessment,
            ),
            status=_manifest_status(exit_code),
            exit_code=int(exit_code),
        )

    return ChaosRunSummary(
        run_id=context.run_id,
        status=status,
        exit_code=exit_code,
        experiment_plan=plan,
        findings_count=len(findings),
        baseline_captured=baseline_captured,
        rollback_attempted=rollback_attempted,
        aborted=aborted,
        abort_reason=abort_reason,
        error_detail=error_detail,
        normalized_bundle_path=normalized_bundle_path,
        report_path=report_path,
        raw_artifact_paths=tuple(raw_artifact_paths),
    )


def run_chaos_live_flow(
    *,
    project_root: Path,
    app: AppConfig,
    profile: ChaosProfile,
    environ: Mapping[str, str] | None = None,
    auth_client: httpx.Client | None = None,
    monitoring_client: httpx.Client | None = None,
    when: datetime | None = None,
    toxiproxy_base_url: str = "http://127.0.0.1:8474",
) -> ChaosRunSummary:
    """Run a live chaos experiment using a real Toxiproxy runtime.

    Requires a running Toxiproxy server at toxiproxy_base_url and a live
    target behind a configured proxy matching profile.target_service.
    """
    resolved_when = when or datetime.now(UTC)
    plan = build_chaos_experiment_plan(app=app, profile=profile)
    context = prepare_run_context(
        project_root,
        RunRequest(
            app_id=app.id,
            environment=app.environment,
            profile=profile.name,
            modules=("chaos",),
        ),
        when=resolved_when,
    )
    resolve_auth_session(app, environ=environ, client=auth_client)

    service = ChaosExecutionService(base_url=toxiproxy_base_url)
    raw_artifact_paths: list[Path] = []
    baseline_captured = False
    rollback_attempted = False
    findings: list[NormalizedResult] = []
    status = ChaosRunStatus.FAILED
    exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    aborted = False
    abort_reason: str | None = None
    error_detail: str | None = None
    injected_fault: ToxiproxyFaultHandle | None = None
    lock: ChaosRunLock | None = None
    experiment_assessment: ExperimentAssessment | None = None
    lock_key: str | None = None

    try:
        lock = acquire_chaos_lock(
            project_root,
            app_id=app.id,
            environment=app.environment,
        )
        lock_key = lock.key

        service.preflight(proxy_name=plan.target_service)

        baseline = capture_live_baseline(
            app=app,
            duration_seconds=plan.baseline_duration_seconds,
            client=monitoring_client,
        )
        baseline_path = _write_json_artifact(
            context.raw_dir / "chaos" / "baseline-observations.json",
            monitoring_observations_to_payload(baseline.observations),
        )
        raw_artifact_paths.append(baseline_path)
        baseline_captured = True

        injected_fault = service.inject_fault(
            proxy_name=plan.target_service,
            fault_type=plan.fault_type,
        )

        experiment_observations = collect_live_experiment_observations(
            app=app,
            duration_seconds=plan.experiment_duration_seconds,
            client=monitoring_client,
        )
        experiment_path = _write_json_artifact(
            context.raw_dir / "chaos" / "experiment-observations.json",
            monitoring_observations_to_payload(experiment_observations),
        )
        raw_artifact_paths.append(experiment_path)

        experiment_assessment = evaluate_abort_thresholds(
            baseline=baseline,
            observations=experiment_observations,
            consecutive_health_failures_threshold=(
                plan.consecutive_health_failures
            ),
            max_error_rate_threshold=plan.max_error_rate,
        )
        findings = _build_findings(
            app=app,
            plan=plan,
            assessment=experiment_assessment,
            default_started_at=baseline.started_at,
            default_finished_at=(
                experiment_observations[-1].observed_at
                if experiment_observations
                else baseline.finished_at
            ),
        )
        aborted = experiment_assessment.aborted
        abort_reason = _abort_reason(experiment_assessment)
        exit_code = determine_chaos_exit_code(
            resilience_failure=experiment_assessment.resilience_failure,
            failed=False,
        )
        status = (
            ChaosRunStatus.RESILIENCE_FAILURE
            if experiment_assessment.resilience_failure
            else ChaosRunStatus.SUCCESS
        )
    except ChaosLockAcquisitionError as exc:
        error_detail = str(exc)
        status = ChaosRunStatus.FAILED
        exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    except TimeoutError as exc:
        error_detail = str(exc) or "Chaos experiment timed out."
        status = ChaosRunStatus.FAILED
        exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    except Exception as exc:
        error_detail = str(exc)
        status = ChaosRunStatus.FAILED
        exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
    finally:
        rollback_error: Exception | None = None
        if injected_fault is not None:
            rollback_attempted = True
            try:
                service.rollback_fault(injected_fault)
            except Exception as exc:
                rollback_error = exc
                status = ChaosRunStatus.FAILED
                exit_code = ExitCode.CONFIG_OR_RUNTIME_ERROR
                if error_detail is None:
                    error_detail = str(exc)
                else:
                    error_detail = (
                        f"{error_detail}; rollback failed: {exc}"
                    )

        service.close()

        if lock is not None:
            release_chaos_lock(lock)

        actions_artifact = _write_json_artifact(
            context.raw_dir / "chaos" / "orchestration-actions.json",
            _build_action_payload(
                plan=plan,
                lock_key=lock_key,
                rollback_attempted=rollback_attempted,
                rollback_failed=rollback_error is not None,
                controller_operations=service.operations,
                error_detail=error_detail,
            ),
        )
        raw_artifact_paths.append(actions_artifact)

        normalized_bundle_path = write_normalized_results(
            context, findings
        )
        report_path = write_markdown_summary(context.run_dir)
        write_run_manifest(
            context,
            start_time=resolved_when,
            end_time=_end_time(
                resolved_when=resolved_when,
                assessment=experiment_assessment,
            ),
            status=_manifest_status(exit_code),
            exit_code=int(exit_code),
        )

    return ChaosRunSummary(
        run_id=context.run_id,
        status=status,
        exit_code=exit_code,
        experiment_plan=plan,
        findings_count=len(findings),
        baseline_captured=baseline_captured,
        rollback_attempted=rollback_attempted,
        aborted=aborted,
        abort_reason=abort_reason,
        error_detail=error_detail,
        normalized_bundle_path=normalized_bundle_path,
        report_path=report_path,
        raw_artifact_paths=tuple(raw_artifact_paths),
    )


def _build_findings(
    *,
    app: AppConfig,
    plan: ChaosExperimentPlan,
    assessment: ExperimentAssessment,
    default_started_at: datetime,
    default_finished_at: datetime,
) -> list[NormalizedResult]:
    if not assessment.resilience_failure:
        return []

    evidence = [
        f"{item.summary}: {json.dumps(item.values, sort_keys=True)}" for item in assessment.evidence
    ]
    return [
        NormalizedResult(
            app_id=app.id,
            environment=app.environment,
            target=plan.target_service,
            tool="chaos",
            category="resilience_abort_threshold_breach",
            severity="high",
            confidence="high",
            evidence=evidence,
            remediation_summary=(
                "Review dependency resilience, fault thresholds, and rollback "
                "readiness before rerunning this experiment."
            ),
            timestamps=ResultTimestamps(
                started_at=default_started_at,
                finished_at=default_finished_at,
            ),
        )
    ]


def _abort_reason(assessment: ExperimentAssessment) -> str | None:
    if not assessment.evidence:
        return None
    return assessment.evidence[0].summary


def _write_json_artifact(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _build_action_payload(
    *,
    plan: ChaosExperimentPlan,
    lock_key: str | None,
    rollback_attempted: bool,
    rollback_failed: bool,
    controller_operations: Sequence[dict[str, object]],
    error_detail: str | None,
) -> dict[str, object]:
    return {
        "app_id": plan.app_id,
        "environment": plan.environment,
        "profile": plan.profile,
        "target_service": plan.target_service,
        "fault_type": plan.fault_type,
        "lock_key": lock_key,
        "rollback_attempted": rollback_attempted,
        "rollback_failed": rollback_failed,
        "error_detail": error_detail,
        "controller_operations": list(controller_operations),
    }


def _manifest_status(exit_code: ExitCode) -> RunStatus:
    if exit_code == ExitCode.CONFIG_OR_RUNTIME_ERROR:
        return RunStatus.FAILED
    return RunStatus.SUCCESS


def _end_time(
    *,
    resolved_when: datetime,
    assessment: ExperimentAssessment | None,
) -> datetime:
    if assessment is None or not assessment.observations:
        return resolved_when
    return assessment.observations[-1].observed_at
