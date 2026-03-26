"""Stable process exit codes."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes reserved by the toolkit contract."""

    SUCCESS = 0
    FINDINGS_OR_FAILURE = 1
    CONFIG_OR_RUNTIME_ERROR = 2
