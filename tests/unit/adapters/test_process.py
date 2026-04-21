import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from toolkit.adapters.base import ToolExecution
from toolkit.adapters.process import (
    check_binary_available,
    find_binary,
    run_tool_execution,
)
from toolkit.core.logging import ProcessLogContext, runtime_logging_scope


class ProcessRunnerTests(unittest.TestCase):
    def test_find_binary_resolves_existing_python3(self) -> None:
        resolved = find_binary("python3")

        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.is_absolute())

    def test_check_binary_available_reports_missing_binary(self) -> None:
        availability = check_binary_available("definitely-not-a-real-binary-name")

        self.assertFalse(availability.available)
        self.assertEqual(availability.binary, "definitely-not-a-real-binary-name")
        self.assertIn("not found", availability.reason)

    def test_run_tool_execution_captures_successful_stdout(self) -> None:
        execution = ToolExecution(
            tool="python",
            command=("python3", "-c", "print('hello from runner')"),
        )

        result = run_tool_execution(execution)

        self.assertTrue(result.succeeded)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello from runner")
        self.assertEqual(result.stderr, "")
        self.assertFalse(result.timed_out)

    def test_run_tool_execution_captures_non_zero_exit(self) -> None:
        execution = ToolExecution(
            tool="python",
            command=(
                "python3",
                "-c",
                "import sys; sys.stderr.write('boom\\n'); raise SystemExit(7)",
            ),
        )

        result = run_tool_execution(execution)

        self.assertFalse(result.succeeded)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, "")
        self.assertIn("boom", result.stderr)
        self.assertFalse(result.timed_out)

    def test_run_tool_execution_marks_timeout(self) -> None:
        execution = ToolExecution(
            tool="python",
            command=("python3", "-c", "import time; time.sleep(0.2)"),
            timeout_seconds=0.01,
        )

        result = run_tool_execution(execution)

        self.assertFalse(result.succeeded)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.returncode, -1)

    def test_run_tool_execution_streams_stdout_and_stderr(self) -> None:
        execution = ToolExecution(
            tool="python",
            command=(
                "python3",
                "-c",
                ("import sys; " "print('hello streamed'); " "sys.stderr.write('warn streamed\\n')"),
            ),
        )
        stdout_target = StringIO()
        stderr_target = StringIO()

        with runtime_logging_scope(verbosity=2, color=False):
            result = run_tool_execution(
                execution,
                stream_output=True,
                stdout_target=stdout_target,
                stderr_target=stderr_target,
            )

        self.assertTrue(result.succeeded)
        self.assertIn("hello streamed", result.stdout)
        self.assertIn("warn streamed", result.stderr)
        self.assertIn("event=tool.start", stdout_target.getvalue())
        self.assertIn("event=tool.output", stdout_target.getvalue())
        self.assertIn("tool=python", stdout_target.getvalue())
        self.assertIn("stream=stdout", stdout_target.getvalue())
        self.assertIn("hello streamed", stdout_target.getvalue())
        self.assertIn("event=tool.finish", stdout_target.getvalue())
        self.assertIn("stream=stderr", stderr_target.getvalue())
        self.assertIn("warn streamed", stderr_target.getvalue())

    def test_run_tool_execution_treats_zap_exit_with_artifact_as_completed_with_findings(
        self,
    ) -> None:
        with TemporaryDirectory() as tmp_dir_name:
            output_path = Path(tmp_dir_name) / "results.json"
            execution = ToolExecution(
                tool="python",
                command=(
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({str(output_path)!r}).write_text('{{}}', encoding='utf-8'); "
                        "raise SystemExit(2)"
                    ),
                ),
            )
            stdout_target = StringIO()
            stderr_target = StringIO()

            with runtime_logging_scope(verbosity=0, color=False):
                result = run_tool_execution(
                    execution,
                    stream_output=True,
                    stdout_target=stdout_target,
                    stderr_target=stderr_target,
                    log_context=ProcessLogContext(
                        runtime="container",
                        tool="zap",
                        output_path=output_path,
                    ),
                )

        self.assertFalse(result.succeeded)
        self.assertEqual(result.returncode, 2)
        self.assertIn("status=completed_with_findings", stdout_target.getvalue())
        self.assertIn("event=tool.finish", stdout_target.getvalue())
        self.assertNotIn("status=failed", stdout_target.getvalue())
