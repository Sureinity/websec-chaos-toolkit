import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.chaos.edge_runtime import (
    EDGE_CHAOS_DEFAULT_PROXY_PORT,
    EDGE_CHAOS_PROXY_HOST,
    EDGE_CHAOS_PROXY_NAME_PREFIX,
    EDGE_CHAOS_RUNTIME_BACKEND,
    EDGE_CHAOS_SUPPORTED_FAULT_TYPES,
    build_edge_chaos_proxy_plan,
    inspect_edge_chaos_runtime_readiness,
)


class EdgeChaosRuntimeTests(unittest.TestCase):
    def test_build_edge_chaos_proxy_plan_uses_local_proxy_origin(self) -> None:
        plan = build_edge_chaos_proxy_plan(
            "http://127.0.0.1:8000/app?view=full",
            fault_type="latency",
        )

        self.assertEqual(plan.app.id, "adhoc-127-0-0-1-8000")
        self.assertEqual(plan.app.enabled_modules, ["chaos"])
        self.assertEqual(plan.fault_type, "latency")
        self.assertEqual(
            plan.proxy_name,
            f"{EDGE_CHAOS_PROXY_NAME_PREFIX}-adhoc-127-0-0-1-8000",
        )
        self.assertEqual(plan.requested_url, "http://127.0.0.1:8000/app?view=full")
        self.assertEqual(plan.upstream_origin, "http://127.0.0.1:8000")
        self.assertEqual(
            plan.proxy_origin,
            f"http://{EDGE_CHAOS_PROXY_HOST}:{EDGE_CHAOS_DEFAULT_PROXY_PORT}",
        )
        self.assertEqual(
            plan.healthcheck_url,
            f"http://{EDGE_CHAOS_PROXY_HOST}:{EDGE_CHAOS_DEFAULT_PROXY_PORT}/",
        )

    def test_build_edge_chaos_proxy_plan_rejects_unknown_faults(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported edge-chaos fault type"):
            build_edge_chaos_proxy_plan(
                "http://127.0.0.1:8000",
                fault_type="packet_loss",  # type: ignore[arg-type]
            )

    def test_build_edge_chaos_proxy_plan_rejects_invalid_proxy_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "proxy_port"):
            build_edge_chaos_proxy_plan(
                "http://127.0.0.1:8000",
                proxy_port=70000,
            )

    def test_supported_fault_types_match_safe_edge_contract(self) -> None:
        self.assertEqual(
            EDGE_CHAOS_SUPPORTED_FAULT_TYPES,
            ("latency", "bandwidth", "timeout", "connection_refused"),
        )

    def test_inspect_edge_chaos_runtime_readiness_reports_missing_docker(self) -> None:
        with patch(
            "toolkit.chaos.edge_runtime.find_binary",
            return_value=None,
        ):
            readiness = inspect_edge_chaos_runtime_readiness()

        self.assertFalse(readiness.ready)
        self.assertIsNone(readiness.backend)
        self.assertIn("docker binary was not found on PATH", readiness.detail)

    def test_inspect_edge_chaos_runtime_readiness_reports_future_container_backend(self) -> None:
        with patch(
            "toolkit.chaos.edge_runtime.find_binary",
            return_value=Path("/usr/bin/docker"),
        ):
            readiness = inspect_edge_chaos_runtime_readiness()

        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.backend, EDGE_CHAOS_RUNTIME_BACKEND)
        self.assertEqual(readiness.binary, "/usr/bin/docker")
        self.assertIn("not implemented yet", readiness.detail)


if __name__ == "__main__":
    unittest.main()
