import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from toolkit.adapters.base import build_failed_result
from toolkit.audit.auth import AuditAuthMode
from toolkit.audit.discovery import KatanaDiscoveryResult
from toolkit.audit.fingerprint import AuditFingerprintError, HttpxFingerprint
from toolkit.auth.session import AuthSession
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


def _fingerprint() -> HttpxFingerprint:
    return HttpxFingerprint(
        requested_url="http://127.0.0.1:8000/",
        final_url="http://127.0.0.1:8000/",
        reachable=True,
        status_code=200,
        redirect_chain=(),
        title="Test App",
        server="uvicorn",
        technology_hints=("server: uvicorn",),
        tls=None,
    )


def _discovery(tmp_dir: Path) -> KatanaDiscoveryResult:
    raw_output_path = tmp_dir / "outputs" / "run" / "raw" / "katana" / "results.jsonl"
    route_manifest_path = tmp_dir / "outputs" / "run" / "raw" / "katana" / "discovered-routes.txt"
    return KatanaDiscoveryResult(
        raw_output_path=raw_output_path,
        route_manifest_path=route_manifest_path,
        routes=("http://127.0.0.1:8000/", "http://127.0.0.1:8000/admin"),
    )


def _discovery_with_assets(tmp_dir: Path) -> KatanaDiscoveryResult:
    raw_output_path = tmp_dir / "outputs" / "run" / "raw" / "katana" / "results.jsonl"
    route_manifest_path = tmp_dir / "outputs" / "run" / "raw" / "katana" / "discovered-routes.txt"
    return KatanaDiscoveryResult(
        raw_output_path=raw_output_path,
        route_manifest_path=route_manifest_path,
        routes=(
            "http://127.0.0.1:8000/",
            "http://127.0.0.1:8000/login",
            "http://127.0.0.1:8000/build/app.js",
            "http://127.0.0.1:8000/assets/logo.png",
            "http://127.0.0.1:8000/report-problem",
        ),
    )


def _discovery_with_many_routes(tmp_dir: Path) -> KatanaDiscoveryResult:
    raw_output_path = tmp_dir / "outputs" / "run" / "raw" / "katana" / "results.jsonl"
    route_manifest_path = tmp_dir / "outputs" / "run" / "raw" / "katana" / "discovered-routes.txt"
    return KatanaDiscoveryResult(
        raw_output_path=raw_output_path,
        route_manifest_path=route_manifest_path,
        routes=(
            "http://127.0.0.1:8000/",
            "http://127.0.0.1:8000/login",
            "http://127.0.0.1:8000/register",
            "http://127.0.0.1:8000/contact",
            "http://127.0.0.1:8000/report-problem",
            "http://127.0.0.1:8000/forgot-password",
            "http://127.0.0.1:8000/account",
            "http://127.0.0.1:8000/profile",
            "http://127.0.0.1:8000/dashboard",
            "http://127.0.0.1:8000/projects",
            "http://127.0.0.1:8000/projects/one",
            "http://127.0.0.1:8000/projects/two",
            "http://127.0.0.1:8000/about",
            "http://127.0.0.1:8000/blog",
            "http://127.0.0.1:8000/blog/post-1",
            "http://127.0.0.1:8000/admin",
            "http://127.0.0.1:8000/api",
            "http://127.0.0.1:8000/checkout",
            "http://127.0.0.1:8000/payment",
            "http://127.0.0.1:8000/apply",
            "http://127.0.0.1:8000/cart",
            "http://127.0.0.1:8000/help",
            "http://127.0.0.1:8000/docs",
            "http://127.0.0.1:8000/faq",
            "http://127.0.0.1:8000/pricing",
            "http://127.0.0.1:8000/team",
            "http://127.0.0.1:8000/company",
            "http://127.0.0.1:8000/legal",
            "http://127.0.0.1:8000/support",
            "http://127.0.0.1:8000/status",
            "http://127.0.0.1:8000/roadmap",
            "http://127.0.0.1:8000/settings",
            "http://127.0.0.1:8000/preferences",
        ),
    )


def _auth_session(method: str = "none") -> AuthSession:
    if method == "api_login":
        return AuthSession(
            method="api_login",
            headers={"Authorization": "Bearer token"},
            provenance={
                "source": "api_login",
                "login_url": "http://127.0.0.1:8000/api/login",
                "auth_result": "bearer_json",
            },
        )
    return AuthSession(method="none", provenance={"source": "none"})


class AuditCommandTests(unittest.TestCase):
    def test_audit_help_groups_auth_options_by_mode(self) -> None:
        result = RUNNER.invoke(
            app,
            ["audit", "--help"],
            catch_exceptions=False,
        )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("General Audit Options", result.stdout)
        self.assertIn("Auth Mode Selection", result.stdout)
        self.assertIn("Auth Mode: bearer_token", result.stdout)
        self.assertIn("Auth Mode: cookie", result.stdout)
        self.assertIn("Auth Mode: session", result.stdout)
        self.assertIn("Auth Modes: form and api_login", result.stdout)
        self.assertIn("Auth Mode: api_login", result.stdout)
        self.assertIn("--intensity", result.stdout)
        self.assertIn("--token-env-var", result.stdout)
        self.assertIn("--cookie-name", result.stdout)
        self.assertIn("--session-header", result.stdout)
        self.assertIn("--login-url", result.stdout)
        self.assertIn("--auth-result", result.stdout)

    def test_audit_succeeds_without_yaml_using_auto_selected_runtime(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ) as select_runtime,
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.FINDINGS_OR_FAILURE),
                ) as run_flow,
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Audit completed.", result.stdout)
        self.assertIn("Intensity: safe", result.stdout)
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
        self.assertIn("context", kwargs)
        self.assertEqual(len(kwargs["extra_raw_artifact_paths"]), 5)
        self.assertEqual(kwargs["extra_raw_artifact_paths"][0].name, "fingerprint.json")
        self.assertEqual(kwargs["target_urls"]["zap"][1], "http://127.0.0.1:8000/admin")
        self.assertEqual(kwargs["target_urls"]["nuclei"][1], "http://127.0.0.1:8000/admin")

    def test_audit_accepts_explicit_safe_intensity(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000", "--intensity", "safe"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Intensity: safe", result.stdout)

    def test_audit_accepts_explicit_balanced_intensity(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000", "--intensity", "balanced"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Intensity: balanced", result.stdout)

    def test_audit_accepts_explicit_deep_intensity(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000", "--intensity", "deep"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Intensity: deep", result.stdout)

    def test_audit_omitted_intensity_matches_safe_scope(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery_with_many_routes(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ) as run_flow,
            ):
                with chdir(project_root):
                    RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000"],
                        catch_exceptions=False,
                    )
                    omitted_kwargs = run_flow.call_args.kwargs
                    RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000", "--intensity", "safe"],
                        catch_exceptions=False,
                    )
                    safe_kwargs = run_flow.call_args.kwargs

        self.assertEqual(
            omitted_kwargs["target_urls"]["zap"],
            safe_kwargs["target_urls"]["zap"],
        )
        self.assertEqual(
            omitted_kwargs["target_urls"]["nuclei"],
            safe_kwargs["target_urls"]["nuclei"],
        )
        self.assertEqual(
            omitted_kwargs["profile"].tools.nuclei.allowlisted_rules,
            safe_kwargs["profile"].tools.nuclei.allowlisted_rules,
        )

    def test_audit_balanced_intensity_expands_scope_and_budgets(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery_with_many_routes(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ) as run_flow,
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000", "--intensity", "balanced"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(len(kwargs["target_urls"]["zap"]), 12)
        self.assertEqual(len(kwargs["target_urls"]["nuclei"]), 16)
        self.assertEqual(kwargs["profile"].tools.zap.profile, "balanced")
        self.assertEqual(kwargs["profile"].tools.nuclei.profile, "balanced")
        self.assertEqual(kwargs["profile"].tools.nuclei.allowlisted_rules, ["http/exposures"])
        self.assertEqual(kwargs["profile"].tools.nmap.profile, "top-ports")

    def test_audit_deep_intensity_expands_scope_and_allowlist(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery_with_many_routes(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ) as run_flow,
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000", "--intensity", "deep"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(len(kwargs["target_urls"]["zap"]), 20)
        self.assertEqual(len(kwargs["target_urls"]["nuclei"]), 32)
        self.assertEqual(kwargs["profile"].tools.zap.profile, "deep")
        self.assertEqual(kwargs["profile"].tools.nuclei.profile, "deep")
        self.assertEqual(
            kwargs["profile"].tools.nuclei.allowlisted_rules,
            ["http/exposures", "http/misconfiguration", "http/technologies"],
        )
        self.assertEqual(kwargs["profile"].tools.nmap.profile, "top-ports")

    def test_audit_rejects_invalid_intensity_value(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    ["audit", "http://127.0.0.1:8000", "--intensity", "extreme"],
                )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Invalid value", result.output)

    def test_audit_curates_zap_and_nuclei_scope(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery_with_assets(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ) as run_flow,
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        kwargs = run_flow.call_args.kwargs
        self.assertEqual(
            kwargs["target_urls"]["zap"],
            (
                "http://127.0.0.1:8000/",
                "http://127.0.0.1:8000/login",
                "http://127.0.0.1:8000/report-problem",
            ),
        )
        self.assertEqual(
            kwargs["target_urls"]["nuclei"],
            (
                "http://127.0.0.1:8000/",
                "http://127.0.0.1:8000/login",
                "http://127.0.0.1:8000/report-problem",
            ),
        )

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
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.HOST),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session("api_login"),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ) as run_flow,
            ):
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
        self.assertIn("Auth mode: api_login", result.stdout)
        self.assertIn("Auth source: api_login", result.stdout)
        self.assertIn("Fingerprint final URL: http://127.0.0.1:8000/", result.stdout)
        self.assertIn("Discovery routes: 2", result.stdout)

    def test_audit_requires_form_field_names(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with chdir(project_root):
                result = RUNNER.invoke(
                    app,
                    [
                        "audit",
                        "http://127.0.0.1:8000",
                        "--auth-mode",
                        "form",
                        "--login-url",
                        "http://127.0.0.1:8000/login",
                        "--username-env-var",
                        "TOOLKIT_AUDIT_USERNAME",
                        "--password-env-var",
                        "TOOLKIT_AUDIT_PASSWORD",
                    ],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("login_password_field", result.stderr)
        self.assertIn("login_username_field", result.stderr)

    def test_audit_honors_explicit_runtime_selection(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.HOST),
                ) as select_runtime,
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ),
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

    def test_audit_accepts_verbose_flags(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.HOST),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=_summary(project_root, exit_code=ExitCode.SUCCESS),
                ),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "-vv", "https://example.internal"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)

    def test_audit_reports_failed_summary_and_tool_details(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            failed_summary = PentestRunSummary(
                run_id="20260420-074911-3af8685e",
                status=PentestRunStatus.FAILED,
                exit_code=ExitCode.CONFIG_OR_RUNTIME_ERROR,
                findings_count=3,
                actionable_findings_count=2,
                adapter_results=(
                    build_failed_result(
                        "zap",
                        error_detail="zap exited with code 3",
                    ),
                ),
                normalized_bundle_path=(
                    project_root / "outputs" / "run" / "normalized" / "findings.json"
                ),
                report_path=(project_root / "outputs" / "run" / "reports" / "executive-summary.md"),
            )
            with (
                patch(
                    "toolkit.commands.audit.select_audit_runtime",
                    return_value=_selection(RuntimeMode.CONTAINER),
                ),
                patch(
                    "toolkit.commands.audit.capture_httpx_fingerprint",
                    return_value=_fingerprint(),
                ),
                patch(
                    "toolkit.commands.audit.resolve_auth_session",
                    return_value=_auth_session(),
                ),
                patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ),
                patch(
                    "toolkit.commands.audit.run_pentest_live_flow",
                    return_value=failed_summary,
                ),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "https://infosoft.poolreno.com/"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertNotIn("Audit completed.", result.stdout)
        self.assertIn("Status: failed", result.stdout)
        self.assertIn("Audit failed.", result.stderr)
        self.assertIn("Tool failure: zap: zap exited with code 3", result.stderr)

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

    def test_audit_reports_httpx_preflight_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.audit.capture_httpx_fingerprint",
                side_effect=AuditFingerprintError("httpx preflight failed"),
            ):
                with chdir(project_root):
                    result = RUNNER.invoke(
                        app,
                        ["audit", "http://127.0.0.1:8000"],
                        catch_exceptions=False,
                    )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Audit failed.", result.stderr)
        self.assertIn("httpx preflight failed", result.stderr)

    def test_audit_reports_runtime_selection_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with patch(
                "toolkit.commands.audit.capture_httpx_fingerprint",
                return_value=_fingerprint(),
            ):
                with patch(
                    "toolkit.commands.audit.run_katana_discovery",
                    return_value=_discovery(project_root),
                ):
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
