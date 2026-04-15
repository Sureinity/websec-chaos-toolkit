import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from toolkit.cli import app
from toolkit.core.exits import ExitCode
from toolkit.pentest.contracts import PentestRunStatus, PentestRunSummary

RUNNER = CliRunner()


def _summary(tmp_dir: Path, *, exit_code: ExitCode) -> PentestRunSummary:
    status = (
        PentestRunStatus.SUCCESS if exit_code == ExitCode.SUCCESS else PentestRunStatus.FINDINGS
    )
    return PentestRunSummary(
        run_id="20260416-120000-fedcba98",
        status=status,
        exit_code=exit_code,
        findings_count=4,
        actionable_findings_count=2,
        adapter_results=(),
        normalized_bundle_path=tmp_dir / "outputs" / "run" / "normalized" / "findings.json",
        report_path=tmp_dir / "outputs" / "run" / "reports" / "executive-summary.md",
    )


class CodeAuditCommandTests(unittest.TestCase):
    def test_code_audit_runs_without_yaml_and_uses_built_in_profile(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            source_tree = project_root / "repo"
            source_tree.mkdir()
            (source_tree / "app.py").write_text("print('hi')\n", encoding="utf-8")

            with patch(
                "toolkit.commands.code_audit.run_pentest_live_flow",
                return_value=_summary(project_root, exit_code=ExitCode.FINDINGS_OR_FAILURE),
            ) as run_flow:
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["code-audit", str(source_tree)],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Code audit completed.", result.stdout)
        self.assertIn(f"Target path: {source_tree.resolve()}", result.stdout)
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(kwargs["project_root"], project_root)
        self.assertEqual(kwargs["app"].id.startswith("adhoc-source-tree-repo-"), True)
        self.assertEqual(kwargs["profile"].assessment_mode, "source_tree")
        self.assertTrue(kwargs["profile"].tools.semgrep.enabled)
        self.assertTrue(kwargs["profile"].tools.trivy.enabled)
        self.assertIsNone(kwargs["profile"].tools.zap)
        self.assertEqual(
            kwargs["target_paths"],
            {"semgrep": source_tree.resolve(), "trivy": source_tree.resolve()},
        )

    def test_code_audit_can_narrow_to_semgrep_only(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            source_tree = project_root / "repo"
            source_tree.mkdir()

            with patch(
                "toolkit.commands.code_audit.run_pentest_live_flow",
                return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
            ) as run_flow:
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["code-audit", str(source_tree), "--tool", "semgrep"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(kwargs["profile"].name, "adhoc-safe-code-audit-semgrep")
        self.assertTrue(kwargs["profile"].tools.semgrep.enabled)
        self.assertFalse(kwargs["profile"].tools.trivy.enabled)
        self.assertEqual(kwargs["target_paths"], {"semgrep": source_tree.resolve()})

    def test_code_audit_can_narrow_to_trivy_only(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            source_tree = project_root / "repo"
            source_tree.mkdir()

            with patch(
                "toolkit.commands.code_audit.run_pentest_live_flow",
                return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
            ) as run_flow:
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["code-audit", str(source_tree), "--tool", "trivy"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(kwargs["profile"].name, "adhoc-safe-code-audit-trivy")
        self.assertFalse(kwargs["profile"].tools.semgrep.enabled)
        self.assertTrue(kwargs["profile"].tools.trivy.enabled)
        self.assertEqual(kwargs["target_paths"], {"trivy": source_tree.resolve()})

    def test_code_audit_rejects_invalid_tool(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            source_tree = project_root / "repo"
            source_tree.mkdir()

            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["code-audit", str(source_tree), "--tool", "zap"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Code audit failed.", result.stderr)
        self.assertIn("Unsupported code-audit tool", result.stderr)

    def test_code_audit_rejects_missing_path(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["code-audit", "./missing-repo"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Code audit failed.", result.stderr)
        self.assertIn("does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
