"""Safe nmap adapter with fixture-driven normalization."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
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


@dataclass(slots=True, frozen=True)
class NmapAdapter:
    """Safe nmap wrapper using conservative discovery profiles."""

    app: AppConfig
    settings: PentestToolSettings
    output_path: Path

    name: str = "nmap"
    binary: str = "nmap"

    def check_availability(self) -> AdapterAvailability:
        return check_binary_available(self.binary)

    def build_execution(self) -> ToolExecution:
        if not self.settings.safe_mode:
            raise ValueError("nmap adapter refuses to build commands when safe_mode is disabled.")

        command = [
            self.binary,
            "-Pn",
            "-oX",
            str(self.output_path),
        ]
        command.extend(_profile_args(self.settings.profile))
        command.extend(self.app.host_targets)

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
            metadata={"format": "xml"},
        )

    def parse_artifact(
        self,
        artifact_path: Path | None = None,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> tuple[NormalizedResult, ...]:
        path = artifact_path or self.output_path
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        findings: list[NormalizedResult] = []
        resolved_started_at = started_at or datetime.now(UTC)

        for host in root.findall("host"):
            address = host.find("address")
            if address is None:
                continue
            host_target = address.attrib.get("addr", "")

            for port in host.findall("./ports/port"):
                state = port.find("state")
                if state is None or state.attrib.get("state") != "open":
                    continue

                service = port.find("service")
                port_id = port.attrib.get("portid", "")
                findings.append(
                    build_normalized_result(
                        app_id=self.app.id,
                        environment=self.app.environment,
                        target=f"{host_target}:{port_id}",
                        tool=self.name,
                        category="ports",
                        severity=_severity_for_service(
                            service.attrib.get("name", "") if service is not None else ""
                        ),
                        confidence="high",
                        evidence=_build_evidence(
                            service_name=service.attrib.get("name", "")
                            if service is not None
                            else "",
                            port_id=port_id,
                        ),
                        remediation_summary=_build_remediation_summary(
                            service_name=service.attrib.get("name", "")
                            if service is not None
                            else "",
                            port_id=port_id,
                        ),
                        started_at=resolved_started_at,
                        finished_at=finished_at,
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


def _profile_args(profile: str) -> tuple[str, ...]:
    if profile == "top-ports":
        return ("--top-ports", "100")
    if profile == "baseline":
        return ("-F",)
    return ("-F",)


def _severity_for_service(service_name: str) -> str:
    normalized = service_name.lower()
    if normalized in {"telnet", "ftp"}:
        return "high"
    if normalized in {"http", "https"}:
        return "low"
    return "medium"


def _build_evidence(*, service_name: str, port_id: str) -> list[str]:
    evidence = [f"port: {port_id}"]
    if service_name:
        evidence.append(f"service: {service_name}")
    return evidence


def _build_remediation_summary(*, service_name: str, port_id: str) -> str:
    if service_name:
        return f"Review why {service_name} is exposed on port {port_id} and restrict access if not required."
    return f"Review why port {port_id} is exposed and restrict access if not required."
