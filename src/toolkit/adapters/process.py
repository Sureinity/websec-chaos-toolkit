"""Shared process execution helpers for scanner adapters."""

import os
import shlex
import shutil
import subprocess
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TextIO

from toolkit.adapters.base import AdapterAvailability, ToolExecution
from toolkit.core.logging import (
    ProcessLogContext,
    current_runtime_log_settings,
    emit_runtime_log,
)


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


def run_tool_execution(
    execution: ToolExecution,
    *,
    stream_output: bool = False,
    stdout_target: TextIO | None = None,
    stderr_target: TextIO | None = None,
    log_context: ProcessLogContext | None = None,
) -> ProcessResult:
    """Execute a prepared tool command and capture stdout/stderr."""

    return run_process_command(
        command=execution.command,
        cwd=execution.cwd,
        env_overrides=execution.env_overrides,
        timeout_seconds=execution.timeout_seconds,
        stream_output=stream_output,
        stdout_target=stdout_target,
        stderr_target=stderr_target,
        log_context=log_context
        or ProcessLogContext(
            runtime="host",
            tool=execution.tool,
            cwd=execution.cwd,
        ),
    )


def run_process_command(
    *,
    command: tuple[str, ...],
    cwd: Path | None = None,
    env_overrides: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
    stream_output: bool = False,
    stdout_target: TextIO | None = None,
    stderr_target: TextIO | None = None,
    log_context: ProcessLogContext | None = None,
) -> ProcessResult:
    """Execute a command, optionally teeing live output to stdout/stderr."""

    merged_environment = _merged_environment(env_overrides or {})
    resolved_log_context = log_context or ProcessLogContext(
        runtime="host",
        tool=command[0],
        cwd=cwd,
    )

    try:
        if stream_output:
            return _run_streaming_command(
                command=command,
                cwd=cwd,
                env=merged_environment,
                timeout_seconds=timeout_seconds,
                stdout_target=stdout_target,
                stderr_target=stderr_target,
                log_context=resolved_log_context,
            )

        completed = subprocess.run(
            command,
            cwd=cwd,
            env=merged_environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return ProcessResult(
            command=command,
            returncode=-1,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )

    return ProcessResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _merged_environment(env_overrides: Mapping[str, str]) -> dict[str, str]:
    # Build a fresh process environment without mutating os.environ.
    merged_env = dict(os.environ)
    merged_env.update(env_overrides)
    return merged_env


def _run_streaming_command(
    *,
    command: tuple[str, ...],
    cwd: Path | None,
    env: dict[str, str],
    timeout_seconds: float | None,
    stdout_target: TextIO | None,
    stderr_target: TextIO | None,
    log_context: ProcessLogContext,
) -> ProcessResult:
    resolved_stdout_target = stdout_target or sys.stdout
    resolved_stderr_target = stderr_target or sys.stderr
    log_settings = current_runtime_log_settings()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        bufsize=1,
    )
    started_at = monotonic()
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    emit_runtime_log(
        resolved_stdout_target,
        level="INFO",
        event="tool.start",
        runtime=log_context.runtime,
        tool=log_context.tool,
        output=log_context.output_path,
        cwd=log_context.cwd or cwd,
        command=shlex.join(command),
        timeout_seconds=timeout_seconds,
        settings=log_settings,
    )

    stdout_thread = threading.Thread(
        target=_tee_stream,
        args=(
            process.stdout,
            stdout_chunks,
            resolved_stdout_target,
            log_context,
            "stdout",
            "INFO",
            log_settings,
        ),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_tee_stream,
        args=(
            process.stderr,
            stderr_chunks,
            resolved_stderr_target,
            log_context,
            "stderr",
            "WARN",
            log_settings,
        ),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()

    stdout_thread.join()
    stderr_thread.join()
    duration_ms = int((monotonic() - started_at) * 1000)
    resolved_returncode = -1 if timed_out else (process.returncode or 0)
    finish_target = (
        resolved_stderr_target if timed_out or resolved_returncode != 0 else resolved_stdout_target
    )
    emit_runtime_log(
        finish_target,
        level="ERROR" if timed_out or resolved_returncode != 0 else "INFO",
        event="tool.finish",
        runtime=log_context.runtime,
        tool=log_context.tool,
        status="timed_out" if timed_out else ("failed" if resolved_returncode != 0 else "success"),
        exit_code=resolved_returncode,
        duration_ms=duration_ms,
        settings=log_settings,
    )
    return ProcessResult(
        command=command,
        returncode=resolved_returncode,
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
        timed_out=timed_out,
    )


def _tee_stream(
    stream: TextIO | None,
    sink: list[str],
    target: TextIO,
    log_context: ProcessLogContext,
    stream_name: str,
    level: str,
    log_settings,
) -> None:
    if stream is None:
        return

    try:
        for line in iter(stream.readline, ""):
            sink.append(line)
            message = line.rstrip("\r\n")
            if not message:
                continue
            emit_runtime_log(
                target,
                level=level,
                event="tool.output",
                runtime=log_context.runtime,
                tool=log_context.tool,
                stream=stream_name,
                message=message,
                settings=log_settings,
            )
    finally:
        stream.close()
