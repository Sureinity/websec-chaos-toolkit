from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.trivy import TrivyAdapter
from toolkit.config.models import AppConfig, AuthConfig, PentestToolSettings

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "trivy"


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


def build_settings(
    *,
    safe_mode: bool = True,
    allowlisted_rules: list[str] | None = None,
) -> PentestToolSettings:
    return PentestToolSettings(
        enabled=True,
        safe_mode=safe_mode,
        profile="config-audit",
        allowlisted_rules=allowlisted_rules or ["vulnerabilities", "misconfigurations"],
    )


class TrivyAdapterTests(unittest.TestCase):
    def test_check_availability_uses_binary_lookup(self) -> None:
        adapter = TrivyAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/trivy/results.json"),
        )

        with patch("toolkit.adapters.trivy.check_binary_available") as check_binary_available:
            check_binary_available.return_value = AdapterAvailability(
                available=False,
                reason="trivy binary was not found on PATH",
                binary="trivy",
            )

            availability = adapter.check_availability()

        self.assertFalse(availability.available)
        self.assertEqual(availability.binary, "trivy")

    def test_build_execution_uses_safe_read_only_command(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            output_path = Path(temp_dir_name) / "results.json"
            target_path = Path(temp_dir_name) / "sample-repo"
            target_path.mkdir()
            adapter = TrivyAdapter(
                app=build_app(),
                settings=build_settings(),
                output_path=output_path,
                target_path=target_path,
            )

            execution = adapter.build_execution()

        self.assertEqual(
            execution.command,
            (
                "trivy",
                "fs",
                "--format",
                "json",
                "--output",
                str(output_path),
                "--quiet",
                "--scanners",
                "vuln,misconfig",
                ".",
            ),
        )
        self.assertEqual(execution.cwd, target_path.resolve())
        self.assertEqual(execution.timeout_seconds, 300.0)
        self.assertEqual(execution.env_overrides, {"TRIVY_NON_SSL": "true"})

    def test_build_execution_blocks_when_safe_mode_is_disabled(self) -> None:
        adapter = TrivyAdapter(
            app=build_app(),
            settings=build_settings(safe_mode=False),
            output_path=Path("/tmp/run/raw/trivy/results.json"),
        )

        with self.assertRaisesRegex(ValueError, "safe_mode is disabled"):
            adapter.build_execution()

    def test_build_execution_requires_supported_allowlisted_categories(self) -> None:
        adapter = TrivyAdapter(
            app=build_app(),
            settings=build_settings(allowlisted_rules=["unknown-category"]),
            output_path=Path("/tmp/run/raw/trivy/results.json"),
        )

        with self.assertRaisesRegex(ValueError, "supported allowlisted rule category"):
            adapter.build_execution()

    def test_build_execution_requires_explicit_target_for_filesystem_mode(self) -> None:
        adapter = TrivyAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/trivy/results.json"),
        )

        with patch.dict("os.environ", {}, clear=False):
            with self.assertRaisesRegex(ValueError, "TOOLKIT_TRIVY_TARGET_PATH"):
                adapter.build_execution()

    def test_build_execution_supports_image_audit_mode(self) -> None:
        adapter = TrivyAdapter(
            app=build_app(),
            settings=PentestToolSettings(
                enabled=True,
                safe_mode=True,
                profile="image-audit",
                allowlisted_rules=["vulnerabilities"],
            ),
            output_path=Path("/tmp/run/raw/trivy/results.json"),
        )

        with patch.dict("os.environ", {"TOOLKIT_TRIVY_IMAGE_REF": "demo/image:latest"}):
            execution = adapter.build_execution()

        self.assertEqual(
            execution.command,
            (
                "trivy",
                "image",
                "--format",
                "json",
                "--output",
                "/tmp/run/raw/trivy/results.json",
                "--quiet",
                "demo/image:latest",
            ),
        )
        self.assertIsNone(execution.cwd)

    def test_parse_artifact_normalizes_fixture_findings(self) -> None:
        adapter = TrivyAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-results.json",
        )

        findings = adapter.parse_artifact(
            started_at=datetime(2026, 3, 30, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 30, 1, 4, 5, tzinfo=UTC),
        )

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].tool, "trivy")
        self.assertEqual(findings[0].category, "vulnerabilities")
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[0].confidence, "high")
        self.assertIn("VulnerabilityID: CVE-2026-0001", findings[0].evidence)
        self.assertEqual(findings[1].category, "misconfigurations")
        self.assertEqual(findings[1].severity, "medium")

    def test_build_fixture_result_preserves_artifact_and_findings(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            target_path = Path(temp_dir_name) / "sample-repo"
            target_path.mkdir()
            adapter = TrivyAdapter(
                app=build_app(),
                settings=build_settings(),
                output_path=FIXTURE_ROOT / "sample-results.json",
                target_path=target_path,
            )

            result = adapter.build_fixture_result(
                availability=AdapterAvailability(available=True, binary="trivy"),
                started_at=datetime(2026, 3, 30, 1, 2, 3, tzinfo=UTC),
                finished_at=datetime(2026, 3, 30, 1, 4, 5, tzinfo=UTC),
            )

        self.assertFalse(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.execution.tool, "trivy")
        self.assertEqual(result.artifacts[0].path, FIXTURE_ROOT / "sample-results.json")
        self.assertEqual(result.artifacts[0].metadata, {"format": "json"})
        self.assertEqual(len(result.findings), 2)
