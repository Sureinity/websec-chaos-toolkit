"""Integration tests for the container runtime backend.

These tests verify Docker command construction and availability
behavior without requiring a real Docker installation.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.runtime.container import ContainerRuntime
from toolkit.runtime.contracts import CONTAINER_TOOL_IMAGES, RuntimeMode
from toolkit.runtime.host import HostRuntime
from toolkit.runtime.models import RuntimeRequest


class RuntimeModeSelectionTests(unittest.TestCase):
    def test_host_mode_uses_host_runtime(self) -> None:
        runtime = HostRuntime()
        with patch(
            "toolkit.runtime.host.find_binary",
            return_value=Path("/usr/bin/nmap"),
        ):
            availability = runtime.check_tool_available("nmap")

        self.assertTrue(availability.available)
        self.assertNotIn("docker", availability.binary)

    def test_container_mode_uses_container_runtime(self) -> None:
        runtime = ContainerRuntime()
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=Path("/usr/bin/docker"),
        ):
            availability = runtime.check_tool_available("nmap")

        self.assertTrue(availability.available)
        self.assertIn("docker", availability.binary)


class ContainerRuntimeIntegrationTests(unittest.TestCase):
    def test_docker_command_preserves_tool_arguments(self) -> None:
        runtime = ContainerRuntime()
        request = RuntimeRequest(
            tool="nuclei",
            command=(
                "nuclei",
                "-target",
                "http://localhost:8080",
                "-jsonl",
                "-o",
                "/outputs/results.jsonl",
            ),
            output_path=Path("/outputs/results.jsonl"),
            env_overrides={"NUCLEI_DISABLE_UPDATE_CHECK": "true"},
        )

        cmd = runtime._build_docker_command(
            request, image="projectdiscovery/nuclei:latest"
        )

        # Tool args (without binary) are appended after the image.
        image_idx = list(cmd).index("projectdiscovery/nuclei:latest")
        tool_args = cmd[image_idx + 1 :]
        self.assertEqual(
            tool_args,
            (
                "-target",
                "http://localhost:8080",
                "-jsonl",
                "-o",
                "/outputs/results.jsonl",
            ),
        )

    def test_all_core_tools_have_container_images(self) -> None:
        runtime = ContainerRuntime()
        for tool in ("zap", "nuclei", "nmap"):
            image = runtime._resolve_image(tool)
            self.assertIsNotNone(image, f"no image for core tool: {tool}")

    def test_image_override_replaces_default(self) -> None:
        runtime = ContainerRuntime(
            image_overrides={"nmap": "custom/nmap:v2"}
        )
        image = runtime._resolve_image("nmap")
        self.assertEqual(image, "custom/nmap:v2")
