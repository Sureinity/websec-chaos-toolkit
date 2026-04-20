import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from toolkit.core.run_context import RunRequest, prepare_run_context
from toolkit.reports.builder import (
    build_markdown_summary,
    build_markdown_summary_from_run_dir,
    executive_summary_path,
    write_markdown_summary,
)
from toolkit.results.io import (
    read_normalized_results,
    read_normalized_results_from_path,
    write_normalized_results,
)
from toolkit.results.models import NormalizedResult, ResultTimestamps


def build_result(
    *,
    app_id: str = "sample-app",
    environment: str = "local",
    target: str = "http://localhost:8000",
    tool: str = "zap",
    category: str = "headers",
    severity: str = "low",
    confidence: str = "high",
    remediation_summary: str = "Set the missing security header.",
) -> NormalizedResult:
    return NormalizedResult(
        app_id=app_id,
        environment=environment,
        target=target,
        tool=tool,
        category=category,
        severity=severity,
        confidence=confidence,
        evidence=["missing x-frame-options"],
        remediation_summary=remediation_summary,
        timestamps=ResultTimestamps(
            started_at=datetime(2026, 3, 28, 2, 3, 4, tzinfo=UTC),
            finished_at=datetime(2026, 3, 28, 2, 5, 6, tzinfo=UTC),
        ),
    )


class NormalizedResultsIoTests(unittest.TestCase):
    def test_write_and_read_normalized_results_round_trip(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [
            build_result(),
            build_result(
                tool="nuclei",
                category="exposure",
                severity="medium",
                confidence="medium",
                remediation_summary="Restrict the exposed endpoint.",
            ),
        ]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            bundle_path = write_normalized_results(context, results)
            loaded_results = read_normalized_results(context)

        self.assertEqual(bundle_path.name, "findings.json")
        self.assertEqual(len(loaded_results), 2)
        self.assertEqual(loaded_results[0].tool, "zap")
        self.assertEqual(loaded_results[1].tool, "nuclei")
        self.assertEqual(loaded_results[1].severity, "medium")

    def test_write_normalized_results_uses_deterministic_json_format(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [build_result()]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            bundle_path = write_normalized_results(context, results)
            content = bundle_path.read_text(encoding="utf-8")

        self.assertTrue(content.endswith("\n"))
        self.assertIn('"app_id": "sample-app"', content)
        self.assertIn('"started_at": "2026-03-28T02:03:04Z"', content)
        self.assertIn('"tool": "zap"', content)

    def test_read_normalized_results_from_path_supports_explicit_bundle_path(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [build_result()]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            bundle_path = write_normalized_results(context, results)
            loaded_results = read_normalized_results_from_path(bundle_path)

        self.assertEqual(len(loaded_results), 1)
        self.assertEqual(loaded_results[0].remediation_summary, "Set the missing security header.")


class ReportBuilderTests(unittest.TestCase):
    def test_build_markdown_summary_groups_by_app_and_severity(self) -> None:
        results = [
            build_result(severity="medium", tool="nuclei", category="exposure"),
            build_result(severity="high", tool="zap", category="headers"),
            build_result(
                app_id="sample-api",
                target="https://staging.internal.example",
                severity="low",
                tool="nmap",
                category="ports",
                remediation_summary="Close the exposed port.",
            ),
        ]

        summary = build_markdown_summary("20260328-020304-deadbeef", results)

        self.assertIn("# Run Summary: 20260328-020304-deadbeef", summary)
        self.assertIn("## sample-api", summary)
        self.assertIn("## sample-app", summary)
        self.assertIn("### high (1)", summary)
        self.assertIn("### medium (1)", summary)
        self.assertIn("### low (1)", summary)
        self.assertIn("- Tool: zap", summary)
        self.assertIn("- Tool: nuclei", summary)
        self.assertIn("- Tool: nmap", summary)

    def test_build_markdown_summary_handles_empty_runs(self) -> None:
        summary = build_markdown_summary("20260328-020304-deadbeef", [])

        self.assertIn("Total findings: 0", summary)
        self.assertIn("No findings were normalized for this run.", summary)

    def test_write_markdown_summary_rebuilds_from_stored_bundle(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )
        results = [
            build_result(severity="high", tool="zap", category="headers"),
            build_result(tool="nuclei", category="exposure", severity="medium"),
        ]

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )
            write_normalized_results(context, results)

            rebuilt_summary = build_markdown_summary_from_run_dir(context.run_dir)
            summary_path = write_markdown_summary(context.run_dir)
            written_summary = summary_path.read_text(encoding="utf-8")

        self.assertEqual(summary_path, executive_summary_path(context.run_dir))
        self.assertTrue(written_summary.endswith("\n"))
        self.assertEqual(written_summary.rstrip("\n"), rebuilt_summary)
        self.assertIn("## sample-app", rebuilt_summary)
        self.assertIn("### high (1)", rebuilt_summary)
        self.assertIn("### medium (1)", rebuilt_summary)

    def test_report_builder_includes_target_fingerprint_section_when_present(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )
            (context.raw_dir / "httpx").mkdir(parents=True, exist_ok=True)
            (context.raw_dir / "httpx" / "fingerprint.json").write_text(
                json.dumps(
                    {
                        "requested_url": "https://target.internal/",
                        "final_url": "https://target.internal/dashboard",
                        "reachable": True,
                        "status_code": 200,
                        "redirect_chain": [{"url": "https://target.internal/", "status_code": 302}],
                        "title": "Dashboard",
                        "server": "nginx",
                        "technology_hints": ["server: nginx"],
                        "tls": {
                            "enabled": True,
                            "http_version": "HTTP/1.1",
                            "strict_transport_security": "max-age=31536000",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            (context.raw_dir / "katana").mkdir(parents=True, exist_ok=True)
            (context.raw_dir / "katana" / "discovered-routes.txt").write_text(
                "https://target.internal/\nhttps://target.internal/dashboard\n",
                encoding="utf-8",
            )
            (context.raw_dir / "audit").mkdir(parents=True, exist_ok=True)
            (context.raw_dir / "audit" / "auth-context.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "api_login",
                        "is_authenticated": True,
                        "provenance": {
                            "source": "api_login",
                            "login_url": "https://target.internal/api/login",
                            "auth_result": "bearer_json",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            write_normalized_results(context, [])

            summary = build_markdown_summary_from_run_dir(context.run_dir)

        self.assertIn("## Target Fingerprint", summary)
        self.assertIn("Requested URL: https://target.internal/", summary)
        self.assertIn("Technology hints: server: nginx", summary)
        self.assertIn("## Discovery Coverage", summary)
        self.assertIn("Routes in scope: 2", summary)
        self.assertIn("## Auth Context", summary)
        self.assertIn("Auth mode: api_login", summary)
