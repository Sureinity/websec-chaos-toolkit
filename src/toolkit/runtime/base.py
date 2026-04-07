"""Runtime backend protocol for scanner tool execution."""

from typing import Protocol

from toolkit.adapters.base import AdapterAvailability
from toolkit.runtime.models import RuntimeRequest, RuntimeResult


class RuntimeBackend(Protocol):
    """Contract that host and container backends must satisfy.

    The pentest execution service calls check_tool_available() first, then
    execute() if the tool is available. The backend is responsible for
    translating the RuntimeRequest into the appropriate invocation.
    """

    def check_tool_available(self, tool: str) -> AdapterAvailability:
        """Check whether the tool can be executed by this backend."""
        ...

    def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Run the tool and return a backend-agnostic result."""
        ...
