"""Shared normalized result models."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "low", "medium", "high", "critical"]
Confidence = Literal["low", "medium", "high"]


class ResultTimestamps(BaseModel):
    """Run timing metadata."""

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class NormalizedResult(BaseModel):
    """Stable result contract shared across tools."""

    app_id: str
    environment: str
    target: str
    tool: str
    category: str
    severity: Severity
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list)
    remediation_summary: str
    timestamps: ResultTimestamps
