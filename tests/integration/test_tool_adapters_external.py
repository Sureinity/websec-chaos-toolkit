import os
from pathlib import Path
import unittest

from toolkit.adapters.base import ToolExecution
from toolkit.adapters.nmap import NmapAdapter
from toolkit.adapters.nuclei import NucleiAdapter
from toolkit.adapters.process import run_tool_execution
from toolkit.adapters.zap import ZapAdapter
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


def build_settings(*, allowlisted_rules: list[str], profile: str = "baseline") -> PentestToolSettings:
    return PentestToolSettings(
        enabled=True,
        safe_mode=True,
        profile=profile,
        allowlisted_rules=allowlisted_rules,
    )


class ExternalToolAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get(_EXTERNAL_FLAG) != "1":
            raise unittest.SkipTest(
                f"Set {_EXTERNAL_FLAG}=1 to run external tool adapter smoke tests."
            )

    def test_nuclei_binary_is_available_and_responds_to_version(self) -> None:
        adapter = NucleiAdapter(
            app=build_app(),
            settings=build_settings(
                allowlisted_rules=["http/exposures", "network/exposure"],
                profile="safe",
            ),
            output_path=Path("/tmp/nuclei-smoke.jsonl"),
        )

        availability = adapter.check_availability()
        if not availability.available:
            self.skipTest("nuclei binary is not installed")

        result = run_tool_execution(
            ToolExecution(
                tool="nuclei",
                command=(adapter.binary, "-version"),
                timeout_seconds=30.0,
            )
        )

        self.assertTrue(result.succeeded)
        self.assertIn("nuclei", (result.stdout + result.stderr).lower())

    def test_nmap_binary_is_available_and_responds_to_version(self) -> None:
        adapter = NmapAdapter(
            app=build_app(),
            settings=build_settings(
                allowlisted_rules=["conservative-tcp"],
                profile="top-ports",
            ),
            output_path=Path("/tmp/nmap-smoke.xml"),
        )

        availability = adapter.check_availability()
        if not availability.available:
            self.skipTest("nmap binary is not installed")

        result = run_tool_execution(
            ToolExecution(
                tool="nmap",
                command=(adapter.binary, "--version"),
                timeout_seconds=30.0,
            )
        )

        self.assertTrue(result.succeeded)
        self.assertIn("nmap", (result.stdout + result.stderr).lower())

    def test_zap_baseline_binary_is_available_and_responds_to_help(self) -> None:
        adapter = ZapAdapter(
            app=build_app(),
            settings=build_settings(
                allowlisted_rules=["headers", "tls"],
                profile="baseline",
            ),
            output_path=Path("/tmp/zap-smoke.json"),
        )

        availability = adapter.check_availability()
        if not availability.available:
            self.skipTest("zap-baseline.py is not installed")

        result = run_tool_execution(
            ToolExecution(
                tool="zap",
                command=(adapter.binary, "-h"),
                timeout_seconds=30.0,
            )
        )

        self.assertTrue(result.succeeded)
        self.assertIn("zap", (result.stdout + result.stderr).lower())
