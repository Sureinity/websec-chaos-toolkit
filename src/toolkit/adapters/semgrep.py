"""Safe Semgrep adapter with fixture-driven normalization."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path

from toolkit.adapters.base import (
    AdapterAvailability,
    AdapterRunResult,
    ToolArtifact,
    ToolExecution,
    build_success_result,
)
from toolkit.adapters.process import check_binary_available
from toolkit.config.models import AppConfig, PentestToolSettings
from toolkit.results.models import NormalizedResult
from toolkit.results.normalizers import build_normalized_result

_SEVERITY_MAPPING = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "low",
}

_CONFIDENCE_MAPPING = {
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
}


@dataclass(slots=True, frozen=True)
class SemgrepAdapter:
    """Safe Semgrep wrapper for read-only local code scans."""

    app: AppConfig
    settings: PentestToolSettings
    output_path: Path
    target_path: Path = field(default_factory=lambda: Path("."))

    name: str = "semgrep"
    binary: str = "semgrep"

    def check_availability(self) -> AdapterAvailability:
        return check_binary_available(self.binary)

    def build_execution(self) -> ToolExecution:
        if not self.settings.safe_mode:
            raise ValueError("semgrep adapter refuses to build commands when safe_mode is disabled.")

        command = [
            self.binary,
            "scan",
            f"--json-output={self.output_path}",
            "--quiet",
        ]
        for config in self.settings.allowlisted_rules:
            command.extend(["--config", config])
        command.append(str(self.target_path))

        return ToolExecution(
            tool=self.name,
            command=tuple(command),
            timeout_seconds=300.0,
        )

    def build_raw_artifact(self) -> ToolArtifact:
        return ToolArtifact(
            tool=self.name,
            path=self.output_path,
            kind="raw_output",
            metadata={"format": "json"},
        )

    def parse_artifact(
        self,
        artifact_path: Path | None = None,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> tuple[NormalizedResult, ...]:
        path = artifact_path or self.output_path
        payload = json.loads(path.read_text(encoding="utf-8"))
        findings: list[NormalizedResult] = []
        resolved_started_at = started_at or datetime.now(UTC)

        for result in payload.get("results", []):
            extra = result.get("extra", {})
            metadata = extra.get("metadata", {}) if isinstance(extra, dict) else {}
            findings.append(
                build_normalized_result(
                    app_id=self.app.id,
                    environment=self.app.environment,
                    target=str(result.get("path", str(self.target_path))),
                    tool=self.name,
                    category=_category_for_result(result, metadata),
                    severity=extra.get("severity") if isinstance(extra, dict) else None,
                    confidence=metadata.get("confidence") if isinstance(metadata, dict) else None,
                    evidence=_build_evidence(result, extra),
                    remediation_summary=_build_remediation_summary(result, extra),
                    started_at=resolved_started_at,
                    finished_at=finished_at,
                    severity_mapping=_SEVERITY_MAPPING,
                    confidence_mapping=_CONFIDENCE_MAPPING,
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
        return build_success_result(
            self.name,
            execution=self.build_execution(),
            availability=availability or AdapterAvailability(available=True, binary=self.binary),
            artifacts=(self.build_raw_artifact(),),
            findings=self.parse_artifact(
                artifact_path,
                started_at=started_at,
                finished_at=finished_at,
            ),
        )


def _category_for_result(result: dict[str, object], metadata: dict[str, object]) -> str:
    check_id = result.get("check_id")
    if isinstance(check_id, str):
        lowered = check_id.lower()
        if "secret" in lowered:
            return "secrets"
        if ".security." in lowered:
            return "security"

    category = metadata.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip().lower()
    return "code"


def _build_evidence(result: dict[str, object], extra: object) -> list[str]:
    evidence: list[str] = []
    check_id = result.get("check_id")
    if isinstance(check_id, str) and check_id.strip():
        evidence.append(f"check_id: {check_id.strip()}")

    path = result.get("path")
    if isinstance(path, str) and path.strip():
        evidence.append(f"path: {path.strip()}")

    if isinstance(extra, dict):
        message = extra.get("message")
        if isinstance(message, str) and message.strip():
            evidence.append(f"message: {message.strip()}")
        lines = extra.get("lines")
        if isinstance(lines, str) and lines.strip():
            evidence.append(f"lines: {lines.strip()}")

    return evidence


def _build_remediation_summary(result: dict[str, object], extra: object) -> str:
    if isinstance(extra, dict):
        message = extra.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    check_id = result.get("check_id", "the identified semgrep finding")
    return f"Review and remediate {check_id}."
