"""Safe Trivy adapter with fixture-driven normalization."""

import json
from dataclasses import dataclass, field
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

_SCANNER_MAPPING = {
    "vulnerabilities": "vuln",
    "misconfigurations": "misconfig",
    "secrets": "secret",
}


@dataclass(slots=True, frozen=True)
class TrivyAdapter:
    """Safe Trivy wrapper for read-only filesystem and config checks."""

    app: AppConfig
    settings: PentestToolSettings
    output_path: Path
    target_path: Path = field(default_factory=lambda: Path("."))

    name: str = "trivy"
    binary: str = "trivy"

    def check_availability(self) -> AdapterAvailability:
        return check_binary_available(self.binary)

    def build_execution(self) -> ToolExecution:
        if not self.settings.safe_mode:
            raise ValueError("trivy adapter refuses to build commands when safe_mode is disabled.")

        scanners = _scanners_from_allowlist(self.settings.allowlisted_rules)
        if not scanners:
            raise ValueError(
                "trivy adapter requires at least one supported allowlisted rule category."
            )

        return ToolExecution(
            tool=self.name,
            command=(
                self.binary,
                "fs",
                "--format",
                "json",
                "--output",
                str(self.output_path),
                "--quiet",
                "--skip-db-update",
                "--skip-java-db-update",
                "--scanners",
                ",".join(scanners),
                str(self.target_path),
            ),
            timeout_seconds=300.0,
            env_overrides={"TRIVY_NON_SSL": "true"},
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
        allowed_categories = {value.lower() for value in self.settings.allowlisted_rules}

        for result in payload.get("Results", []):
            target = result.get("Target", str(self.target_path))

            if "vulnerabilities" in allowed_categories:
                for vulnerability in result.get("Vulnerabilities", []):
                    findings.append(
                        build_normalized_result(
                            app_id=self.app.id,
                            environment=self.app.environment,
                            target=_target_with_package(target, vulnerability.get("PkgName")),
                            tool=self.name,
                            category="vulnerabilities",
                            severity=vulnerability.get("Severity"),
                            confidence=_vulnerability_confidence(vulnerability),
                            evidence=_build_vulnerability_evidence(vulnerability),
                            remediation_summary=_build_vulnerability_remediation(vulnerability),
                            started_at=resolved_started_at,
                            finished_at=finished_at,
                        )
                    )

            if "misconfigurations" in allowed_categories:
                for misconfiguration in result.get("Misconfigurations", []):
                    findings.append(
                        build_normalized_result(
                            app_id=self.app.id,
                            environment=self.app.environment,
                            target=str(target),
                            tool=self.name,
                            category="misconfigurations",
                            severity=misconfiguration.get("Severity"),
                            confidence="high",
                            evidence=_build_misconfiguration_evidence(misconfiguration),
                            remediation_summary=_build_misconfiguration_remediation(
                                misconfiguration
                            ),
                            started_at=resolved_started_at,
                            finished_at=finished_at,
                        )
                    )

            if "secrets" in allowed_categories:
                for secret in result.get("Secrets", []):
                    findings.append(
                        build_normalized_result(
                            app_id=self.app.id,
                            environment=self.app.environment,
                            target=str(target),
                            tool=self.name,
                            category="secrets",
                            severity=secret.get("Severity", "high"),
                            confidence="high",
                            evidence=_build_secret_evidence(secret),
                            remediation_summary=_build_secret_remediation(secret),
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


def _scanners_from_allowlist(allowlisted_rules: list[str]) -> tuple[str, ...]:
    scanners: list[str] = []
    for rule in allowlisted_rules:
        mapped = _SCANNER_MAPPING.get(rule.strip().lower())
        if mapped is not None and mapped not in scanners:
            scanners.append(mapped)
    return tuple(scanners)


def _target_with_package(target: object, package_name: object) -> str:
    resolved_target = str(target)
    if isinstance(package_name, str) and package_name.strip():
        return f"{resolved_target}:{package_name.strip()}"
    return resolved_target


def _vulnerability_confidence(vulnerability: dict[str, object]) -> str:
    if vulnerability.get("PrimaryURL") or vulnerability.get("FixedVersion"):
        return "high"
    if vulnerability.get("Title"):
        return "medium"
    return "low"


def _build_vulnerability_evidence(vulnerability: dict[str, object]) -> list[str]:
    evidence: list[str] = []
    for field in ("VulnerabilityID", "PkgName", "InstalledVersion", "FixedVersion", "Title"):
        value = vulnerability.get(field)
        if isinstance(value, str) and value.strip():
            evidence.append(f"{field}: {value.strip()}")
    return evidence


def _build_misconfiguration_evidence(misconfiguration: dict[str, object]) -> list[str]:
    evidence: list[str] = []
    for field in ("ID", "Title", "Resolution"):
        value = misconfiguration.get(field)
        if isinstance(value, str) and value.strip():
            evidence.append(f"{field}: {value.strip()}")
    return evidence


def _build_secret_evidence(secret: dict[str, object]) -> list[str]:
    evidence: list[str] = []
    for field in ("RuleID", "Title", "Category"):
        value = secret.get(field)
        if isinstance(value, str) and value.strip():
            evidence.append(f"{field}: {value.strip()}")
    return evidence


def _build_vulnerability_remediation(vulnerability: dict[str, object]) -> str:
    fixed_version = vulnerability.get("FixedVersion")
    if isinstance(fixed_version, str) and fixed_version.strip():
        return f"Upgrade to the fixed version {fixed_version.strip()}."
    title = vulnerability.get("Title", "the identified vulnerability")
    return f"Review and remediate {title}."


def _build_misconfiguration_remediation(misconfiguration: dict[str, object]) -> str:
    resolution = misconfiguration.get("Resolution")
    if isinstance(resolution, str) and resolution.strip():
        return resolution.strip()
    title = misconfiguration.get("Title", "the identified misconfiguration")
    return f"Review and remediate {title}."


def _build_secret_remediation(secret: dict[str, object]) -> str:
    title = secret.get("Title", "the identified secret exposure")
    return f"Remove or rotate the secret material related to {title}."
