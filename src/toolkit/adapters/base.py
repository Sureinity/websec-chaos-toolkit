"""Base protocol for external tool adapters."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(slots=True, frozen=True)
class ToolArtifact:
    """A raw artifact produced by a tool run."""

    tool: str
    raw_output: Path
    metadata: dict[str, str] = field(default_factory=dict)


class ToolAdapter(Protocol):
    """Shared contract for future tool wrappers."""

    name: str

    def is_available(self) -> bool:
        """Return whether the tool binary or runtime is available."""
