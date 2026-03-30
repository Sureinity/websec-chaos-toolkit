"""Toxiproxy client wrapper for reversible chaos faults."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

import httpx

from toolkit.chaos.contracts import SupportedChaosFaultType

TOXIPROXY_DEFAULT_BASE_URL = "http://127.0.0.1:8474"
TOXIPROXY_DEFAULT_STREAM = "downstream"
TOXIPROXY_DEFAULT_TOXICITY = 1.0
TOXIPROXY_TOOLKIT_NAME_PREFIX = "toolkit"

ToxiproxyStream = Literal["upstream", "downstream"]
ToxiproxyRollbackAction = Literal["remove_toxic", "enable_proxy"]
ToxiproxyOperation = Literal["create_toxic", "disable_proxy"]


@dataclass(slots=True, frozen=True)
class ToxiproxyRequestError(RuntimeError):
    """Raised when the Toxiproxy API cannot be reached or returns a bad response."""

    operation: str
    detail: str

    def __str__(self) -> str:
        return f"Toxiproxy request failed during {self.operation}: {self.detail}"


@dataclass(slots=True, frozen=True)
class ToxiproxyProxyNotFoundError(RuntimeError):
    """Raised when the requested proxy is not defined in Toxiproxy."""

    proxy_name: str

    def __str__(self) -> str:
        return f"Toxiproxy proxy was not found: {self.proxy_name!r}"


@dataclass(slots=True, frozen=True)
class ToxiproxyProxyStateError(RuntimeError):
    """Raised when a proxy or toxic is present but not in a usable state."""

    proxy_name: str
    detail: str

    def __str__(self) -> str:
        return f"Toxiproxy proxy {self.proxy_name!r} is not in a usable state: {self.detail}"


@dataclass(slots=True, frozen=True)
class UnsupportedToxiproxyFaultError(RuntimeError):
    """Raised when a chaos fault cannot be mapped safely to Toxiproxy."""

    fault_type: str
    detail: str

    def __str__(self) -> str:
        return f"Chaos fault {self.fault_type!r} is not supported by the Toxiproxy wrapper: {self.detail}"


@dataclass(slots=True, frozen=True)
class ToxiproxyToxic:
    """Normalized toxic metadata returned by the Toxiproxy API."""

    name: str
    toxic_type: str
    stream: ToxiproxyStream
    toxicity: float
    attributes: dict[str, object]


@dataclass(slots=True, frozen=True)
class ToxiproxyProxy:
    """Normalized proxy metadata returned by the Toxiproxy API."""

    name: str
    listen: str
    upstream: str
    enabled: bool
    toxics: tuple[ToxiproxyToxic, ...]


@dataclass(slots=True, frozen=True)
class ToxiproxyFaultRequest:
    """One wrapper-level fault request translated into a Toxiproxy operation."""

    proxy_name: str
    fault_type: SupportedChaosFaultType
    operation: ToxiproxyOperation
    rollback_action: ToxiproxyRollbackAction
    payload: dict[str, object]
    toxic_name: str | None = None
    toxic_type: str | None = None


@dataclass(slots=True, frozen=True)
class ToxiproxyFaultHandle:
    """Fault handle returned after successful injection for later rollback."""

    proxy_name: str
    fault_type: SupportedChaosFaultType
    rollback_action: ToxiproxyRollbackAction
    toxic_name: str | None = None
    toxic_type: str | None = None


class ToxiproxyClient:
    """Small wrapper around the Toxiproxy HTTP API."""

    def __init__(
        self,
        *,
        base_url: str = TOXIPROXY_DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if client is None:
            self._client = httpx.Client(timeout=timeout)
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False

    def close(self) -> None:
        """Close the owned HTTP client if this wrapper created it."""

        if self._owns_client:
            self._client.close()

    def get_proxy(self, proxy_name: str) -> ToxiproxyProxy:
        """Fetch and parse one Toxiproxy proxy definition."""

        response = self._request(
            "GET",
            f"/proxies/{proxy_name}",
            operation=f"get proxy {proxy_name!r}",
        )
        if response.status_code == httpx.codes.NOT_FOUND:
            raise ToxiproxyProxyNotFoundError(proxy_name=proxy_name)
        if response.is_error:
            raise ToxiproxyRequestError(
                operation=f"get proxy {proxy_name!r}",
                detail=f"HTTP {response.status_code}",
            )
        payload = self._parse_json_response(
            response,
            operation=f"get proxy {proxy_name!r}",
        )
        return _parse_proxy_payload(proxy_name, payload)

    def require_proxy(self, proxy_name: str, *, expect_enabled: bool = True) -> ToxiproxyProxy:
        """Return a proxy and enforce the expected enabled state."""

        proxy = self.get_proxy(proxy_name)
        if expect_enabled and not proxy.enabled:
            raise ToxiproxyProxyStateError(
                proxy_name=proxy_name,
                detail="expected an enabled proxy before fault injection",
            )
        return proxy

    def list_toxics(self, proxy_name: str) -> tuple[ToxiproxyToxic, ...]:
        """Return the current toxics for a proxy."""

        return self.get_proxy(proxy_name).toxics

    def inject_fault(
        self,
        *,
        proxy_name: str,
        fault_type: SupportedChaosFaultType,
        attributes: Mapping[str, int | float] | None = None,
        toxic_name: str | None = None,
        stream: ToxiproxyStream = TOXIPROXY_DEFAULT_STREAM,
    ) -> ToxiproxyFaultHandle:
        """Inject one fault using the wrapper-level chaos contract."""

        self.require_proxy(proxy_name, expect_enabled=True)
        request = build_toxiproxy_fault_request(
            proxy_name=proxy_name,
            fault_type=fault_type,
            attributes=attributes,
            toxic_name=toxic_name,
            stream=stream,
        )

        if request.operation == "disable_proxy":
            response = self._request(
                "POST",
                f"/proxies/{proxy_name}",
                operation=f"disable proxy {proxy_name!r}",
                json_body=request.payload,
            )
            if response.status_code == httpx.codes.NOT_FOUND:
                raise ToxiproxyProxyNotFoundError(proxy_name=proxy_name)
            if response.is_error:
                raise ToxiproxyRequestError(
                    operation=f"disable proxy {proxy_name!r}",
                    detail=f"HTTP {response.status_code}",
                )
            proxy = _parse_proxy_payload(
                proxy_name,
                self._parse_json_response(
                    response,
                    operation=f"disable proxy {proxy_name!r}",
                ),
            )
            if proxy.enabled:
                raise ToxiproxyProxyStateError(
                    proxy_name=proxy_name,
                    detail="proxy remained enabled after connection_refused injection",
                )
        else:
            response = self._request(
                "POST",
                f"/proxies/{proxy_name}/toxics",
                operation=f"create toxic for proxy {proxy_name!r}",
                json_body=request.payload,
            )
            if response.status_code == httpx.codes.NOT_FOUND:
                raise ToxiproxyProxyNotFoundError(proxy_name=proxy_name)
            if response.is_error:
                raise ToxiproxyRequestError(
                    operation=f"create toxic for proxy {proxy_name!r}",
                    detail=f"HTTP {response.status_code}",
                )
            created_toxic = _parse_toxic_payload(
                proxy_name,
                self._parse_json_response(
                    response,
                    operation=f"create toxic for proxy {proxy_name!r}",
                ),
            )
            if request.toxic_name is not None and created_toxic.name != request.toxic_name:
                raise ToxiproxyProxyStateError(
                    proxy_name=proxy_name,
                    detail=(
                        "created toxic name did not match the requested toolkit-managed toxic: "
                        f"{created_toxic.name!r}"
                    ),
                )

        return ToxiproxyFaultHandle(
            proxy_name=proxy_name,
            fault_type=fault_type,
            rollback_action=request.rollback_action,
            toxic_name=request.toxic_name,
            toxic_type=request.toxic_type,
        )

    def rollback_fault(self, handle: ToxiproxyFaultHandle) -> None:
        """Rollback a previously injected fault and confirm the final state."""

        if handle.rollback_action == "remove_toxic":
            if handle.toxic_name is None:
                raise ToxiproxyProxyStateError(
                    proxy_name=handle.proxy_name,
                    detail="rollback requested toxic removal without a toxic name",
                )
            response = self._request(
                "DELETE",
                f"/proxies/{handle.proxy_name}/toxics/{handle.toxic_name}",
                operation=(
                    f"remove toxic {handle.toxic_name!r} from proxy {handle.proxy_name!r}"
                ),
            )
            if response.status_code not in (
                httpx.codes.OK,
                httpx.codes.NO_CONTENT,
                httpx.codes.NOT_FOUND,
            ):
                raise ToxiproxyRequestError(
                    operation=(
                        f"remove toxic {handle.toxic_name!r} from proxy {handle.proxy_name!r}"
                    ),
                    detail=f"HTTP {response.status_code}",
                )
        elif handle.rollback_action == "enable_proxy":
            response = self._request(
                "POST",
                f"/proxies/{handle.proxy_name}",
                operation=f"enable proxy {handle.proxy_name!r}",
                json_body={"enabled": True},
            )
            if response.status_code == httpx.codes.NOT_FOUND:
                raise ToxiproxyProxyNotFoundError(proxy_name=handle.proxy_name)
            if response.is_error:
                raise ToxiproxyRequestError(
                    operation=f"enable proxy {handle.proxy_name!r}",
                    detail=f"HTTP {response.status_code}",
                )
            proxy = _parse_proxy_payload(
                handle.proxy_name,
                self._parse_json_response(
                    response,
                    operation=f"enable proxy {handle.proxy_name!r}",
                ),
            )
            if not proxy.enabled:
                raise ToxiproxyProxyStateError(
                    proxy_name=handle.proxy_name,
                    detail="proxy remained disabled after rollback",
                )
        else:
            raise ToxiproxyProxyStateError(
                proxy_name=handle.proxy_name,
                detail=f"unsupported rollback action: {handle.rollback_action}",
            )

        self.confirm_rollback(handle)

    def confirm_rollback(self, handle: ToxiproxyFaultHandle) -> None:
        """Confirm that the rollback action left the proxy in the expected state."""

        proxy = self.get_proxy(handle.proxy_name)
        if handle.rollback_action == "remove_toxic":
            if handle.toxic_name is None:
                raise ToxiproxyProxyStateError(
                    proxy_name=handle.proxy_name,
                    detail="rollback confirmation requires a toxic name",
                )
            if any(toxic.name == handle.toxic_name for toxic in proxy.toxics):
                raise ToxiproxyProxyStateError(
                    proxy_name=handle.proxy_name,
                    detail=f"toxic {handle.toxic_name!r} still exists after rollback",
                )
            return

        if handle.rollback_action == "enable_proxy" and not proxy.enabled:
            raise ToxiproxyProxyStateError(
                proxy_name=handle.proxy_name,
                detail="proxy is still disabled after rollback confirmation",
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json_body: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        try:
            return self._client.request(
                method,
                f"{self.base_url}{path}",
                json=json_body,
            )
        except httpx.HTTPError as exc:
            raise ToxiproxyRequestError(operation=operation, detail=str(exc)) from exc

    def _parse_json_response(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ToxiproxyRequestError(
                operation=operation,
                detail="response did not contain valid JSON",
            ) from exc

        if not isinstance(payload, Mapping):
            raise ToxiproxyRequestError(
                operation=operation,
                detail="response JSON must be an object",
            )
        return payload


def build_toxiproxy_fault_request(
    *,
    proxy_name: str,
    fault_type: SupportedChaosFaultType,
    attributes: Mapping[str, int | float] | None = None,
    toxic_name: str | None = None,
    stream: ToxiproxyStream = TOXIPROXY_DEFAULT_STREAM,
) -> ToxiproxyFaultRequest:
    """Translate one chaos fault request into a Toxiproxy API operation."""

    normalized_stream = _normalize_stream(stream)
    normalized_attributes = dict(attributes or {})

    if fault_type == "packet_loss":
        raise UnsupportedToxiproxyFaultError(
            fault_type=fault_type,
            detail="the official Toxiproxy HTTP API does not expose a packet_loss toxic",
        )

    if fault_type == "connection_refused":
        if normalized_attributes:
            raise UnsupportedToxiproxyFaultError(
                fault_type=fault_type,
                detail="connection_refused does not accept toxic attributes",
            )
        return ToxiproxyFaultRequest(
            proxy_name=proxy_name,
            fault_type=fault_type,
            operation="disable_proxy",
            rollback_action="enable_proxy",
            payload={"enabled": False},
        )

    if fault_type == "latency":
        toxic_attributes = {
            "latency": _require_non_negative_number(
                normalized_attributes,
                key="latency_ms",
                fault_type=fault_type,
            ),
            "jitter": _optional_non_negative_number(
                normalized_attributes,
                key="jitter_ms",
                default=0,
                fault_type=fault_type,
            ),
        }
        toxic_type = "latency"
    elif fault_type == "bandwidth":
        toxic_attributes = {
            "rate": _require_positive_number(
                normalized_attributes,
                key="rate_kbps",
                fault_type=fault_type,
            )
        }
        toxic_type = "bandwidth"
    elif fault_type == "timeout":
        toxic_attributes = {
            "timeout": _require_non_negative_number(
                normalized_attributes,
                key="timeout_ms",
                fault_type=fault_type,
            )
        }
        toxic_type = "timeout"
    else:
        raise UnsupportedToxiproxyFaultError(
            fault_type=fault_type,
            detail="no Toxiproxy mapping exists for this fault type",
        )

    _reject_unknown_keys(
        normalized_attributes,
        allowed_keys=_allowed_attribute_keys_for_fault(fault_type),
        fault_type=fault_type,
    )

    resolved_toxic_name = toxic_name or _default_toxic_name(
        proxy_name=proxy_name,
        fault_type=fault_type,
        stream=normalized_stream,
    )
    return ToxiproxyFaultRequest(
        proxy_name=proxy_name,
        fault_type=fault_type,
        operation="create_toxic",
        rollback_action="remove_toxic",
        payload={
            "name": resolved_toxic_name,
            "type": toxic_type,
            "stream": normalized_stream,
            "toxicity": TOXIPROXY_DEFAULT_TOXICITY,
            "attributes": toxic_attributes,
        },
        toxic_name=resolved_toxic_name,
        toxic_type=toxic_type,
    )


def _allowed_attribute_keys_for_fault(fault_type: SupportedChaosFaultType) -> set[str]:
    if fault_type == "latency":
        return {"latency_ms", "jitter_ms"}
    if fault_type == "bandwidth":
        return {"rate_kbps"}
    if fault_type == "timeout":
        return {"timeout_ms"}
    return set()


def _reject_unknown_keys(
    attributes: Mapping[str, int | float],
    *,
    allowed_keys: set[str],
    fault_type: SupportedChaosFaultType,
) -> None:
    unknown_keys = set(attributes) - allowed_keys
    if unknown_keys:
        raise UnsupportedToxiproxyFaultError(
            fault_type=fault_type,
            detail=(
                "unexpected attribute keys were provided: "
                + ", ".join(sorted(unknown_keys))
            ),
        )


def _normalize_stream(stream: str) -> ToxiproxyStream:
    if stream not in {"upstream", "downstream"}:
        raise ValueError(f"Unsupported Toxiproxy stream: {stream!r}")
    return cast(ToxiproxyStream, stream)


def _default_toxic_name(
    *,
    proxy_name: str,
    fault_type: SupportedChaosFaultType,
    stream: ToxiproxyStream,
) -> str:
    return f"{TOXIPROXY_TOOLKIT_NAME_PREFIX}-{proxy_name}-{fault_type}-{stream}"


def _require_positive_number(
    attributes: Mapping[str, int | float],
    *,
    key: str,
    fault_type: SupportedChaosFaultType,
) -> int | float:
    value = _require_numeric_attribute(attributes, key=key, fault_type=fault_type)
    if value <= 0:
        raise UnsupportedToxiproxyFaultError(
            fault_type=fault_type,
            detail=f"attribute {key!r} must be greater than zero",
        )
    return value


def _require_non_negative_number(
    attributes: Mapping[str, int | float],
    *,
    key: str,
    fault_type: SupportedChaosFaultType,
) -> int | float:
    value = _require_numeric_attribute(attributes, key=key, fault_type=fault_type)
    if value < 0:
        raise UnsupportedToxiproxyFaultError(
            fault_type=fault_type,
            detail=f"attribute {key!r} must be zero or greater",
        )
    return value


def _optional_non_negative_number(
    attributes: Mapping[str, int | float],
    *,
    key: str,
    default: int | float,
    fault_type: SupportedChaosFaultType,
) -> int | float:
    if key not in attributes:
        return default
    return _require_non_negative_number(attributes, key=key, fault_type=fault_type)


def _require_numeric_attribute(
    attributes: Mapping[str, int | float],
    *,
    key: str,
    fault_type: SupportedChaosFaultType,
) -> int | float:
    if key not in attributes:
        raise UnsupportedToxiproxyFaultError(
            fault_type=fault_type,
            detail=f"required attribute {key!r} is missing",
        )
    value = attributes[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UnsupportedToxiproxyFaultError(
            fault_type=fault_type,
            detail=f"attribute {key!r} must be numeric",
        )
    return value


def _parse_proxy_payload(proxy_name: str, payload: Mapping[str, Any]) -> ToxiproxyProxy:
    try:
        toxics_payload = payload.get("toxics", [])
        if not isinstance(toxics_payload, list):
            raise TypeError("toxics must be a list")
        toxics = tuple(_parse_toxic_payload(proxy_name, item) for item in toxics_payload)
        enabled = payload["enabled"]
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        return ToxiproxyProxy(
            name=_require_string_field(payload, "name"),
            listen=_require_string_field(payload, "listen"),
            upstream=_require_string_field(payload, "upstream"),
            enabled=enabled,
            toxics=toxics,
        )
    except (KeyError, TypeError) as exc:
        raise ToxiproxyProxyStateError(
            proxy_name=proxy_name,
            detail=f"proxy payload was invalid: {exc}",
        ) from exc


def _parse_toxic_payload(proxy_name: str, payload: Mapping[str, Any]) -> ToxiproxyToxic:
    try:
        stream = _normalize_stream(_require_string_field(payload, "stream"))
        toxicity = payload["toxicity"]
        if not isinstance(toxicity, int | float):
            raise TypeError("toxicity must be numeric")
        attributes = payload.get("attributes", {})
        if not isinstance(attributes, Mapping):
            raise TypeError("attributes must be an object")
        return ToxiproxyToxic(
            name=_require_string_field(payload, "name"),
            toxic_type=_require_string_field(payload, "type"),
            stream=stream,
            toxicity=float(toxicity),
            attributes=dict(attributes),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ToxiproxyProxyStateError(
            proxy_name=proxy_name,
            detail=f"toxic payload was invalid: {exc}",
        ) from exc


def _require_string_field(payload: Mapping[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{key} must be a non-empty string")
    return value
