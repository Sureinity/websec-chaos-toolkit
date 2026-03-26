"""Chaos orchestration placeholders."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ChaosRunRequest:
    """A normalized request to run a chaos profile once."""

    app_id: str
    environment: str
    profile: str
