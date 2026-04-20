import unittest

from toolkit.config.models import AuthConfig
from toolkit.pentest.planner import CORE_PENTEST_TOOL_ORDER, build_pentest_plan
from toolkit.targets.adhoc import (
    URL_AUDIT_DEFAULT_ENVIRONMENT,
    URL_AUDIT_DEFAULT_HEALTH_ENDPOINT,
    URL_AUDIT_PROFILE_NAME,
    build_url_audit_app,
    build_url_audit_app_with_auth,
    build_url_audit_profile,
    build_url_edge_chaos_app,
    derive_url_audit_app_id,
)


class AdHocTargetBuilderTests(unittest.TestCase):
    def test_derive_url_audit_app_id_uses_host_and_port(self) -> None:
        self.assertEqual(
            derive_url_audit_app_id("http://LOCALHOST:8000/admin"),
            "adhoc-localhost-8000",
        )
        self.assertEqual(
            derive_url_audit_app_id("https://staging.internal.example"),
            "adhoc-staging-internal-example-443",
        )

    def test_build_url_audit_app_creates_valid_pentest_target(self) -> None:
        app = build_url_audit_app("http://127.0.0.1:8000")

        self.assertEqual(app.id, "adhoc-127-0-0-1-8000")
        self.assertEqual(app.environment, URL_AUDIT_DEFAULT_ENVIRONMENT)
        self.assertEqual(app.base_url.host, "127.0.0.1")
        self.assertEqual(app.base_url.port, 8000)
        self.assertEqual(app.host_targets, ["127.0.0.1"])
        self.assertEqual(app.target_allowlist, ["127.0.0.1"])
        self.assertEqual(app.auth.method, "none")
        self.assertEqual(app.health_endpoint, URL_AUDIT_DEFAULT_HEALTH_ENDPOINT)
        self.assertEqual(app.enabled_modules, ["pentest"])

    def test_build_url_audit_app_preserves_path_and_query(self) -> None:
        app = build_url_audit_app("https://example.internal/app?view=full")

        self.assertEqual(app.base_url.host, "example.internal")
        self.assertEqual(app.base_url.path, "/app")
        self.assertEqual(app.base_url.query, "view=full")
        self.assertEqual(app.id, "adhoc-example-internal-443")

    def test_build_url_edge_chaos_app_enables_chaos_only(self) -> None:
        app = build_url_edge_chaos_app("http://127.0.0.1:8000")

        self.assertEqual(app.id, "adhoc-127-0-0-1-8000")
        self.assertEqual(app.enabled_modules, ["chaos"])
        self.assertEqual(app.health_endpoint, URL_AUDIT_DEFAULT_HEALTH_ENDPOINT)
        self.assertEqual(app.base_url.host, "127.0.0.1")

    def test_build_url_audit_app_with_auth_overrides_auth_contract(self) -> None:
        app = build_url_audit_app_with_auth(
            "http://127.0.0.1:8000",
            auth=AuthConfig(
                method="cookie", cookie_name="sessionid", cookie_value_env_var="COOKIE"
            ),
        )

        self.assertEqual(app.auth.method, "cookie")
        self.assertEqual(app.auth.cookie_name, "sessionid")
        self.assertEqual(app.auth.cookie_value_env_var, "COOKIE")

    def test_build_url_audit_profile_matches_safe_remote_web_contract(self) -> None:
        profile = build_url_audit_profile()

        self.assertEqual(profile.name, URL_AUDIT_PROFILE_NAME)
        self.assertEqual(profile.assessment_mode, "remote_web")
        self.assertTrue(profile.tools.zap.enabled)
        self.assertEqual(profile.tools.zap.allowlisted_rules, ["headers", "tls"])
        self.assertTrue(profile.tools.nuclei.enabled)
        self.assertEqual(profile.tools.nuclei.allowlisted_rules, ["http/exposures"])
        self.assertTrue(profile.tools.nmap.enabled)
        self.assertEqual(profile.tools.nmap.allowlisted_rules, ["conservative-tcp"])
        self.assertIsNone(profile.tools.trivy)
        self.assertIsNone(profile.tools.semgrep)

    def test_built_profile_produces_enabled_core_plan(self) -> None:
        app = build_url_audit_app("http://target.example:8080")
        profile = build_url_audit_profile()

        plan = build_pentest_plan(
            app_id=app.id,
            environment=app.environment,
            profile=profile,
        )

        self.assertEqual(tuple(tool.tool for tool in plan.tools), CORE_PENTEST_TOOL_ORDER)
        self.assertTrue(all(tool.enabled for tool in plan.tools))


if __name__ == "__main__":
    unittest.main()
