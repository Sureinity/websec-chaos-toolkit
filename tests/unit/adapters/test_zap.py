from datetime import UTC, datetime
from pathlib import Path
import unittest
from unittest.mock import patch

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.zap import ZapAdapter
from toolkit.config.models import AppConfig, AuthConfig, PentestToolSettings

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "zap"


def build_app() -> AppConfig:
    return AppConfig(
        id="sample-app",
        environment="local",
        base_url="http://localhost:8000",
        host_targets=["localhost"],
        target_allowlist=["localhost", "127.0.0.1"],
        auth=AuthConfig(method="none"),
        health_endpoint="/health",
        enabled_modules=["pentest"],
    )


def build_settings(*, safe_mode: bool = True) -> PentestToolSettings:
    return PentestToolSettings(
        enabled=True,
        safe_mode=safe_mode,
        profile="baseline",
        allowlisted_rules=["headers", "tls"],
    )


class ZapAdapterTests(unittest.TestCase):
    def test_check_availability_uses_binary_lookup(self) -> None:
        adapter = ZapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/zap/results.json"),
        )

        with patch("toolkit.adapters.zap.check_binary_available") as check_binary_available:
            check_binary_available.return_value = AdapterAvailability(
                available=False,
                reason="zap-baseline.py binary was not found on PATH",
                binary="zap-baseline.py",
            )

            availability = adapter.check_availability()

        self.assertFalse(availability.available)
        self.assertEqual(availability.binary, "zap-baseline.py")

    def test_build_execution_uses_safe_baseline_command(self) -> None:
        adapter = ZapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/zap/results.json"),
        )

        execution = adapter.build_execution()

        self.assertEqual(
            execution.command,
            (
                "zap-baseline.py",
                "-t",
                "http://localhost:8000/",
                "-J",
                "/tmp/run/raw/zap/results.json",
                "-m",
                "1",
            ),
        )
        self.assertEqual(execution.timeout_seconds, 600.0)

    def test_build_execution_blocks_when_safe_mode_is_disabled(self) -> None:
        adapter = ZapAdapter(
            app=build_app(),
            settings=build_settings(safe_mode=False),
            output_path=Path("/tmp/run/raw/zap/results.json"),
        )

        with self.assertRaisesRegex(ValueError, "safe_mode is disabled"):
            adapter.build_execution()

    def test_parse_artifact_filters_to_allowlisted_categories(self) -> None:
        adapter = ZapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-baseline.json",
        )

        findings = adapter.parse_artifact(
            started_at=datetime(2026, 3, 29, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 29, 1, 4, 5, tzinfo=UTC),
        )

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].category, "headers")
        self.assertEqual(findings[0].severity, "low")
        self.assertEqual(findings[0].confidence, "high")
        self.assertEqual(findings[1].category, "tls")
        self.assertEqual(findings[1].severity, "medium")

    def test_build_fixture_result_preserves_artifact_and_findings(self) -> None:
        adapter = ZapAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-baseline.json",
        )

        result = adapter.build_fixture_result(
            availability=AdapterAvailability(available=True, binary="zap-baseline.py"),
            started_at=datetime(2026, 3, 29, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 29, 1, 4, 5, tzinfo=UTC),
        )

        self.assertFalse(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.execution.tool, "zap")
        self.assertEqual(result.artifacts[0].metadata, {"format": "json"})
        self.assertEqual(len(result.findings), 2)
