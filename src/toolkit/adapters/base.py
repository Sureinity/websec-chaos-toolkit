"""Contract types for safe external tool adapters."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from toolkit.results.models import NormalizedResult


class AdapterSkipReason(StrEnum):
    """Reasons an adapter can skip execution without being a hard runtime failure."""

    DISABLED = "disabled"
    MISSING_BINARY = "missing_binary"
    UNSUPPORTED_ENVIRONMENT = "unsupported_environment"
    SAFE_MODE_BLOCKED = "safe_mode_blocked"


@dataclass(slots=True, frozen=True)
class AdapterAvailability:
    """Availability check result for a scanner adapter."""

    available: bool
    reason: str | None = None
    binary: str | None = None


@dataclass(slots=True, frozen=True)
class ToolExecution:
    """The safe command an adapter intends to run."""

    tool: str
    command: tuple[str, ...]
    cwd: Path | None = None
    timeout_seconds: float | None = None
    env_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ToolArtifact:
    """A raw artifact produced or consumed by a tool run."""

    tool: str
    path: Path
    kind: str = "raw_output"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class AdapterRunResult:
    """Normalized outcome of a tool adapter invocation.

    Contract expectations:
    - raw artifacts are preserved even when parsing succeeds
    - normalized findings are deterministic and adapter-independent
    - skipped runs use `skip_reason` instead of pretending success
    - hard failures use `error_detail` with safe, user-facing text
    """

    tool: str
    execution: ToolExecution | None = None
    availability: AdapterAvailability | None = None
    artifacts: tuple[ToolArtifact, ...] = ()
    findings: tuple[NormalizedResult, ...] = ()
    skip_reason: AdapterSkipReason | None = None
    error_detail: str | None = None

    @property
    def skipped(self) -> bool:
        return self.skip_reason is not None

    @property
    def failed(self) -> bool:
        return self.error_detail is not None


class ToolAdapter(Protocol):
    """Shared contract for safe scanner wrappers.

    Every adapter must:
    - expose an availability check before execution
    - build commands from validated config only
    - stay safe by default and avoid destructive flags/templates
    - preserve raw artifacts and normalize findings into shared result models
    """

    name: str

    def check_availability(self) -> AdapterAvailability:
        """Return whether the tool binary/runtime is available."""

    def build_execution(self) -> ToolExecution:
        """Return the safe command the adapter would run."""


def build_success_result(
    tool: str,
    *,
    execution: ToolExecution | None = None,
    availability: AdapterAvailability | None = None,
    artifacts: tuple[ToolArtifact, ...] = (),
    findings: tuple[NormalizedResult, ...] = (),
) -> AdapterRunResult:
    """Build a successful adapter outcome."""

    return AdapterRunResult(
        tool=tool,
        execution=execution,
        availability=availability,
        artifacts=artifacts,
        findings=findings,
    )


def build_skipped_result(
    tool: str,
    *,
    skip_reason: AdapterSkipReason,
    execution: ToolExecution | None = None,
    availability: AdapterAvailability | None = None,
    artifacts: tuple[ToolArtifact, ...] = (),
) -> AdapterRunResult:
    """Build a skipped adapter outcome."""

    return AdapterRunResult(
        tool=tool,
        execution=execution,
        availability=availability,
        artifacts=artifacts,
        skip_reason=skip_reason,
    )


def build_failed_result(
    tool: str,
    *,
    error_detail: str,
    execution: ToolExecution | None = None,
    availability: AdapterAvailability | None = None,
    artifacts: tuple[ToolArtifact, ...] = (),
) -> AdapterRunResult:
    """Build a hard-failure adapter outcome."""

    return AdapterRunResult(
        tool=tool,
        execution=execution,
        availability=availability,
        artifacts=artifacts,
        error_detail=error_detail,
    )
