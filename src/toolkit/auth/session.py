"""Authentication placeholder types."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SessionSeed:
    """Minimal reference to externally supplied auth material."""

    method: str
    secret_ref: str | None = None
