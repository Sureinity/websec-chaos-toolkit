"""Safe nuclei adapter with fixture-driven normalization."""

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path

from toolkit.adapters.base import (
    AdapterAvailability,
    AdapterRunResult,
    ToolArtifact,
    ToolExecution,
)
from toolkit.adapters.process import check_binary_available
from toolkit.config.models import AppConfig, PentestToolSettings
from toolkit.results.models import NormalizedResult, ResultTimestamps


@dataclass(slots=True, frozen=True)
class NucleiAdapter:
    """Safe nuclei wrapper using explicit template allowlists."""

    app: AppConfig
    settings: PentestToolSettings
    output_path: Path

    name: str = "nuclei"
    binary: str = "nuclei"

    def check_availability(self) -> AdapterAvailability:
        return check_binary_available(self.binary)

    def build_execution(self) -> ToolExecution:
        if not self.settings.safe_mode:
            raise ValueError("nuclei adapter refuses to build commands when safe_mode is disabled.")

        command = [
            self.binary,
            "-target",
            str(self.app.base_url),
            "-jsonl",
            "-silent",
            "-o",
            str(self.output_path),
        ]
        for template in self.settings.allowlisted_rules:
            command.extend(["-t", template])

        return ToolExecution(
            tool=self.name,
            command=tuple(command),
            timeout_seconds=300.0,
            env_overrides={"NUCLEI_DISABLE_UPDATE_CHECK": "true"},
        )

    def build_raw_artifact(self) -> ToolArtifact:
        return ToolArtifact(
            tool=self.name,
            path=self.output_path,
            kind="raw_output",
            metadata={"format": "jsonl"},
        )

    def parse_artifact(
        self,
        artifact_path: Path | None = None,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> tuple[NormalizedResult, ...]:
        path = artifact_path or self.output_path
        findings: list[NormalizedResult] = []
        resolved_started_at = started_at or datetime.now(UTC)

        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            findings.append(
                NormalizedResult(
                    app_id=self.app.id,
                    environment=self.app.environment,
                    target=payload.get("matched-at", str(self.app.base_url)),
                    tool=self.name,
                    category=_category_from_template(payload.get("template-id", "unknown")),
                    severity=_normalize_severity(payload.get("info", {}).get("severity")),
                    confidence=_derive_confidence(payload),
                    evidence=_build_evidence(payload),
                    remediation_summary=_build_remediation_summary(payload),
                    timestamps=ResultTimestamps(
                        started_at=resolved_started_at,
                        finished_at=finished_at,
                    ),
                )
            )

        return tuple(findings)

    def build_fixture_result(
        self,
        *,
        artifact_path: Path | None = None,
        availability: AdapterAvailability | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> AdapterRunResult:
        return AdapterRunResult(
            tool=self.name,
            execution=self.build_execution(),
            availability=availability or AdapterAvailability(available=True, binary=self.binary),
            artifacts=(self.build_raw_artifact(),),
            findings=self.parse_artifact(
                artifact_path,
                started_at=started_at,
                finished_at=finished_at,
            ),
        )


def _normalize_severity(value: str | None) -> str:
    normalized = (value or "info").strip().lower()
    if normalized in {"critical", "high", "medium", "low", "info"}:
        return normalized
    return "info"


def _derive_confidence(payload: dict[str, object]) -> str:
    if payload.get("matcher-name"):
        return "high"
    if payload.get("matched-at"):
        return "medium"
    return "low"


def _build_evidence(payload: dict[str, object]) -> list[str]:
    evidence: list[str] = []
    for field in ("template-id", "matcher-name", "curl-command"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            evidence.append(f"{field}: {value.strip()}")
    return evidence


def _build_remediation_summary(payload: dict[str, object]) -> str:
    template_id = payload.get("template-id", "unknown-template")
    return f"Review and remediate the exposure identified by nuclei template {template_id}."


def _category_from_template(template_id: str) -> str:
    parts = template_id.split("/", 1)
    if len(parts) == 2 and parts[0]:
        return parts[0]
    return "general"
