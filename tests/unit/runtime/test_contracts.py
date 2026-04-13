"""Tests for the container runtime contract definitions."""

import unittest

from toolkit.runtime.contracts import (
    CONTAINER_TOOL_ALIASES,
    CONTAINER_CORE_TOOLS,
    CONTAINER_TOOL_IMAGES,
    RuntimeMode,
)


class RuntimeContractTests(unittest.TestCase):
    def test_runtime_mode_covers_host_and_container(self) -> None:
        self.assertEqual(RuntimeMode.HOST, "host")
        self.assertEqual(RuntimeMode.CONTAINER, "container")

    def test_container_images_defined_for_all_core_tools(self) -> None:
        for tool in CONTAINER_CORE_TOOLS:
            self.assertIn(
                tool,
                CONTAINER_TOOL_IMAGES,
                f"missing container image for core tool: {tool}",
            )

    def test_core_tools_match_pentest_core_tool_set(self) -> None:
        self.assertEqual(
            CONTAINER_CORE_TOOLS,
            frozenset({"zap", "nuclei", "nmap"}),
        )

    def test_container_images_include_optional_tools(self) -> None:
        for tool in ("trivy", "semgrep"):
            self.assertIn(tool, CONTAINER_TOOL_IMAGES)

    def test_container_images_are_non_empty_strings(self) -> None:
        for tool, image in CONTAINER_TOOL_IMAGES.items():
            self.assertIsInstance(image, str)
            self.assertTrue(
                image.strip(),
                f"container image for {tool} must be non-empty",
            )

    def test_container_aliases_cover_zap_binary_name(self) -> None:
        self.assertEqual(
            CONTAINER_TOOL_ALIASES["zap-baseline.py"],
            "zap",
        )
