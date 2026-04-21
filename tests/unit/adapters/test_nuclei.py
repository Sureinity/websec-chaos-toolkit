import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.nuclei import NucleiAdapter
from toolkit.auth.session import AuthSession
from toolkit.config.models import AppConfig, AuthConfig, PentestToolSettings

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "nuclei"


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
        profile="safe",
        allowlisted_rules=["http/exposures", "network/exposure"],
    )


class NucleiAdapterTests(unittest.TestCase):
    def test_check_availability_uses_binary_lookup(self) -> None:
        adapter = NucleiAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=Path("/tmp/run/raw/nuclei/results.jsonl"),
        )

        with patch("toolkit.adapters.nuclei.check_binary_available") as check_binary_available:
            check_binary_available.return_value = AdapterAvailability(
                available=False,
                reason="nuclei binary was not found on PATH",
                binary="nuclei",
            )

            availability = adapter.check_availability()

        self.assertFalse(availability.available)
        self.assertEqual(availability.binary, "nuclei")

    def test_build_execution_uses_safe_allowlisted_command(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            output_path = Path(temp_dir_name) / "results.jsonl"
            adapter = NucleiAdapter(
                app=build_app(),
                settings=build_settings(),
                output_path=output_path,
            )

            execution = adapter.build_execution()

        self.assertEqual(execution.tool, "nuclei")
        self.assertEqual(
            execution.command,
            (
                "nuclei",
                "-jsonl",
                "-silent",
                "-o",
                str(output_path),
                "-target",
                "http://localhost:8000/",
                "-t",
                "http/exposures",
                "-t",
                "network/exposure",
            ),
        )
        self.assertEqual(execution.cwd, output_path.parent)
        self.assertEqual(execution.timeout_seconds, 300.0)
        self.assertEqual(
            execution.env_overrides,
            {"NUCLEI_DISABLE_UPDATE_CHECK": "true"},
        )

    def test_build_execution_supports_route_lists_and_auth_headers(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            output_path = Path(temp_dir_name) / "results.jsonl"
            adapter = NucleiAdapter(
                app=build_app(),
                settings=build_settings(),
                output_path=output_path,
                target_urls=("http://localhost:8000/", "http://localhost:8000/admin"),
                auth_session=AuthSession(
                    method="api_login",
                    headers={"Authorization": "Bearer token"},
                    cookies={"sessionid": "cookie-value"},
                ),
            )

            execution = adapter.build_execution()

        self.assertIn("-l", execution.command)
        self.assertIn("-H", execution.command)
        self.assertIn("Authorization: Bearer token", execution.command)
        self.assertIn("Cookie: sessionid=cookie-value", execution.command)
        self.assertEqual(execution.cwd, output_path.parent)

    def test_build_execution_supports_explicit_cookie_header(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            output_path = Path(temp_dir_name) / "results.jsonl"
            adapter = NucleiAdapter(
                app=build_app(),
                settings=build_settings(),
                output_path=output_path,
                auth_session=AuthSession(
                    method="form",
                    headers={"Cookie": "wordpress_cookie=admin; wordpress_cookie=root"},
                    cookie_header="wordpress_cookie=admin; wordpress_cookie=root",
                ),
            )

            execution = adapter.build_execution()

        self.assertIn("Cookie: wordpress_cookie=admin; wordpress_cookie=root", execution.command)

    def test_build_execution_blocks_when_safe_mode_is_disabled(self) -> None:
        adapter = NucleiAdapter(
            app=build_app(),
            settings=build_settings(safe_mode=False),
            output_path=Path("/tmp/run/raw/nuclei/results.jsonl"),
        )

        with self.assertRaisesRegex(ValueError, "safe_mode is disabled"):
            adapter.build_execution()

    def test_parse_artifact_normalizes_fixture_findings(self) -> None:
        adapter = NucleiAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-findings.jsonl",
        )

        findings = adapter.parse_artifact(
            started_at=datetime(2026, 3, 29, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 29, 1, 4, 5, tzinfo=UTC),
        )

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].tool, "nuclei")
        self.assertEqual(findings[0].category, "http")
        self.assertEqual(findings[0].severity, "medium")
        self.assertEqual(findings[0].confidence, "high")
        self.assertIn("template-id: http/exposures/panel", findings[0].evidence)
        self.assertEqual(findings[1].category, "network")
        self.assertEqual(findings[1].severity, "high")

    def test_build_fixture_result_preserves_artifact_and_findings(self) -> None:
        adapter = NucleiAdapter(
            app=build_app(),
            settings=build_settings(),
            output_path=FIXTURE_ROOT / "sample-findings.jsonl",
        )

        result = adapter.build_fixture_result(
            availability=AdapterAvailability(available=True, binary="nuclei"),
            started_at=datetime(2026, 3, 29, 1, 2, 3, tzinfo=UTC),
            finished_at=datetime(2026, 3, 29, 1, 4, 5, tzinfo=UTC),
        )

        self.assertFalse(result.skipped)
        self.assertFalse(result.failed)
        self.assertEqual(result.execution.tool, "nuclei")
        self.assertEqual(result.artifacts[0].path, FIXTURE_ROOT / "sample-findings.jsonl")
        self.assertEqual(result.artifacts[0].metadata, {"format": "jsonl"})
        self.assertEqual(len(result.findings), 2)
