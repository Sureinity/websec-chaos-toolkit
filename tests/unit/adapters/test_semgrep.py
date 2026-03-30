from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.semgrep import SemgrepAdapter
from toolkit.config.models import AppConfig, AuthConfig, PentestToolSettings

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "semgrep"


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
        profile="default",
        allowlisted_rules=["p/default", "p/secrets"],
    )


class SemgrepAdapterTests(unittest.TestCase):
    def test_check_availability_uses_binary_lookup(self) -> None:
        adapter = SemgrepAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/semgrep/results.json"),
        )

        with patch("toolkit.adapters.semgrep.check_binary_available") as check_binary_available:
            check_binary_available.return_value = AdapterAvailability(
                available=False,
                reason="semgrep binary was not found on PATH",
                binary="semgrep",
            )

            availability = adapter.check_availability()

        self.assertFalse(availability.available)
        self.assertEqual(availability.binary, "semgrep")

    def test_build_execution_uses_safe_read_only_command(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            output_path = Path(temp_dir_name) / "results.json"
            target_path = Path(temp_dir_name) / "sample-repo"
            target_path.mkdir()
            adapter = SemgrepAdapter(
                app=build_app(),
                settings=build_settings(),
                output_path=output_path,
                target_path=target_path,
            )

            execution = adapter.build_execution()

        self.assertEqual(
            execution.command,
            (
                "semgrep",
                "scan",
                f"--json-output={output_path}",
                "--quiet",
                "--config",
                "p/default",
                "--config",
                "p/secrets",
                str(target_path),
            ),
        )
        self.assertEqual(execution.timeout_seconds, 300.0)

    def test_build_execution_blocks_when_safe_mode_is_disabled(self) -> None:
        adapter = SemgrepAdapter(
            app=build_app(),
            settings=build_settings(safe_mode=False),
            output_path=Path("/tmp/run/raw/semgrep/results.json"),
        )

        with self.assertRaisesRegex(ValueError, "safe_mode is disabled"):
            adapter.build_execution()

    def test_parse_artifact_normalizes_fixture_findings(self) -> None:
        adapter = SemgrepAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-results.json",
        )

        findings = adapter.parse_artifact(
            started_at=datetime(2026, 3, 30, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 30, 1, 4, 5, tzinfo=UTC),
        )

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].tool, "semgrep")
        self.assertEqual(findings[0].category, "security")
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[0].confidence, "high")
        self.assertIn(
            "check_id: python.lang.security.audit.dangerous-subprocess-use",
            findings[0].evidence,
        )
        self.assertEqual(findings[1].category, "secrets")
        self.assertEqual(findings[1].severity, "medium")

    def test_build_fixture_result_preserves_artifact_and_findings(self) -> None:
        adapter = SemgrepAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-results.json",
        )

        result = adapter.build_fixture_result(
            availability=AdapterAvailability(available=True, binary="semgrep"),
            started_at=datetime(2026, 3, 30, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 30, 1, 4, 5, tzinfo=UTC),
        )

        self.assertFalse(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.execution.tool, "semgrep")
        self.assertEqual(result.artifacts[0].path, FIXTURE_ROOT / "sample-results.json")
        self.assertEqual(result.artifacts[0].metadata, {"format": "json"})
        self.assertEqual(len(result.findings), 2)
