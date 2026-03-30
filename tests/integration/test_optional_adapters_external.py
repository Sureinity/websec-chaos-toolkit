import os
from pathlib import Path
import unittest

from toolkit.adapters.base import ToolExecution
from toolkit.adapters.process import run_tool_execution
from toolkit.adapters.semgrep import SemgrepAdapter
from toolkit.adapters.trivy import TrivyAdapter
from toolkit.config.models import AppConfig, AuthConfig, PentestToolSettings

_EXTERNAL_FLAG = "TOOLKIT_RUN_EXTERNAL_TOOL_TESTS"


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


def build_settings(*, allowlisted_rules: list[str], profile: str) -> PentestToolSettings:
    return PentestToolSettings(
        enabled=True,
        safe_mode=True,
        profile=profile,
        allowlisted_rules=allowlisted_rules,
    )


class OptionalExternalAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get(_EXTERNAL_FLAG) != "1":
            raise unittest.SkipTest(
                f"Set {_EXTERNAL_FLAG}=1 to run optional adapter external smoke tests."
            )

    def test_trivy_binary_is_available_and_responds_to_version(self) -> None:
        adapter = TrivyAdapter(
            app=build_app(),
            settings=build_settings(
                allowlisted_rules=["vulnerabilities", "misconfigurations"],
                profile="config-audit",
            ),
            output_path=Path("/tmp/trivy-smoke.json"),
        )

        availability = adapter.check_availability()
        if not availability.available:
            self.skipTest("trivy binary is not installed")

        result = run_tool_execution(
            ToolExecution(
                tool="trivy",
                command=(adapter.binary, "--version"),
                timeout_seconds=30.0,
            )
        )

        self.assertTrue(result.succeeded)
        self.assertIn("trivy", (result.stdout + result.stderr).lower())

    def test_semgrep_binary_is_available_and_responds_to_version(self) -> None:
        adapter = SemgrepAdapter(
            app=build_app(),
            settings=build_settings(
                allowlisted_rules=["p/default", "p/secrets"],
                profile="default",
            ),
            output_path=Path("/tmp/semgrep-smoke.json"),
        )

        availability = adapter.check_availability()
        if not availability.available:
            self.skipTest("semgrep binary is not installed")

        result = run_tool_execution(
            ToolExecution(
                tool="semgrep",
                command=(adapter.binary, "--version"),
                timeout_seconds=30.0,
            )
        )

        self.assertTrue(result.succeeded)
        self.assertIn("semgrep", (result.stdout + result.stderr).lower())
