import unittest
from io import StringIO
from pathlib import Path

from toolkit.core.logging import emit_runtime_log, runtime_logging_scope


class _TtyStringIO(StringIO):
    def isatty(self) -> bool:
        return True


class RuntimeLoggingTests(unittest.TestCase):
    def test_logging_is_disabled_outside_scope(self) -> None:
        target = StringIO()

        emit_runtime_log(
            target,
            level="INFO",
            event="tool.start",
            runtime="host",
            tool="zap",
        )

        self.assertEqual(target.getvalue(), "")

    def test_default_scope_hides_stdout_tool_output(self) -> None:
        target = StringIO()

        with runtime_logging_scope(verbosity=0, color=False):
            emit_runtime_log(
                target,
                level="INFO",
                event="tool.start",
                runtime="host",
                tool="zap",
                output=Path("/tmp/results.json"),
                cwd=Path("/tmp"),
                command="zap-baseline.py -J results.json",
            )
            emit_runtime_log(
                target,
                level="INFO",
                event="tool.output",
                runtime="host",
                tool="zap",
                stream="stdout",
                message="passive scan started",
            )

        rendered = target.getvalue()
        self.assertIn("event=tool.start", rendered)
        self.assertNotIn("event=tool.output", rendered)
        self.assertNotIn("output=/tmp/results.json", rendered)
        self.assertNotIn("cwd=/tmp", rendered)
        self.assertNotIn("command=", rendered)

    def test_single_verbose_level_shows_stderr_output(self) -> None:
        target = StringIO()

        with runtime_logging_scope(verbosity=1, color=False):
            emit_runtime_log(
                target,
                level="WARN",
                event="tool.output",
                runtime="host",
                tool="zap",
                stream="stderr",
                message="scan warning",
            )

        rendered = target.getvalue()
        self.assertIn("event=tool.output", rendered)
        self.assertIn("stream=stderr", rendered)
        self.assertIn('message="scan warning"', rendered)

    def test_triple_verbose_level_shows_command_field(self) -> None:
        target = StringIO()

        with runtime_logging_scope(verbosity=3, color=False):
            emit_runtime_log(
                target,
                level="INFO",
                event="tool.start",
                runtime="container",
                tool="nuclei",
                output=Path("/tmp/results.jsonl"),
                cwd=Path("/workspace"),
                command="docker run nuclei",
            )

        rendered = target.getvalue()
        self.assertIn("output=/tmp/results.jsonl", rendered)
        self.assertIn("cwd=/workspace", rendered)
        self.assertIn('command="docker run nuclei"', rendered)

    def test_colorizes_timestamp_and_level_when_enabled(self) -> None:
        target = _TtyStringIO()

        with runtime_logging_scope(verbosity=0, color=True):
            emit_runtime_log(
                target,
                level="INFO",
                event="tool.start",
                runtime="host",
                tool="zap",
            )

        rendered = target.getvalue()
        self.assertIn("\x1b[36m", rendered)
        self.assertIn("\x1b[32mINFO\x1b[0m", rendered)


if __name__ == "__main__":
    unittest.main()
