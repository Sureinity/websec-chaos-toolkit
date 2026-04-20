import unittest

from toolkit.audit.auth import (
    ApiLoginAuthResult,
    ApiLoginContentType,
    AuditAuthMode,
    AuditAuthValidationError,
    build_url_audit_auth_config,
)


class UrlAuditAuthConfigTests(unittest.TestCase):
    def test_no_auth_mode_defaults_to_unauthenticated(self) -> None:
        auth = build_url_audit_auth_config()

        self.assertEqual(auth.method, "none")

    def test_flags_without_auth_mode_fail_closed(self) -> None:
        with self.assertRaises(AuditAuthValidationError) as context:
            build_url_audit_auth_config(token_env_var="TOKEN")

        self.assertIn("--auth-mode", str(context.exception))

    def test_bearer_token_requires_token_env_var(self) -> None:
        with self.assertRaises(AuditAuthValidationError) as context:
            build_url_audit_auth_config(auth_mode=AuditAuthMode.BEARER_TOKEN)

        self.assertIn("token_env_var", str(context.exception))

    def test_api_login_requires_mode_specific_fields(self) -> None:
        with self.assertRaises(AuditAuthValidationError) as context:
            build_url_audit_auth_config(
                auth_mode=AuditAuthMode.API_LOGIN,
                login_url="https://example.internal/api/login",
                username_env_var="USER",
                password_env_var="PASS",
                login_content_type=ApiLoginContentType.JSON,
                login_username_field="username",
                login_password_field="password",
                auth_result=ApiLoginAuthResult.BEARER_JSON,
            )

        self.assertIn("auth_result_path", str(context.exception))

    def test_session_json_requires_session_header(self) -> None:
        with self.assertRaises(AuditAuthValidationError) as context:
            build_url_audit_auth_config(
                auth_mode=AuditAuthMode.API_LOGIN,
                login_url="https://example.internal/api/login",
                username_env_var="USER",
                password_env_var="PASS",
                login_content_type=ApiLoginContentType.JSON,
                login_username_field="username",
                login_password_field="password",
                auth_result=ApiLoginAuthResult.SESSION_JSON,
                auth_result_path="session.id",
            )

        self.assertIn("session_header", str(context.exception))

    def test_cookie_mode_rejects_mixed_flags(self) -> None:
        with self.assertRaises(AuditAuthValidationError) as context:
            build_url_audit_auth_config(
                auth_mode=AuditAuthMode.COOKIE,
                cookie_name="sessionid",
                cookie_value_env_var="COOKIE",
                token_env_var="TOKEN",
            )

        self.assertIn("does not allow", str(context.exception))

    def test_api_login_builds_auth_config_for_cookie_result(self) -> None:
        auth = build_url_audit_auth_config(
            auth_mode=AuditAuthMode.API_LOGIN,
            login_url="https://example.internal/api/login",
            username_env_var="USER",
            password_env_var="PASS",
            login_content_type=ApiLoginContentType.JSON,
            login_username_field="email",
            login_password_field="password",
            auth_result=ApiLoginAuthResult.COOKIE,
        )

        self.assertEqual(auth.method, "api_login")
        self.assertEqual(auth.login_username_field, "email")
        self.assertEqual(auth.auth_result, "cookie")
