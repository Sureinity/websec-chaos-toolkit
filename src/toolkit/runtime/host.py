"""Host runtime backend executing tools as direct subprocesses.

This formalizes the existing subprocess-backed execution into the
RuntimeBackend protocol. The host backend requires scanner binaries
installed on the operator's PATH.
"""

import os
import subprocess
from pathlib import Path

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.process import find_binary
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
        merged_env = dict(os.environ)
        merged_env.update(request.env_overrides)

        try:
            completed = subprocess.run(
                request.command,
                cwd=request.cwd,
                env=merged_env,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return RuntimeResult(
                command=request.command,
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )

        return RuntimeResult(
            command=request.command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
