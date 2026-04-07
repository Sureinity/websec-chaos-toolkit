"""Tests for the Docker container runtime backend."""

import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.runtime.container import ContainerRuntime
from toolkit.runtime.models import RuntimeRequest


class ContainerRuntimeAvailabilityTests(unittest.TestCase):
    def test_available_when_docker_and_image_exist(self) -> None:
        runtime = ContainerRuntime()
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=Path("/usr/bin/docker"),
        ):
            result = runtime.check_tool_available("nmap")

        self.assertTrue(result.available)
        self.assertIn("docker", result.binary)
        self.assertIn("nmap", result.binary)

    def test_unavailable_when_docker_missing(self) -> None:
        runtime = ContainerRuntime()
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=None,
        ):
            result = runtime.check_tool_available("nmap")

        self.assertFalse(result.available)
        self.assertIn("docker", result.reason)

    def test_unavailable_when_no_image_configured(self) -> None:
        runtime = ContainerRuntime()
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=Path("/usr/bin/docker"),
        ):
            result = runtime.check_tool_available("unknown-tool")

        self.assertFalse(result.available)
        self.assertIn("no container image", result.reason)

    def test_image_override_takes_precedence(self) -> None:
        runtime = ContainerRuntime(
            image_overrides={"nmap": "my-registry/nmap:v1"}
        )
        with patch(
            "toolkit.runtime.container.find_binary",
            return_value=Path("/usr/bin/docker"),
        ):
            result = runtime.check_tool_available("nmap")

        self.assertTrue(result.available)
        self.assertIn("my-registry/nmap:v1", result.binary)


class ContainerCommandBuildTests(unittest.TestCase):
    def test_builds_docker_run_with_network_host(self) -> None:
        runtime = ContainerRuntime()
        request = RuntimeRequest(
            tool="nmap",
            command=("nmap", "-F", "localhost"),
            output_path=Path("/tmp/outputs/nmap/results.xml"),
        )

        cmd = runtime._build_docker_command(
            request, image="instrumentisto/nmap:latest"
        )

        self.assertEqual(cmd[0], "docker")
        self.assertEqual(cmd[1], "run")
        self.assertIn("--rm", cmd)
        self.assertIn("--network=host", cmd)
        self.assertIn("instrumentisto/nmap:latest", cmd)
        # Original command args (minus binary) appended after image.
        self.assertIn("-F", cmd)
        self.assertIn("localhost", cmd)

    def test_mounts_output_directory(self) -> None:
        runtime = ContainerRuntime()
        request = RuntimeRequest(
            tool="nmap",
            command=("nmap",),
            output_path=Path("/tmp/outputs/nmap/results.xml"),
        )

        cmd = runtime._build_docker_command(
            request, image="instrumentisto/nmap:latest"
        )

        idx = cmd.index("-v")
        mount = cmd[idx + 1]
        self.assertIn("/tmp/outputs/nmap", mount)

    def test_forwards_env_overrides(self) -> None:
        runtime = ContainerRuntime()
        request = RuntimeRequest(
            tool="nuclei",
            command=("nuclei",),
            output_path=Path("/tmp/outputs/nuclei/results.jsonl"),
            env_overrides={"NUCLEI_DISABLE_UPDATE_CHECK": "true"},
        )

        cmd = runtime._build_docker_command(
            request, image="projectdiscovery/nuclei:latest"
        )

        idx = cmd.index("-e")
        env_val = cmd[idx + 1]
        self.assertEqual(env_val, "NUCLEI_DISABLE_UPDATE_CHECK=true")

    def test_mounts_cwd_when_different_from_output(self) -> None:
        runtime = ContainerRuntime()
        request = RuntimeRequest(
            tool="trivy",
            command=("trivy", "fs", "."),
            output_path=Path("/tmp/outputs/trivy/results.json"),
            cwd=Path("/app/src"),
        )

        cmd = runtime._build_docker_command(
            request, image="aquasec/trivy:latest"
        )

        mount_args = [
            cmd[i + 1] for i in range(len(cmd)) if cmd[i] == "-v"
        ]
        self.assertTrue(
            any("/app/src" in m for m in mount_args),
            f"cwd mount not found in {mount_args}",
        )


class ContainerExecutionTests(unittest.TestCase):
    def test_execute_returns_failure_for_missing_image(self) -> None:
        runtime = ContainerRuntime(image_overrides={})
        request = RuntimeRequest(
            tool="unknown",
            command=("unknown",),
            output_path=Path("/tmp/out"),
        )

        result = runtime.execute(request)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no container image", result.stderr)
