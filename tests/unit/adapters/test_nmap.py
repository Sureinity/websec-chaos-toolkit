import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.nmap import NmapAdapter
from toolkit.config.models import AppConfig, AuthConfig, PentestToolSettings

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "nmap"


def build_app() -> AppConfig:
    return AppConfig(
        id="sample-app",
        environment="local",
        base_url="http://localhost:8000",
        host_targets=["localhost", "127.0.0.1"],
        target_allowlist=["localhost", "127.0.0.1"],
        auth=AuthConfig(method="none"),
        health_endpoint="/health",
        enabled_modules=["pentest"],
    )


def build_settings(*, safe_mode: bool = True, profile: str = "top-ports") -> PentestToolSettings:
    return PentestToolSettings(
        enabled=True,
        safe_mode=safe_mode,
        profile=profile,
        allowlisted_rules=["conservative-tcp"],
    )


class NmapAdapterTests(unittest.TestCase):
    def test_check_availability_uses_binary_lookup(self) -> None:
        adapter = NmapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/nmap/results.xml"),
        )

        with patch("toolkit.adapters.nmap.check_binary_available") as check_binary_available:
            check_binary_available.return_value = AdapterAvailability(
                available=False,
                reason="nmap binary was not found on PATH",
                binary="nmap",
            )

            availability = adapter.check_availability()

        self.assertFalse(availability.available)
        self.assertEqual(availability.binary, "nmap")

    def test_build_execution_uses_safe_profile_command(self) -> None:
        adapter = NmapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/nmap/results.xml"),
        )

        execution = adapter.build_execution()

        self.assertEqual(
            execution.command,
            (
                "nmap",
                "-Pn",
                "-oX",
                "/tmp/run/raw/nmap/results.xml",
                "--top-ports",
                "100",
                "localhost",
                "127.0.0.1",
            ),
        )
        self.assertEqual(execution.timeout_seconds, 300.0)

    def test_build_execution_blocks_when_safe_mode_is_disabled(self) -> None:
        adapter = NmapAdapter(
            app=build_app(),
            settings=build_settings(safe_mode=False),
            output_path=Path("/tmp/run/raw/nmap/results.xml"),
        )

        with self.assertRaisesRegex(ValueError, "safe_mode is disabled"):
            adapter.build_execution()

    def test_parse_artifact_normalizes_open_ports(self) -> None:
        adapter = NmapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-scan.xml",
        )

        findings = adapter.parse_artifact(
            started_at=datetime(2026, 3, 29, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 29, 1, 4, 5, tzinfo=UTC),
        )

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].category, "ports")
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[0].target, "127.0.0.1:23")
        self.assertEqual(findings[1].severity, "low")
        self.assertEqual(findings[1].target, "127.0.0.1:80")

    def test_build_fixture_result_preserves_artifact_and_findings(self) -> None:
        adapter = NmapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-scan.xml",
        )

        result = adapter.build_fixture_result(
            availability=AdapterAvailability(available=True, binary="nmap"),
            started_at=datetime(2026, 3, 29, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 29, 1, 4, 5, tzinfo=UTC),
        )

        self.assertFalse(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.execution.tool, "nmap")
        self.assertEqual(result.artifacts[0].metadata, {"format": "xml"})
        self.assertEqual(len(result.findings), 2)
