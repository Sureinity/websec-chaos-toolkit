"""Live Toxiproxy execution service for the chaos orchestration path.

This service isolates all live proxy interaction behind one runtime-facing
boundary. The runner delegates fault injection and rollback here instead of
calling the Toxiproxy client directly.

Runtime failure contract
------------------------
- Missing Toxiproxy server: ToxiproxyRequestError (exit code 2).
- Missing proxy: ToxiproxyProxyNotFoundError (exit code 2).
- Invalid proxy state: ToxiproxyProxyStateError (exit code 2).
- Failed rollback: ToxiproxyRequestError or ToxiproxyProxyStateError (exit 2).
- Unsupported fault (packet_loss): UnsupportedToxiproxyFaultError (exit 2).

The service records every operation it performs so the runner can persist
an auditable action log in the run artifacts.
"""

from collections.abc import Mapping

from toolkit.chaos.contracts import SupportedChaosFaultType
from toolkit.chaos.service import default_fault_attributes
from toolkit.chaos.toxiproxy import (
    TOXIPROXY_DEFAULT_BASE_URL,
    ToxiproxyClient,
    ToxiproxyFaultHandle,
    ToxiproxyProxy,
)


class ChaosExecutionService:
    """Live Toxiproxy execution boundary for the chaos runner.

    Satisfies the ChaosFaultController protocol so the runner can use it
    interchangeably with the FixtureToxiproxyController.
    """

    def __init__(
        self,
        *,
        base_url: str = TOXIPROXY_DEFAULT_BASE_URL,
        timeout: float = 5.0,
    ) -> None:
        self._client = ToxiproxyClient(base_url=base_url, timeout=timeout)
        self.operations: list[dict[str, object]] = []

    def close(self) -> None:
        self._client.close()

    def preflight(self, *, proxy_name: str) -> ToxiproxyProxy:
        """Check Toxiproxy server availability and validate the target proxy.

        Raises ToxiproxyRequestError if the server is unreachable, and
        ToxiproxyProxyNotFoundError or ToxiproxyProxyStateError if the
        proxy is missing or disabled.
        """
        self.operations.append(
            {
                "action": "preflight",
                "proxy_name": proxy_name,
            }
        )
        proxy = self._client.require_proxy(proxy_name, expect_enabled=True)
        self.operations.append(
            {
                "action": "preflight_ok",
                "proxy_name": proxy_name,
                "listen": proxy.listen,
                "upstream": proxy.upstream,
            }
        )
        return proxy

    def inject_fault(
        self,
        *,
        proxy_name: str,
        fault_type: SupportedChaosFaultType,
        attributes: Mapping[str, int | float] | None = None,
    ) -> ToxiproxyFaultHandle:
        """Inject one reversible fault through the Toxiproxy API.

        Uses default_fault_attributes() when no explicit attributes are
        provided. Records the operation for the action log.
        """
        resolved_attributes = (
            dict(attributes) if attributes else default_fault_attributes(fault_type)
        )
        self.operations.append(
            {
                "action": "inject_fault",
                "proxy_name": proxy_name,
                "fault_type": fault_type,
                "attributes": resolved_attributes,
            }
        )
        handle = self._client.inject_fault(
            proxy_name=proxy_name,
            fault_type=fault_type,
            attributes=resolved_attributes,
        )
        self.operations.append(
            {
                "action": "inject_fault_ok",
                "proxy_name": proxy_name,
                "fault_type": fault_type,
                "rollback_action": handle.rollback_action,
                "toxic_name": handle.toxic_name,
            }
        )
        return handle

    def rollback_fault(self, handle: ToxiproxyFaultHandle) -> None:
        """Rollback a previously injected fault and confirm the result.

        Records the operation for the action log. Raises on confirmation
        failure so the runner can escalate to exit code 2.
        """
        self.operations.append(
            {
                "action": "rollback_fault",
                "proxy_name": handle.proxy_name,
                "fault_type": handle.fault_type,
                "rollback_action": handle.rollback_action,
                "toxic_name": handle.toxic_name,
            }
        )
        self._client.rollback_fault(handle)
        self.operations.append(
            {
                "action": "rollback_fault_ok",
                "proxy_name": handle.proxy_name,
            }
        )
