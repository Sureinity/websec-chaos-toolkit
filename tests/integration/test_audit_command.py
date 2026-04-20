import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from toolkit.audit.auth import AuditAuthMode
from toolkit.cli import app
from toolkit.core.exits import ExitCode
from toolkit.pentest.contracts import PentestRunStatus, PentestRunSummary
from toolkit.runtime.contracts import RuntimeMode
from toolkit.runtime.host import HostRuntime
from toolkit.runtime.selector import (
    AuditRuntimeReadiness,
    AuditRuntimeSelection,
    RuntimeSelectionError,
)

RUNNER = CliRunner()


def _selection(mode: RuntimeMode) -> AuditRuntimeSelection:
    return AuditRuntimeSelection(
        mode=mode,
        backend=HostRuntime(),
        readiness=AuditRuntimeReadiness(mode=mode, tool_statuses=()),
    )


def _summary(tmp_dir: Path, *, exit_code: ExitCode) -> PentestRunSummary:
    status = (
        PentestRunStatus.SUCCESS if exit_code == ExitCode.SUCCESS else PentestRunStatus.FINDINGS
    )
    return PentestRunSummary(
        run_id="20260414-010101-abcdef12",
        status=status,
        exit_code=exit_code,
        findings_count=3,
        actionable_findings_count=1,
        adapter_results=(),
        normalized_bundle_path=tmp_dir / "outputs" / "run" / "normalized" / "findings.json",
        report_path=tmp_dir / "outputs" / "run" / "reports" / "executive-summary.md",
    )


class AuditCommandTests(unittest.TestCase):
    def test_audit_succeeds_without_yaml_using_auto_selected_runtime(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.audit.select_audit_runtime",
                return_value=_selection(RuntimeMode.CONTAINER),
            ) as select_runtime:
                with patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.FINDINGS_OR_FAILURE),
                ) as run_flow:
                    with chdir(project_root):
                        result = RUNNER.invoke(
                            app,
                            ["audit", "http://127.0.0.1:8000"],
                            catch_exceptions=False,
                        )

        self.assertEqual(result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Audit completed.", result.stdout)
        self.assertIn("Target: http://127.0.0.1:8000/", result.stdout)
        self.assertIn("Runtime: container", result.stdout)
        self.assertIn("Status: findings", result.stdout)
        select_runtime.assert_called_once_with(preferred_mode=None)

        kwargs = run_flow.call_args.kwargs
        self.assertEqual(kwargs["project_root"], project_root)
        self.assertEqual(kwargs["app"].id, "adhoc-127-0-0-1-8000")
        self.assertEqual(kwargs["app"].environment, "local")
        self.assertEqual(kwargs["app"].auth.method, "none")
        self.assertEqual(kwargs["profile"].name, "adhoc-safe-web-baseline")
        self.assertEqual(kwargs["profile"].assessment_mode, "remote_web")

    def test_audit_rejects_missing_required_auth_flags(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["audit", "http://127.0.0.1:8000", "--auth-mode", "bearer_token"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("requires", result.stderr)

    def test_audit_rejects_mixed_auth_mode_flags(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    [
                        "audit",
                        "http://127.0.0.1:8000",
                        "--auth-mode",
                        "bearer_token",
                        "--token-env-var",
                        "TOKEN",
                        "--cookie-name",
                        "sessionid",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("does not allow", result.stderr)

    def test_audit_rejects_auth_flags_without_auth_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    [
                        "audit",
                        "http://127.0.0.1:8000",
                        "--token-env-var",
                        "TOKEN",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("--auth-mode", result.stderr)

    def test_audit_passes_api_login_auth_config_without_downgrading(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.audit.select_audit_runtime",
                return_value=_selection(RuntimeMode.HOST),
            ):
                with patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ) as run_flow:
                    with chdir(project_root):
                        result = RUNNER.invoke(
                            app,
                            [
                                "audit",
                                "http://127.0.0.1:8000",
                                "--auth-mode",
                                "api_login",
                                "--login-url",
                                "http://127.0.0.1:8000/api/login",
                                "--username-env-var",
                                "TOOLKIT_AUDIT_USERNAME",
                                "--password-env-var",
                                "TOOLKIT_AUDIT_PASSWORD",
                                "--login-content-type",
                                "json",
                                "--login-username-field",
                                "username",
                                "--login-password-field",
                                "password",
                                "--auth-result",
                                "bearer_json",
                                "--auth-result-path",
                                "token",
                            ],
                            catch_exceptions=False,
                        )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(kwargs["app"].auth.method, AuditAuthMode.API_LOGIN.value)
        self.assertEqual(kwargs["app"].auth.login_url.host, "127.0.0.1")
        self.assertEqual(kwargs["app"].auth.login_content_type, "json")
        self.assertEqual(kwargs["app"].auth.auth_result, "bearer_json")

    def test_audit_honors_explicit_runtime_selection(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.audit.select_audit_runtime",
                return_value=_selection(RuntimeMode.HOST),
            ) as select_runtime:
                with patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ):
                    with chdir(project_root):
                        result = RUNNER.invoke(
                            app,
                            ["audit", "https://example.internal", "--runtime", "host"],
                            catch_exceptions=False,
                        )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Runtime: host", result.stdout)
        select_runtime.assert_called_once_with(preferred_mode=RuntimeMode.HOST)

    def test_audit_rejects_invalid_url(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["audit", "not-a-url"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Audit failed.", result.stderr)

    def test_audit_reports_runtime_selection_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.audit.select_audit_runtime",
                side_effect=RuntimeSelectionError("No audit runtime is ready."),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Audit failed.", result.stderr)
        self.assertIn("No audit runtime is ready.", result.stderr)


if __name__ == "__main__":
    unittest.main()
