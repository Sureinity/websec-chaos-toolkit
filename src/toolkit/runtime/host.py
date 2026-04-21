"""Host runtime backend executing tools as direct subprocesses.

This formalizes the existing subprocess-backed execution into the
RuntimeBackend protocol. The host backend requires scanner binaries
installed on the operator's PATH.
"""

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.process import find_binary, run_process_command
from toolkit.core.logging import ProcessLogContext
from toolkit.runtime.models import RuntimeRequest, RuntimeResult


class HostRuntime:
    """Execute scanner tools as direct host subprocesses."""

    def check_tool_available(self, tool: str) -> AdapterAvailability:
        resolved = find_binary(tool)
        if resolved is None:
            return AdapterAvailability(
                available=False,
                reason=f"{tool} binary was not found on PATH",
                binary=tool,
            )
        return AdapterAvailability(
            available=True,
            binary=str(resolved),
        )

    def execute(self, request: RuntimeRequest) -> RuntimeResult:
        completed = run_process_command(
            command=request.command,
            cwd=request.cwd,
            env_overrides=request.env_overrides,
            timeout_seconds=request.timeout_seconds,
            stream_output=True,
            log_context=ProcessLogContext(
                runtime="host",
                tool=request.tool,
                output_path=request.output_path,
                cwd=request.cwd,
            ),
        )

        return RuntimeResult(
            command=completed.command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=completed.timed_out,
        )
