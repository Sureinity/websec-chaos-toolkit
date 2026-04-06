"""Shared process execution helpers for scanner adapters."""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from toolkit.adapters.base import AdapterAvailability, ToolExecution


@dataclass(slots=True, frozen=True)
class ProcessResult:
    """Captured result of a tool execution."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.returncode == 0


def find_binary(binary: str) -> Path | None:
    """Resolve a binary on PATH."""

    resolved = shutil.which(binary)
    return Path(resolved) if resolved is not None else None


def check_binary_available(binary: str) -> AdapterAvailability:
    """Return a normalized availability result for a scanner binary."""

    resolved = find_binary(binary)
    if resolved is None:
        return AdapterAvailability(
            available=False,
            reason=f"{binary} binary was not found on PATH",
            binary=binary,
        )

    return AdapterAvailability(
        available=True,
        binary=str(resolved),
    )


def run_tool_execution(execution: ToolExecution) -> ProcessResult:
    """Execute a prepared tool command and capture stdout/stderr."""

    try:
        completed = subprocess.run(
            execution.command,
            cwd=execution.cwd,
            env=_merged_environment(execution.env_overrides),
            capture_output=True,
            text=True,
            timeout=execution.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return ProcessResult(
            command=execution.command,
            returncode=-1,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )

    return ProcessResult(
        command=execution.command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _merged_environment(env_overrides: dict[str, str]) -> dict[str, str]:
    # Build a fresh process environment without mutating os.environ.
    merged_env = dict(os.environ)
    merged_env.update(env_overrides)
    return merged_env
