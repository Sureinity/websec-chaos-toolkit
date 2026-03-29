"""Safe ZAP baseline adapter with fixture-driven normalization."""

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
class ZapAdapter:
    """Safe ZAP baseline wrapper for passive checks only."""

    app: AppConfig
    settings: PentestToolSettings
    output_path: Path

    name: str = "zap"
    binary: str = "zap-baseline.py"

    def check_availability(self) -> AdapterAvailability:
        return check_binary_available(self.binary)

    def build_execution(self) -> ToolExecution:
        if not self.settings.safe_mode:
            raise ValueError("zap adapter refuses to build commands when safe_mode is disabled.")

        return ToolExecution(
            tool=self.name,
            command=(
                self.binary,
                "-t",
                str(self.app.base_url),
                "-J",
                str(self.output_path),
                "-m",
                "1",
            ),
            timeout_seconds=600.0,
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

        for site in payload.get("site", []):
            for alert in site.get("alerts", []):
                category = _category_from_alert_name(alert.get("name", ""))
                if category not in self.settings.allowlisted_rules:
                    continue
                findings.append(
                    NormalizedResult(
                        app_id=self.app.id,
                        environment=self.app.environment,
                        target=_target_from_alert(alert, site.get("@name", str(self.app.base_url))),
                        tool=self.name,
                        category=category,
                        severity=_severity_from_riskcode(alert.get("riskcode")),
                        confidence=_confidence_from_confidence(alert.get("confidence")),
                        evidence=_build_evidence(alert),
                        remediation_summary=_build_remediation_summary(alert),
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


def _severity_from_riskcode(value: str | int | None) -> str:
    mapping = {
        "0": "info",
        "1": "low",
        "2": "medium",
        "3": "high",
        0: "info",
        1: "low",
        2: "medium",
        3: "high",
    }
    return mapping.get(value, "info")


def _confidence_from_confidence(value: str | int | None) -> str:
    mapping = {
        "0": "low",
        "1": "medium",
        "2": "high",
        "3": "high",
        0: "low",
        1: "medium",
        2: "high",
        3: "high",
    }
    return mapping.get(value, "medium")


def _category_from_alert_name(name: str) -> str:
    lowered = name.lower()
    if "header" in lowered:
        return "headers"
    if "tls" in lowered:
        return "tls"
    return "general"


def _target_from_alert(alert: dict[str, object], fallback: str) -> str:
    instances = alert.get("instances", [])
    if isinstance(instances, list) and instances:
        first = instances[0]
        if isinstance(first, dict):
            uri = first.get("uri")
            if isinstance(uri, str) and uri.strip():
                return uri.strip()
    return fallback


def _build_evidence(alert: dict[str, object]) -> list[str]:
    evidence: list[str] = []
    for field in ("pluginid", "name", "desc"):
        value = alert.get(field)
        if isinstance(value, str) and value.strip():
            evidence.append(f"{field}: {value.strip()}")
    return evidence


def _build_remediation_summary(alert: dict[str, object]) -> str:
    name = alert.get("name", "the identified issue")
    return f"Review and remediate {name}."
