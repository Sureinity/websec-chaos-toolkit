import unittest
from pathlib import Path

from toolkit.chaos.contracts import (
    CHAOS_RUN_LIFECYCLE,
    RESERVED_UNIMPLEMENTED_CHAOS_FAULT_TYPES,
    SUPPORTED_CHAOS_FAULT_TYPES,
    ChaosExperimentPlan,
    ChaosRunStatus,
    ChaosRunSummary,
    determine_chaos_exit_code,
    ensure_chaos_contract_preconditions,
)
from toolkit.core.exits import ExitCode


class ChaosContractTests(unittest.TestCase):
    def test_determine_exit_code_returns_success_for_passing_experiment(self) -> None:
        exit_code = determine_chaos_exit_code(
            resilience_failure=False,
            failed=False,
        )

        self.assertEqual(exit_code, ExitCode.SUCCESS)

    def test_determine_exit_code_returns_failure_for_resilience_breach(self) -> None:
        exit_code = determine_chaos_exit_code(
            resilience_failure=True,
            failed=False,
        )

        self.assertEqual(exit_code, ExitCode.FINDINGS_OR_FAILURE)

    def test_determine_exit_code_returns_runtime_error_for_general_failures(self) -> None:
        exit_code = determine_chaos_exit_code(
            resilience_failure=False,
            failed=True,
        )

        self.assertEqual(exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)

    def test_lifecycle_records_baseline_fault_abort_rollback_and_artifacts(self) -> None:
        self.assertEqual(
            CHAOS_RUN_LIFECYCLE,
            (
                "validate app, environment, and chaos profile",
                "build one deterministic chaos experiment plan",
                "acquire the per-app operator-host lock",
                "capture a steady-state baseline from health monitoring",
                "inject exactly one reversible proxy fault",
                "monitor the experiment window for health and optional metrics",
                "abort on threshold breach",
                "attempt rollback",
                "persist artifacts and rebuild the Markdown summary",
            ),
        )

    def test_supported_fault_types_remain_safe_and_reversible(self) -> None:
        self.assertEqual(
            SUPPORTED_CHAOS_FAULT_TYPES,
            (
                "latency",
                "bandwidth",
                "packet_loss",
                "timeout",
                "connection_refused",
            ),
        )
        self.assertEqual(
            RESERVED_UNIMPLEMENTED_CHAOS_FAULT_TYPES,
            ("controlled_restart",),
        )

    def test_preconditions_require_health_monitoring(self) -> None:
        with self.assertRaisesRegex(ValueError, "health_endpoint"):
            ensure_chaos_contract_preconditions(
                health_endpoint="",
                rollback_method="remove-toxics",
                fault_type="latency",
            )

    def test_preconditions_require_rollback_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "rollback"):
            ensure_chaos_contract_preconditions(
                health_endpoint="/healthz",
                rollback_method=" ",
                fault_type="latency",
            )

    def test_preconditions_reject_controlled_restart(self) -> None:
        with self.assertRaisesRegex(ValueError, "controlled_restart"):
            ensure_chaos_contract_preconditions(
                health_endpoint="/healthz",
                rollback_method="remove-toxics",
                fault_type="controlled_restart",
            )

    def test_plan_and_summary_capture_one_fault_and_artifact_expectations(self) -> None:
        ensure_chaos_contract_preconditions(
            health_endpoint="/healthz",
            rollback_method="remove-toxics",
            fault_type="latency",
        )
        plan = ChaosExperimentPlan(
            app_id="sample-app",
            environment="local",
            profile="dependency-latency-baseline",
            target_service="payments-api",
            fault_type="latency",
            baseline_duration_seconds=30,
            experiment_duration_seconds=60,
            health_endpoint="/healthz",
            rollback_method="remove-toxics",
            consecutive_health_failures=2,
            max_error_rate=0.05,
        )
        summary = ChaosRunSummary(
            run_id="20260330-120000-deadbeef",
            status=ChaosRunStatus.RESILIENCE_FAILURE,
            exit_code=ExitCode.FINDINGS_OR_FAILURE,
            experiment_plan=plan,
            baseline_captured=True,
            rollback_attempted=True,
            aborted=True,
            abort_reason="health threshold breached",
            normalized_bundle_path=Path("outputs/run-1/normalized/findings.json"),
            report_path=Path("outputs/run-1/reports/executive-summary.md"),
            raw_artifact_paths=(Path("outputs/run-1/raw/chaos/event-log.json"),),
        )

        self.assertEqual(summary.experiment_plan.fault_type, "latency")
        self.assertTrue(summary.baseline_captured)
        self.assertTrue(summary.rollback_attempted)
        self.assertTrue(summary.aborted)
        self.assertEqual(summary.status, ChaosRunStatus.RESILIENCE_FAILURE)
