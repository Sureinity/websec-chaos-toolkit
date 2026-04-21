"""Tests for the host runtime backend."""

import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.adapters.base import ToolExecution
from toolkit.adapters.process import ProcessResult
from toolkit.core.logging import ProcessLogContext
from toolkit.runtime.host import HostRuntime
from toolkit.runtime.models import RuntimeRequest


class HostRuntimeAvailabilityTests(unittest.TestCase):
    def test_available_when_binary_exists(self) -> None:
        runtime = HostRuntime()
        with patch(
            "toolkit.runtime.host.find_binary",
            return_value=Path("/usr/bin/nmap"),
        ):
            result = runtime.check_tool_available("nmap")

        self.assertTrue(result.available)
        self.assertEqual(result.binary, "/usr/bin/nmap")

    def test_unavailable_when_binary_missing(self) -> None:
        runtime = HostRuntime()
        with patch(
            "toolkit.runtime.host.find_binary",
            return_value=None,
        ):
            result = runtime.check_tool_available("nmap")

        self.assertFalse(result.available)
        self.assertIn("nmap", result.reason)


class HostRuntimeExecutionTests(unittest.TestCase):
    def test_execute_captures_stdout_and_returncode(self) -> None:
        runtime = HostRuntime()
        request = RuntimeRequest(
            tool="echo",
            command=("echo", "hello"),
            output_path=Path("/dev/null"),
        )

        with patch(
            "toolkit.runtime.host.run_process_command",
            return_value=ProcessResult(
                command=request.command,
                returncode=0,
                stdout="hello\n",
                stderr="",
            ),
        ) as run_process:
            result = runtime.execute(request)

        self.assertEqual(result.returncode, 0)
        self.assertIn("hello", result.stdout)
        self.assertTrue(result.succeeded)
        run_process.assert_called_once_with(
            command=request.command,
            cwd=None,
            env_overrides={},
            timeout_seconds=None,
            stream_output=True,
            log_context=ProcessLogContext(
                runtime="host",
                tool="echo",
                output_path=Path("/dev/null"),
                cwd=None,
            ),
        )

    def test_execute_captures_nonzero_returncode(self) -> None:
        runtime = HostRuntime()
        request = RuntimeRequest(
            tool="false",
            command=("false",),
            output_path=Path("/dev/null"),
        )

        with patch(
            "toolkit.runtime.host.run_process_command",
            return_value=ProcessResult(
                command=request.command,
                returncode=1,
                stdout="",
                stderr="failed\n",
            ),
        ):
            result = runtime.execute(request)

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(result.succeeded)

    def test_execute_handles_timeout(self) -> None:
        runtime = HostRuntime()
        request = RuntimeRequest(
            tool="sleep",
            command=("sleep", "10"),
            output_path=Path("/dev/null"),
            timeout_seconds=0.1,
        )

        with patch(
            "toolkit.runtime.host.run_process_command",
            return_value=ProcessResult(
                command=request.command,
                returncode=-1,
                stdout="",
                stderr="",
                timed_out=True,
            ),
        ):
            result = runtime.execute(request)

        self.assertTrue(result.timed_out)
        self.assertFalse(result.succeeded)


class RuntimeRequestFromToolExecutionTests(unittest.TestCase):
    def test_from_tool_execution_preserves_fields(self) -> None:
        execution = ToolExecution(
            tool="nmap",
            command=("nmap", "-F", "localhost"),
            cwd=Path("/tmp"),
            timeout_seconds=300.0,
            env_overrides={"FOO": "bar"},
        )
        output = Path("/tmp/results.xml")

        request = RuntimeRequest.from_tool_execution(execution, output_path=output)

        self.assertEqual(request.tool, "nmap")
        self.assertEqual(request.command, ("nmap", "-F", "localhost"))
        self.assertEqual(request.output_path, output)
        self.assertEqual(request.cwd, Path("/tmp"))
        self.assertEqual(request.timeout_seconds, 300.0)
        self.assertEqual(request.env_overrides, {"FOO": "bar"})
