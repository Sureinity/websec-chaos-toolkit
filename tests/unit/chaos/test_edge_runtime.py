import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from toolkit.chaos.edge_runtime import (
    EDGE_CHAOS_DEFAULT_PROXY_PORT,
    EDGE_CHAOS_PROXY_HOST,
    EDGE_CHAOS_PROXY_NAME_PREFIX,
    EDGE_CHAOS_RUNTIME_BACKEND,
    EDGE_CHAOS_SUPPORTED_FAULT_TYPES,
    EdgeChaosRuntimeError,
    ManagedEdgeChaosDockerRuntime,
    build_edge_chaos_monitoring_app,
    build_edge_chaos_profile,
    build_edge_chaos_proxy_plan,
    inspect_edge_chaos_runtime_readiness,
)
from toolkit.chaos.toxiproxy import ToxiproxyProxy


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

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.backend, EDGE_CHAOS_RUNTIME_BACKEND)
        self.assertEqual(readiness.binary, "/usr/bin/docker")
        self.assertIn("is ready", readiness.detail)

    def test_build_edge_chaos_monitoring_app_routes_health_through_proxy(self) -> None:
        plan = build_edge_chaos_proxy_plan("https://target.internal")
        monitoring_app = build_edge_chaos_monitoring_app(
            plan,
            prepared_proxy=type(
                "Prepared",
                (),
                {
                    "proxy_origin": "https://127.0.0.1:18080",
                },
            )(),
        )

        self.assertEqual(monitoring_app.id, plan.app.id)
        self.assertEqual(str(monitoring_app.base_url), "https://127.0.0.1:18080/")
        self.assertEqual(monitoring_app.target_allowlist, ["127.0.0.1"])
        self.assertEqual(monitoring_app.enabled_modules, ["chaos"])

    def test_build_edge_chaos_profile_targets_prepared_proxy_name(self) -> None:
        plan = build_edge_chaos_proxy_plan("http://127.0.0.1:8000", fault_type="timeout")

        profile = build_edge_chaos_profile(plan)

        self.assertEqual(profile.name, "adhoc-edge-timeout")
        self.assertEqual(profile.target_service, plan.proxy_name)
        self.assertEqual(profile.fault_type, "timeout")

    def test_managed_runtime_prepare_proxy_starts_container_and_creates_proxy(self) -> None:
        plan = build_edge_chaos_proxy_plan("http://127.0.0.1:8000")
        client = Mock()
        client.create_proxy.return_value = ToxiproxyProxy(
            name=plan.proxy_name,
            listen="127.0.0.1:18080",
            upstream="127.0.0.1:8000",
            enabled=True,
            toxics=(),
        )
        runtime = ManagedEdgeChaosDockerRuntime(client=client)

        with patch(
            "toolkit.chaos.edge_runtime.find_binary",
            return_value=Path("/usr/bin/docker"),
        ):
            with patch("toolkit.chaos.edge_runtime._run_docker_command") as run_docker:
                with patch("toolkit.chaos.edge_runtime.wait_for_toxiproxy_api") as wait_ready:
                    prepared = runtime.prepare_proxy(plan)

        run_docker.assert_called_once()
        wait_ready.assert_called_once()
        client.create_proxy.assert_called_once_with(
            proxy_name=plan.proxy_name,
            listen="127.0.0.1:18080",
            upstream="127.0.0.1:8000",
        )
        self.assertEqual(prepared.proxy_name, plan.proxy_name)
        self.assertEqual(prepared.proxy_origin, "http://127.0.0.1:18080")

    def test_managed_runtime_close_removes_proxy_and_stops_container(self) -> None:
        plan = build_edge_chaos_proxy_plan("http://127.0.0.1:8000")
        client = Mock()
        client.create_proxy.return_value = ToxiproxyProxy(
            name=plan.proxy_name,
            listen="127.0.0.1:18080",
            upstream="127.0.0.1:8000",
            enabled=True,
            toxics=(),
        )
        runtime = ManagedEdgeChaosDockerRuntime(client=client)

        with patch(
            "toolkit.chaos.edge_runtime.find_binary",
            return_value=Path("/usr/bin/docker"),
        ):
            with patch("toolkit.chaos.edge_runtime._run_docker_command"):
                with patch("toolkit.chaos.edge_runtime.wait_for_toxiproxy_api"):
                    runtime.prepare_proxy(plan)
                runtime.close()

        client.delete_proxy.assert_called_once_with(plan.proxy_name)

    def test_managed_runtime_requires_docker_for_prepare(self) -> None:
        runtime = ManagedEdgeChaosDockerRuntime(client=Mock())
        with patch(
            "toolkit.chaos.edge_runtime.find_binary",
            return_value=None,
        ):
            with self.assertRaisesRegex(EdgeChaosRuntimeError, "edge-chaos requires Docker"):
                runtime.prepare_proxy(build_edge_chaos_proxy_plan("http://127.0.0.1:8000"))


if __name__ == "__main__":
    unittest.main()
