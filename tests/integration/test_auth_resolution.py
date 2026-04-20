import unittest
from pathlib import Path

import httpx
import yaml

from toolkit.auth.bootstrap import resolve_auth_session
from toolkit.auth.errors import (
    BlankSecretValueError,
    MissingEnvironmentVariableError,
    MissingSessionMaterialError,
    UnsupportedAuthFlowError,
)
from toolkit.config.models import AppRegistry

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "configs"


def load_valid_apps() -> dict[str, object]:
    fixture_path = FIXTURE_ROOT / "valid" / "auth-method-matrix" / "apps.yaml"
    payload = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    registry = AppRegistry.model_validate(payload)
    return {app.id: app for app in registry.apps}


class AuthResolutionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.apps = load_valid_apps()

    def test_resolve_auth_session_supports_unauthenticated_apps(self) -> None:
        session = resolve_auth_session(self.apps["local-no-auth-app"])

        self.assertEqual(session.method, "none")
        self.assertFalse(session.is_authenticated)
        self.assertEqual(session.headers, {})
        self.assertEqual(session.cookies, {})

    def test_resolve_auth_session_supports_bearer_auth(self) -> None:
        session = resolve_auth_session(
            self.apps["local-bearer-auth-app"],
            environ={"SECURITY_TEST_BEARER_TOKEN": "secret-token"},
        )

        self.assertEqual(session.method, "bearer_token")
        self.assertTrue(session.is_authenticated)
        self.assertEqual(session.headers, {"Authorization": "Bearer secret-token"})
        self.assertEqual(session.provenance["token_env_var"], "SECURITY_TEST_BEARER_TOKEN")

    def test_resolve_auth_session_supports_cookie_auth(self) -> None:
        session = resolve_auth_session(
            self.apps["local-cookie-auth-app"],
            environ={"SECURITY_TEST_COOKIE_VALUE": "cookie-value"},
        )

        self.assertEqual(session.method, "cookie")
        self.assertEqual(session.cookies, {"sessionid": "cookie-value"})
        self.assertEqual(session.provenance["cookie_name"], "sessionid")

    def test_resolve_auth_session_supports_session_auth(self) -> None:
        session = resolve_auth_session(
            self.apps["local-session-auth-app"],
            environ={"SECURITY_TEST_SESSION_ID": "session-value"},
        )

        self.assertEqual(session.method, "session")
        self.assertEqual(session.headers, {"X-Session-ID": "session-value"})
        self.assertEqual(session.provenance["session_header"], "X-Session-ID")

    def test_resolve_auth_session_supports_form_auth(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=302,
                    headers={
                        "Location": "https://staging.internal.example/dashboard",
                        "Set-Cookie": "sessionid=session-cookie; Path=/; HttpOnly",
                    },
                    request=request,
                )
            return httpx.Response(status_code=200, text="dashboard", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = resolve_auth_session(
            self.apps["staging-form-auth-app"],
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
            client=client,
        )

        self.assertEqual(session.method, "form")
        self.assertTrue(session.is_authenticated)
        self.assertEqual(session.cookies, {"sessionid": "session-cookie"})
        self.assertEqual(session.provenance["source"], "form_login")
        self.assertEqual(
            session.provenance["final_url"], "https://staging.internal.example/dashboard"
        )

    def test_resolve_auth_session_supports_api_login_bearer_json(self) -> None:
        auth_config = self.apps["local-no-auth-app"].model_copy(deep=True)
        auth_config.auth = auth_config.auth.model_copy(
            update={
                "method": "api_login",
                "login_url": "https://staging.internal.example/api/login",
                "username_env_var": "SECURITY_TEST_USERNAME",
                "password_env_var": "SECURITY_TEST_PASSWORD",
                "login_content_type": "json",
                "login_username_field": "username",
                "login_password_field": "password",
                "auth_result": "bearer_json",
                "auth_result_path": "token",
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=200,
                    json={"token": "api-token"},
                    request=request,
                )
            return httpx.Response(status_code=404, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = resolve_auth_session(
            auth_config,
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
            client=client,
        )

        self.assertEqual(session.method, "api_login")
        self.assertEqual(session.headers, {"Authorization": "Bearer api-token"})
        self.assertEqual(session.provenance["auth_result"], "bearer_json")

    def test_resolve_auth_session_fails_for_missing_env_var(self) -> None:
        with self.assertRaises(MissingEnvironmentVariableError) as context:
            resolve_auth_session(self.apps["local-bearer-auth-app"], environ={})

        self.assertIn("SECURITY_TEST_BEARER_TOKEN", str(context.exception))

    def test_resolve_auth_session_fails_for_blank_env_var(self) -> None:
        with self.assertRaises(BlankSecretValueError) as context:
            resolve_auth_session(
                self.apps["local-cookie-auth-app"],
                environ={"SECURITY_TEST_COOKIE_VALUE": "   "},
            )

        self.assertIn("SECURITY_TEST_COOKIE_VALUE", str(context.exception))

    def test_resolve_auth_session_fails_for_unsupported_form_flow(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                text="MFA required before continuing.",
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        with self.assertRaises(UnsupportedAuthFlowError) as context:
            resolve_auth_session(
                self.apps["staging-form-auth-app"],
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
                client=client,
            )

        self.assertIn("Unsupported authentication flow.", str(context.exception))
        self.assertNotIn("hunter2", str(context.exception))

    def test_resolve_auth_session_fails_for_unusable_api_login_response(self) -> None:
        auth_config = self.apps["local-no-auth-app"].model_copy(deep=True)
        auth_config.auth = auth_config.auth.model_copy(
            update={
                "method": "api_login",
                "login_url": "https://staging.internal.example/api/login",
                "username_env_var": "SECURITY_TEST_USERNAME",
                "password_env_var": "SECURITY_TEST_PASSWORD",
                "login_content_type": "json",
                "login_username_field": "username",
                "login_password_field": "password",
                "auth_result": "cookie",
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json={"message": "ok"},
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        with self.assertRaises(MissingSessionMaterialError):
            resolve_auth_session(
                auth_config,
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
                client=client,
            )
