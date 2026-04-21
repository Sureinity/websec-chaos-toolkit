import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from toolkit.adapters.base import AdapterAvailability
from toolkit.audit.discovery import plan_discovered_audit_scope, run_katana_discovery
from toolkit.auth.session import AuthSession
from toolkit.runtime.models import RuntimeResult


class _RuntimeStub:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.request = None

    def check_tool_available(self, tool: str) -> AdapterAvailability:
        if self.available:
            return AdapterAvailability(available=True, binary=tool)
        return AdapterAvailability(available=False, reason="missing katana", binary=tool)

    def execute(self, request):  # type: ignore[no-untyped-def]
        self.request = request
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_text(
            "\n".join(
                (
                    '{"request": {"endpoint": "https://target.internal/admin"}}',
                    '{"request": {"endpoint": "https://target.internal/"}}',
                    '{"request": {"endpoint": "https://external.example/"}}',
                )
            )
            + "\n",
            encoding="utf-8",
        )
        return RuntimeResult(command=request.command, returncode=0, stdout="", stderr="")


class KatanaDiscoveryTests(unittest.TestCase):
    def test_run_katana_discovery_deduplicates_and_filters_to_same_origin(self) -> None:
        runtime = _RuntimeStub()

        with TemporaryDirectory() as tmp_dir_name:
            raw_dir = Path(tmp_dir_name) / "raw"
            result = run_katana_discovery(
                seed_url="https://target.internal/",
                raw_dir=raw_dir,
                runtime=runtime,
            )

            self.assertTrue(result.raw_output_path.is_file())
            self.assertTrue(result.route_manifest_path.is_file())

        self.assertEqual(
            result.routes,
            ("https://target.internal/", "https://target.internal/admin"),
        )

    def test_plan_discovered_audit_scope_filters_static_assets_for_zap(self) -> None:
        scope = plan_discovered_audit_scope(
            seed_url="https://target.internal/",
            discovered_routes=(
                "https://target.internal/",
                "https://target.internal/login",
                "https://target.internal/build/app.js",
                "https://target.internal/image/logo.png",
                "https://target.internal/report-problem",
            ),
        )

        self.assertEqual(
            scope.zap_routes,
            (
                "https://target.internal/",
                "https://target.internal/login",
                "https://target.internal/report-problem",
            ),
        )
        self.assertIn("https://target.internal/build/app.js", scope.nuclei_routes)
        self.assertIn("https://target.internal/image/logo.png", scope.nuclei_routes)

    def test_plan_discovered_audit_scope_caps_zap_routes_and_prefers_high_value_paths(self) -> None:
        scope = plan_discovered_audit_scope(
            seed_url="https://target.internal/",
            discovered_routes=(
                "https://target.internal/",
                "https://target.internal/login",
                "https://target.internal/register",
                "https://target.internal/contact",
                "https://target.internal/report-problem",
                "https://target.internal/projects",
                "https://target.internal/projects/one",
                "https://target.internal/projects/two",
                "https://target.internal/about",
                "https://target.internal/blog",
                "https://target.internal/blog/post-1",
            ),
            zap_route_limit=4,
        )

        self.assertEqual(
            scope.zap_routes,
            (
                "https://target.internal/",
                "https://target.internal/login",
                "https://target.internal/contact",
                "https://target.internal/register",
            ),
        )
        self.assertGreater(len(scope.nuclei_routes), len(scope.zap_routes))

    def test_run_katana_discovery_forwards_auth_headers_and_cookies(self) -> None:
        runtime = _RuntimeStub()
        auth_session = AuthSession(
            method="api_login",
            headers={"Authorization": "Bearer token"},
            cookies={"sessionid": "cookie-value"},
        )

        with TemporaryDirectory() as tmp_dir_name:
            raw_dir = Path(tmp_dir_name) / "raw"
            run_katana_discovery(
                seed_url="https://target.internal/",
                raw_dir=raw_dir,
                runtime=runtime,
                auth_session=auth_session,
            )

        self.assertIn("-H", runtime.request.command)
        self.assertIn("Authorization: Bearer token", runtime.request.command)
        self.assertIn("Cookie: sessionid=cookie-value", runtime.request.command)

    def test_run_katana_discovery_tolerates_malformed_json_lines(self) -> None:
        runtime = _RuntimeStub()

        with TemporaryDirectory() as tmp_dir_name:
            raw_dir = Path(tmp_dir_name) / "raw"
            output_dir = raw_dir / "katana"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "results.jsonl"
            output_path.write_text(
                "\n".join(
                    (
                        '{"request":{"endpoint":"https://target.internal/"}}',
                        (
                            '{"request":{"endpoint":"https://target.internal/admin"},'
                            '"response":{"body":"bad \\\\u12"}}'
                        ),
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            runtime.execute = lambda request: RuntimeResult(  # type: ignore[assignment]
                command=request.command,
                returncode=0,
                stdout="",
                stderr="",
            )

            result = run_katana_discovery(
                seed_url="https://target.internal/",
                raw_dir=raw_dir,
                runtime=runtime,
            )

        self.assertEqual(
            result.routes,
            ("https://target.internal/", "https://target.internal/admin"),
        )
