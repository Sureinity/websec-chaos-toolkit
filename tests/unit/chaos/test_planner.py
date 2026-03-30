import unittest

from toolkit.config.models import AppConfig, ChaosProfileRegistry
from toolkit.chaos.planner import build_chaos_experiment_plan


class ChaosPlannerTests(unittest.TestCase):
    def test_build_chaos_experiment_plan_returns_expected_fields(self) -> None:
        app = build_app_config()
        profile = build_chaos_profile()

        plan = build_chaos_experiment_plan(
            app=app,
            profile=profile,
        )

        self.assertEqual(plan.app_id, "sample-app")
        self.assertEqual(plan.environment, "local")
        self.assertEqual(plan.profile, "dependency-latency-baseline")
        self.assertEqual(plan.target_service, "payments-api")
        self.assertEqual(plan.fault_type, "latency")
        self.assertEqual(plan.baseline_duration_seconds, 30)
        self.assertEqual(plan.experiment_duration_seconds, 60)
        self.assertEqual(plan.health_endpoint, "/healthz")
        self.assertEqual(plan.rollback_method, "remove-toxics")
        self.assertEqual(plan.consecutive_health_failures, 2)
        self.assertEqual(plan.max_error_rate, 0.05)

    def test_build_chaos_experiment_plan_rejects_app_without_chaos_enabled(self) -> None:
        app = build_app_config(enabled_modules=["pentest"])
        profile = build_chaos_profile()

        with self.assertRaisesRegex(ValueError, "does not enable the chaos module"):
            build_chaos_experiment_plan(
                app=app,
                profile=profile,
            )

    def test_build_chaos_experiment_plan_requires_health_monitoring(self) -> None:
        app = build_app_config().model_copy(update={"health_endpoint": " "})
        profile = build_chaos_profile()

        with self.assertRaisesRegex(ValueError, "health_endpoint"):
            build_chaos_experiment_plan(
                app=app,
                profile=profile,
            )

    def test_build_chaos_experiment_plan_requires_rollback_configuration(self) -> None:
        profile = build_chaos_profile()
        invalid_profile = profile.model_copy(
            update={"rollback": profile.rollback.model_copy(update={"method": " "})}
        )

        with self.assertRaisesRegex(ValueError, "rollback"):
            build_chaos_experiment_plan(
                app=build_app_config(),
                profile=invalid_profile,
            )

    def test_build_chaos_experiment_plan_rejects_reserved_fault_type(self) -> None:
        invalid_profile = build_chaos_profile().model_copy(
            update={"fault_type": "controlled_restart"}
        )

        with self.assertRaisesRegex(ValueError, "controlled_restart"):
            build_chaos_experiment_plan(
                app=build_app_config(),
                profile=invalid_profile,
            )


def build_app_config(*, enabled_modules: list[str] | None = None) -> AppConfig:
    return AppConfig.model_validate(
        {
            "id": "sample-app",
            "environment": "local",
            "base_url": "https://sample.internal.test",
            "host_targets": ["sample.internal.test"],
            "target_allowlist": ["sample.internal.test"],
            "auth": {"method": "none"},
            "health_endpoint": "/healthz",
            "metrics": {"query": "http_requests_total"},
            "enabled_modules": enabled_modules or ["chaos"],
        }
    )


def build_chaos_profile():
    registry = ChaosProfileRegistry.model_validate(
        {
            "profiles": [
                {
                    "name": "dependency-latency-baseline",
                    "fault_type": "latency",
                    "target_service": "payments-api",
                    "baseline_duration_seconds": 30,
                    "experiment_duration_seconds": 60,
                    "abort_thresholds": {
                        "consecutive_health_failures": 2,
                        "max_error_rate": 0.05,
                    },
                    "rollback": {
                        "method": "remove-toxics",
                        "description": "Remove injected toxics from the proxy.",
                    },
                }
            ]
        }
    )
    return registry.profiles[0]
