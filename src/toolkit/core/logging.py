"""Structured console logging helpers for live tool execution."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO


@dataclass(slots=True, frozen=True)
class ProcessLogContext:
    """Context attached to structured process log records."""

    runtime: str
    tool: str
    output_path: Path | None = None
    cwd: Path | None = None


@dataclass(slots=True, frozen=True)
class RuntimeLogSettings:
    """Effective console logging settings for runtime execution."""

    enabled: bool = False
    verbosity: int = 0
    color: bool | None = None


_RUNTIME_LOG_SETTINGS: ContextVar[RuntimeLogSettings] = ContextVar(
    "toolkit_runtime_log_settings",
    default=RuntimeLogSettings(),
)

_FIELD_VERBOSITY: dict[str, int] = {
    "output": 1,
    "cwd": 3,
    "command": 3,
}

_RESET = "\x1b[0m"
_TIMESTAMP_COLOR = "\x1b[36m"
_LEVEL_COLORS = {
    "INFO": "\x1b[32m",
    "WARN": "\x1b[33m",
    "ERROR": "\x1b[31m",
    "DEBUG": "\x1b[35m",
}


@contextmanager
def runtime_logging_scope(
    *,
    verbosity: int = 0,
    color: bool | None = None,
) -> Iterator[None]:
    """Apply runtime logging settings for one command invocation."""

    token = _RUNTIME_LOG_SETTINGS.set(
        RuntimeLogSettings(
            enabled=True,
            verbosity=max(0, min(int(verbosity), 3)),
            color=color,
        )
    )
    try:
        yield
    finally:
        _RUNTIME_LOG_SETTINGS.reset(token)


def current_runtime_log_settings() -> RuntimeLogSettings:
    """Return the current runtime logging settings."""

    return _RUNTIME_LOG_SETTINGS.get()


def emit_runtime_log(
    target: TextIO,
    *,
    level: str,
    event: str,
    message: str | None = None,
    settings: RuntimeLogSettings | None = None,
    **fields: object,
) -> None:
    """Write one structured runtime log line to the target stream."""

    resolved_settings = settings or current_runtime_log_settings()
    if not _should_emit_runtime_log(
        resolved_settings,
        level=level,
        event=event,
        stream=fields.get("stream"),
    ):
        return

    parts = [
        _colorize(target, _timestamp(), color=_TIMESTAMP_COLOR, settings=resolved_settings),
        _colorize(
            target,
            level.upper(),
            color=_LEVEL_COLORS.get(level.upper()),
            settings=resolved_settings,
        ),
        f"event={event}",
    ]
    for key, value in _filtered_fields(resolved_settings, fields).items():
        if value is None:
            continue
        parts.append(f"{key}={_format_field_value(value)}")
    if message is not None:
        parts.append(f"message={json.dumps(message, ensure_ascii=True)}")

    target.write(" ".join(parts) + "\n")
    target.flush()


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _format_field_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Path):
        raw = str(value)
    else:
        raw = str(value)

    if not raw:
        return '""'
    if any(char.isspace() or char in {'"', "="} for char in raw):
        return json.dumps(raw, ensure_ascii=True)
    return raw


def _should_emit_runtime_log(
    settings: RuntimeLogSettings,
    *,
    level: str,
    event: str,
    stream: object | None,
) -> bool:
    if not settings.enabled:
        return False

    normalized_level = level.upper()
    if normalized_level in {"ERROR", "WARN"}:
        return True
    if event in {"tool.start", "tool.finish"}:
        return True
    if event == "tool.output":
        if stream == "stderr":
            return settings.verbosity >= 1
        return settings.verbosity >= 2
    return settings.verbosity >= 3


def _filtered_fields(
    settings: RuntimeLogSettings,
    fields: dict[str, object],
) -> dict[str, object]:
    return {
        key: value
        for key, value in fields.items()
        if settings.verbosity >= _FIELD_VERBOSITY.get(key, 0)
    }


def _colorize(
    target: TextIO,
    text: str,
    *,
    color: str | None,
    settings: RuntimeLogSettings,
) -> str:
    if color is None or not _supports_color(target, settings):
        return text
    return f"{color}{text}{_RESET}"


def _supports_color(target: TextIO, settings: RuntimeLogSettings) -> bool:
    if settings.color is not None:
        return settings.color
    if os.environ.get("NO_COLOR"):
        return False
    isatty = getattr(target, "isatty", None)
    return bool(callable(isatty) and isatty())
