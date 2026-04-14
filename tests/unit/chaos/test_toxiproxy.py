import json
import unittest
from pathlib import Path

import httpx

from toolkit.chaos.toxiproxy import (
    ToxiproxyClient,
    ToxiproxyFaultHandle,
    ToxiproxyProxyNotFoundError,
    ToxiproxyProxyStateError,
    ToxiproxyRequestError,
    UnsupportedToxiproxyFaultError,
    build_toxiproxy_fault_request,
)

FIXTURE_ROOT = Path("tests/fixtures/chaos/toxiproxy")


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class ToxiproxyClientTests(unittest.TestCase):
    def test_get_proxy_returns_parsed_proxy_and_toxics(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == "/proxies/payments-api":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("proxy-with-latency-toxic.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        client = build_client(self, handler)

        proxy = client.get_proxy("payments-api")

        self.assertEqual(proxy.name, "payments-api")
        self.assertTrue(proxy.enabled)
        self.assertEqual(len(proxy.toxics), 1)
        self.assertEqual(proxy.toxics[0].name, "toolkit-payments-api-latency-downstream")
        self.assertEqual(proxy.toxics[0].toxic_type, "latency")

    def test_get_proxy_raises_when_proxy_is_missing(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=404, request=request)

        client = build_client(self, handler)

        with self.assertRaises(ToxiproxyProxyNotFoundError):
            client.get_proxy("missing-proxy")

    def test_create_proxy_posts_proxy_payload(self) -> None:
        seen_requests: list[tuple[str, str, dict[str, object] | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8")) if request.content else None
            seen_requests.append((request.method, request.url.path, body))
            if request.method == "POST" and request.url.path == "/proxies":
                return httpx.Response(
                    status_code=200,
                    json={
                        "name": "edge-proxy",
                        "listen": "127.0.0.1:18080",
                        "upstream": "127.0.0.1:8000",
                        "enabled": True,
                        "toxics": [],
                    },
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        client = build_client(self, handler)

        proxy = client.create_proxy(
            proxy_name="edge-proxy",
            listen="127.0.0.1:18080",
            upstream="127.0.0.1:8000",
        )

        self.assertEqual(proxy.name, "edge-proxy")
        self.assertEqual(
            seen_requests[0],
            (
                "POST",
                "/proxies",
                {
                    "name": "edge-proxy",
                    "listen": "127.0.0.1:18080",
                    "upstream": "127.0.0.1:8000",
                    "enabled": True,
                },
            ),
        )

    def test_delete_proxy_deletes_existing_proxy(self) -> None:
        seen_requests: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append((request.method, request.url.path))
            if request.method == "DELETE" and request.url.path == "/proxies/edge-proxy":
                return httpx.Response(status_code=204, request=request)
            return httpx.Response(status_code=500, request=request)

        client = build_client(self, handler)

        client.delete_proxy("edge-proxy")

        self.assertEqual(seen_requests, [("DELETE", "/proxies/edge-proxy")])

    def test_require_proxy_rejects_disabled_proxy(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json=load_fixture("proxy-disabled.json"),
                request=request,
            )

        client = build_client(self, handler)

        with self.assertRaisesRegex(ToxiproxyProxyStateError, "expected an enabled proxy"):
            client.require_proxy("payments-api")

    def test_build_fault_request_maps_latency_to_toxic_payload(self) -> None:
        request = build_toxiproxy_fault_request(
            proxy_name="payments-api",
            fault_type="latency",
            attributes={
                "latency_ms": 250,
                "jitter_ms": 25,
            },
        )

        self.assertEqual(request.operation, "create_toxic")
        self.assertEqual(request.rollback_action, "remove_toxic")
        self.assertEqual(
            request.payload,
            {
                "name": "toolkit-payments-api-latency-downstream",
                "type": "latency",
                "stream": "downstream",
                "toxicity": 1.0,
                "attributes": {
                    "latency": 250,
                    "jitter": 25,
                },
            },
        )

    def test_build_fault_request_rejects_packet_loss_without_mapping(self) -> None:
        with self.assertRaisesRegex(UnsupportedToxiproxyFaultError, "packet_loss"):
            build_toxiproxy_fault_request(
                proxy_name="payments-api",
                fault_type="packet_loss",
                attributes={"rate_percent": 10},
            )

    def test_inject_fault_posts_latency_toxic(self) -> None:
        seen_requests: list[tuple[str, str, dict[str, object] | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8")) if request.content else None
            seen_requests.append((request.method, request.url.path, body))
            if request.method == "GET" and request.url.path == "/proxies/payments-api":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "POST" and request.url.path == "/proxies/payments-api/toxics":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("toxic-latency.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        client = build_client(self, handler)

        handle = client.inject_fault(
            proxy_name="payments-api",
            fault_type="latency",
            attributes={"latency_ms": 250, "jitter_ms": 25},
        )

        self.assertEqual(
            handle,
            ToxiproxyFaultHandle(
                proxy_name="payments-api",
                fault_type="latency",
                rollback_action="remove_toxic",
                toxic_name="toolkit-payments-api-latency-downstream",
                toxic_type="latency",
            ),
        )
        self.assertEqual(
            seen_requests[1],
            (
                "POST",
                "/proxies/payments-api/toxics",
                {
                    "name": "toolkit-payments-api-latency-downstream",
                    "type": "latency",
                    "stream": "downstream",
                    "toxicity": 1.0,
                    "attributes": {
                        "latency": 250,
                        "jitter": 25,
                    },
                },
            ),
        )

    def test_inject_fault_disables_proxy_for_connection_refused(self) -> None:
        seen_requests: list[tuple[str, str, dict[str, object] | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8")) if request.content else None
            seen_requests.append((request.method, request.url.path, body))
            if request.method == "GET" and request.url.path == "/proxies/payments-api":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "POST" and request.url.path == "/proxies/payments-api":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("proxy-disabled.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        client = build_client(self, handler)

        handle = client.inject_fault(
            proxy_name="payments-api",
            fault_type="connection_refused",
        )

        self.assertEqual(handle.rollback_action, "enable_proxy")
        self.assertEqual(handle.toxic_name, None)
        self.assertEqual(
            seen_requests[1],
            ("POST", "/proxies/payments-api", {"enabled": False}),
        )

    def test_rollback_fault_deletes_toxic_and_confirms_absence(self) -> None:
        seen_requests: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append((request.method, request.url.path))
            if (
                request.method == "DELETE"
                and request.url.path
                == "/proxies/payments-api/toxics/toolkit-payments-api-latency-downstream"
            ):
                return httpx.Response(status_code=204, request=request)
            if request.method == "GET" and request.url.path == "/proxies/payments-api":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("proxy-enabled.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        client = build_client(self, handler)

        client.rollback_fault(
            ToxiproxyFaultHandle(
                proxy_name="payments-api",
                fault_type="latency",
                rollback_action="remove_toxic",
                toxic_name="toolkit-payments-api-latency-downstream",
                toxic_type="latency",
            )
        )

        self.assertEqual(
            seen_requests,
            [
                ("DELETE", "/proxies/payments-api/toxics/toolkit-payments-api-latency-downstream"),
                ("GET", "/proxies/payments-api"),
            ],
        )

    def test_rollback_fault_reenables_proxy_and_confirms_state(self) -> None:
        seen_requests: list[tuple[str, str, dict[str, object] | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8")) if request.content else None
            seen_requests.append((request.method, request.url.path, body))
            if request.method == "POST" and request.url.path == "/proxies/payments-api":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("proxy-enabled.json"),
                    request=request,
                )
            if request.method == "GET" and request.url.path == "/proxies/payments-api":
                return httpx.Response(
                    status_code=200,
                    json=load_fixture("proxy-enabled.json"),
                    request=request,
                )
            return httpx.Response(status_code=500, request=request)

        client = build_client(self, handler)

        client.rollback_fault(
            ToxiproxyFaultHandle(
                proxy_name="payments-api",
                fault_type="connection_refused",
                rollback_action="enable_proxy",
            )
        )

        self.assertEqual(
            seen_requests,
            [
                ("POST", "/proxies/payments-api", {"enabled": True}),
                ("GET", "/proxies/payments-api", None),
            ],
        )

    def test_http_errors_are_wrapped(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("toxiproxy unavailable", request=request)

        client = build_client(self, handler)

        with self.assertRaisesRegex(ToxiproxyRequestError, "toxiproxy unavailable"):
            client.get_proxy("payments-api")


def build_client(test_case: unittest.TestCase, handler) -> ToxiproxyClient:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = ToxiproxyClient(base_url="http://toxiproxy.internal", client=http_client)
    test_case.addCleanup(http_client.close)
    return client
