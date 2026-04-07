"""Tests for the live Toxiproxy execution service."""

import json
import unittest
from pathlib import Path

import httpx

from toolkit.chaos.execution import ChaosExecutionService
from toolkit.chaos.toxiproxy import (
    ToxiproxyFaultHandle,
    ToxiproxyProxyNotFoundError,
    ToxiproxyProxyStateError,
    ToxiproxyRequestError,
)

FIXTURE_ROOT = Path("tests/fixtures/chaos/toxiproxy")


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _build_service(
    test_case: unittest.TestCase,
    handler,
) -> ChaosExecutionService:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    service = ChaosExecutionService.__new__(ChaosExecutionService)
    from toolkit.chaos.toxiproxy import ToxiproxyClient

    service._client = ToxiproxyClient(
        base_url="http://toxiproxy.internal",
        client=http_client,
    )
    service.operations = []
    test_case.addCleanup(http_client.close)
    return service


class PreflightTests(unittest.TestCase):
    def test_preflight_returns_proxy_when_server_is_reachable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json=_load_fixture("proxy-enabled.json"),
                request=request,
            )

        service = _build_service(self, handler)
        proxy = service.preflight(proxy_name="payments-api")

        self.assertEqual(proxy.name, "payments-api")
        self.assertTrue(proxy.enabled)
        self.assertEqual(len(service.operations), 2)
        self.assertEqual(service.operations[0]["action"], "preflight")
        self.assertEqual(service.operations[1]["action"], "preflight_ok")

    def test_preflight_raises_when_server_is_unreachable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        service = _build_service(self, handler)

        with self.assertRaises(ToxiproxyRequestError):
            service.preflight(proxy_name="payments-api")

    def test_preflight_raises_when_proxy_is_missing(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=404, request=request)

        service = _build_service(self, handler)

        with self.assertRaises(ToxiproxyProxyNotFoundError):
            service.preflight(proxy_name="missing-proxy")

    def test_preflight_raises_when_proxy_is_disabled(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json=_load_fixture("proxy-disabled.json"),
                request=request,
            )

        service = _build_service(self, handler)

        with self.assertRaises(ToxiproxyProxyStateError):
            service.preflight(proxy_name="payments-api")


class InjectFaultTests(unittest.TestCase):
    def test_inject_latency_fault_returns_handle(self) -> None:
        created_toxic = _load_fixture("toxic-latency.json")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "POST" and "/toxics" in str(request.url):
                return httpx.Response(
                    status_code=200,
                    json=created_toxic,
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        service = _build_service(self, handler)
        handle = service.inject_fault(
            proxy_name="payments-api",
            fault_type="latency",
            attributes={"latency_ms": 250, "jitter_ms": 25},
        )

        self.assertEqual(handle.proxy_name, "payments-api")
        self.assertEqual(handle.fault_type, "latency")
        self.assertEqual(handle.rollback_action, "remove_toxic")
        inject_ops = [
            op for op in service.operations if op["action"] == "inject_fault"
        ]
        self.assertEqual(len(inject_ops), 1)

    def test_inject_fault_uses_defaults_when_no_attributes(self) -> None:
        created_toxic = _load_fixture("toxic-latency.json")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "POST":
                return httpx.Response(
                    status_code=200,
                    json=created_toxic,
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        service = _build_service(self, handler)
        handle = service.inject_fault(
            proxy_name="payments-api",
            fault_type="latency",
        )

        self.assertIsNotNone(handle.toxic_name)
        inject_op = next(
            op for op in service.operations if op["action"] == "inject_fault"
        )
        self.assertIn("latency_ms", inject_op["attributes"])

    def test_inject_connection_refused_disables_proxy(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "POST":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-disabled.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        service = _build_service(self, handler)
        handle = service.inject_fault(
            proxy_name="payments-api",
            fault_type="connection_refused",
        )

        self.assertEqual(handle.rollback_action, "enable_proxy")
        self.assertIsNone(handle.toxic_name)


class RollbackFaultTests(unittest.TestCase):
    def test_rollback_removes_toxic_and_confirms(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "DELETE":
                return httpx.Response(
                    status_code=204, request=request
                )
            if request.method == "GET":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-enabled.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        service = _build_service(self, handler)
        handle = ToxiproxyFaultHandle(
            proxy_name="payments-api",
            fault_type="latency",
            rollback_action="remove_toxic",
            toxic_name="toolkit-payments-api-latency-downstream",
        )

        service.rollback_fault(handle)

        rollback_ops = [
            op for op in service.operations
            if op["action"] == "rollback_fault_ok"
        ]
        self.assertEqual(len(rollback_ops), 1)

    def test_rollback_re_enables_proxy_and_confirms(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "GET":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-enabled.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        service = _build_service(self, handler)
        handle = ToxiproxyFaultHandle(
            proxy_name="payments-api",
            fault_type="connection_refused",
            rollback_action="enable_proxy",
        )

        service.rollback_fault(handle)

        self.assertEqual(service.operations[-1]["action"], "rollback_fault_ok")

    def test_rollback_failure_propagates_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=500, request=request)

        service = _build_service(self, handler)
        handle = ToxiproxyFaultHandle(
            proxy_name="payments-api",
            fault_type="latency",
            rollback_action="remove_toxic",
            toxic_name="toolkit-payments-api-latency-downstream",
        )

        with self.assertRaises(ToxiproxyRequestError):
            service.rollback_fault(handle)


class OperationLogTests(unittest.TestCase):
    def test_operations_log_records_full_lifecycle(self) -> None:
        created_toxic = _load_fixture("toxic-latency.json")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    status_code=200,
                    json=_load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "POST" and "/toxics" in str(request.url):
                return httpx.Response(
                    status_code=200,
                    json=created_toxic,
                    request=request,
                )
            if request.method == "DELETE":
                return httpx.Response(
                    status_code=204, request=request
                )
            return httpx.Response(status_code=500, request=request)

        service = _build_service(self, handler)

        service.preflight(proxy_name="payments-api")
        handle = service.inject_fault(
            proxy_name="payments-api",
            fault_type="latency",
            attributes={"latency_ms": 250, "jitter_ms": 25},
        )
        service.rollback_fault(handle)

        actions = [op["action"] for op in service.operations]
        self.assertEqual(
            actions,
            [
                "preflight",
                "preflight_ok",
                "inject_fault",
                "inject_fault_ok",
                "rollback_fault",
                "rollback_fault_ok",
            ],
        )
