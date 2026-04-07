"""Shared runtime models for host and container execution backends.

These types are backend-agnostic. Adapters express execution intent through
ToolExecution (defined in adapters/base.py). The runtime layer translates
that intent into a RuntimeRequest, executes it, and returns a RuntimeResult.
"""

from dataclasses import dataclass, field
from pathlib import Path

from toolkit.adapters.base import ToolExecution


@dataclass(slots=True, frozen=True)
class RuntimeRequest:
    """Backend-agnostic execution request built from adapter intent.

    The runtime backend reads this to decide how to run the tool — either
    as a host subprocess or a containerized command.
    """

    tool: str
    command: tuple[str, ...]
    output_path: Path
    cwd: Path | None = None
    timeout_seconds: float | None = None
    env_overrides: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def from_tool_execution(
        execution: ToolExecution, *, output_path: Path
    ) -> "RuntimeRequest":
        return RuntimeRequest(
            tool=execution.tool,
            command=execution.command,
            output_path=output_path,
            cwd=execution.cwd,
            timeout_seconds=execution.timeout_seconds,
            env_overrides=dict(execution.env_overrides),
        )


@dataclass(slots=True, frozen=True)
class RuntimeResult:
    """Backend-agnostic execution result returned by any runtime backend."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.returncode == 0
