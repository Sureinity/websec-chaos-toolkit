import unittest

from toolkit.auth.errors import (
    BlankSecretValueError,
    MissingEnvironmentVariableError,
    UnsupportedAuthFlowError,
)
from toolkit.auth.resolver import (
    resolve_bearer_auth,
    resolve_cookie_auth,
    resolve_session_auth,
    resolve_supported_env_auth,
)
from toolkit.config.models import AuthConfig


class AuthResolverTests(unittest.TestCase):
    def test_resolve_bearer_auth_returns_authorization_header(self) -> None:
        auth_config = AuthConfig(
            method="bearer_token",
            token_env_var="SECURITY_TEST_BEARER_TOKEN",
        )

        resolved = resolve_bearer_auth(
            auth_config,
            environ={"SECURITY_TEST_BEARER_TOKEN": "secret-token"},
        )

        self.assertEqual(resolved.method, "bearer_token")
        self.assertEqual(
            resolved.headers,
            {"Authorization": "Bearer secret-token"},
        )
        self.assertEqual(resolved.cookies, {})
        self.assertTrue(resolved.is_authenticated)
        self.assertEqual(
            resolved.provenance,
            {"source": "env", "token_env_var": "SECURITY_TEST_BEARER_TOKEN"},
        )

    def test_resolve_cookie_auth_returns_cookie_mapping(self) -> None:
        auth_config = AuthConfig(
            method="cookie",
            cookie_name="sessionid",
            cookie_value_env_var="SECURITY_TEST_COOKIE",
        )

        resolved = resolve_cookie_auth(
            auth_config,
            environ={"SECURITY_TEST_COOKIE": "cookie-value"},
        )

        self.assertEqual(resolved.method, "cookie")
        self.assertEqual(resolved.headers, {})
        self.assertEqual(resolved.cookies, {"sessionid": "cookie-value"})
        self.assertTrue(resolved.is_authenticated)
        self.assertEqual(
            resolved.provenance,
            {
                "source": "env",
                "cookie_name": "sessionid",
                "cookie_value_env_var": "SECURITY_TEST_COOKIE",
            },
        )

    def test_resolve_session_auth_returns_header_mapping(self) -> None:
        auth_config = AuthConfig(
            method="session",
            session_header="X-Session-ID",
            session_value_env_var="SECURITY_TEST_SESSION",
        )

        resolved = resolve_session_auth(
            auth_config,
            environ={"SECURITY_TEST_SESSION": "session-value"},
        )

        self.assertEqual(resolved.method, "session")
        self.assertEqual(resolved.cookies, {})
        self.assertEqual(resolved.headers, {"X-Session-ID": "session-value"})
        self.assertTrue(resolved.is_authenticated)
        self.assertEqual(
            resolved.provenance,
            {
                "source": "env",
                "session_header": "X-Session-ID",
                "session_value_env_var": "SECURITY_TEST_SESSION",
            },
        )

    def test_dispatch_resolves_supported_env_auth_modes(self) -> None:
        bearer_config = AuthConfig(
            method="bearer_token",
            token_env_var="SECURITY_TEST_BEARER_TOKEN",
        )

        resolved = resolve_supported_env_auth(
            bearer_config,
            environ={"SECURITY_TEST_BEARER_TOKEN": "secret-token"},
        )

        self.assertEqual(
            resolved.headers,
            {"Authorization": "Bearer secret-token"},
        )

    def test_missing_env_var_fails_closed(self) -> None:
        auth_config = AuthConfig(
            method="bearer_token",
            token_env_var="SECURITY_TEST_BEARER_TOKEN",
        )

        with self.assertRaises(MissingEnvironmentVariableError) as context:
            resolve_bearer_auth(auth_config, environ={})

        self.assertIn("SECURITY_TEST_BEARER_TOKEN", str(context.exception))
        self.assertIn("method=bearer_token", str(context.exception))

    def test_blank_env_var_value_fails_closed(self) -> None:
        auth_config = AuthConfig(
            method="cookie",
            cookie_name="sessionid",
            cookie_value_env_var="SECURITY_TEST_COOKIE",
        )

        with self.assertRaises(BlankSecretValueError) as context:
            resolve_cookie_auth(
                auth_config,
                environ={"SECURITY_TEST_COOKIE": "   "},
            )

        self.assertIn("SECURITY_TEST_COOKIE", str(context.exception))
        self.assertNotIn("cookie-value", str(context.exception))

    def test_dispatch_rejects_unsupported_form_flow(self) -> None:
        auth_config = AuthConfig(
            method="form",
            login_url="https://staging.internal.example/login",
            username_env_var="SECURITY_TEST_USERNAME",
            password_env_var="SECURITY_TEST_PASSWORD",
        )

        with self.assertRaises(UnsupportedAuthFlowError) as context:
            resolve_supported_env_auth(
                auth_config,
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
            )

        text = str(context.exception)
        self.assertIn("Unsupported authentication flow.", text)
        self.assertIn("method=form", text)
        self.assertNotIn("hunter2", text)

    def test_specific_resolver_rejects_wrong_method(self) -> None:
        auth_config = AuthConfig(
            method="session",
            session_header="X-Session-ID",
            session_value_env_var="SECURITY_TEST_SESSION",
        )

        with self.assertRaises(UnsupportedAuthFlowError) as context:
            resolve_bearer_auth(
                auth_config,
                environ={"SECURITY_TEST_SESSION": "session-value"},
            )

        self.assertIn("Expected auth method", str(context.exception))
