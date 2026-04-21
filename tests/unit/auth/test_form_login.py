import unittest
from http import HTTPStatus

import httpx

from toolkit.auth.errors import (
    BlankSecretValueError,
    LoginRequestError,
    MissingEnvironmentVariableError,
    MissingSessionMaterialError,
    UnsupportedAuthFlowError,
)
from toolkit.auth.form_login import perform_form_login
from toolkit.config.models import AuthConfig


def build_form_auth_config() -> AuthConfig:
    return AuthConfig(
        method="form",
        login_url="https://staging.internal.example/login",
        username_env_var="SECURITY_TEST_USERNAME",
        password_env_var="SECURITY_TEST_PASSWORD",
        login_username_field="email",
        login_password_field="passwd",
    )


class FormLoginUnitTests(unittest.TestCase):
    def test_perform_form_login_returns_reusable_cookie_session(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if (
                request.method == "POST"
                and str(request.url) == "https://staging.internal.example/login"
            ):
                self.assertEqual(request.content.decode(), "email=alice&passwd=hunter2")
                return httpx.Response(
                    status_code=HTTPStatus.FOUND,
                    headers={
                        "Location": "https://staging.internal.example/dashboard",
                        "Set-Cookie": "sessionid=session-cookie; Path=/; HttpOnly",
                    },
                    request=request,
                )
            return httpx.Response(
                status_code=HTTPStatus.OK,
                text="dashboard",
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = perform_form_login(
            build_form_auth_config(),
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
            client=client,
        )

        self.assertEqual(session.method, "form")
        self.assertEqual(session.cookies, {"sessionid": "session-cookie"})
        self.assertEqual(session.headers, {})
        self.assertTrue(session.is_authenticated)
        self.assertEqual(
            session.provenance,
            {
                "source": "form_login",
                "login_url": "https://staging.internal.example/login",
                "username_env_var": "SECURITY_TEST_USERNAME",
                "password_env_var": "SECURITY_TEST_PASSWORD",
                "login_username_field": "email",
                "login_password_field": "passwd",
                "final_url": "https://staging.internal.example/dashboard",
                "status_code": "200",
                "cookie_transport": "mapping",
            },
        )

    def test_perform_form_login_raises_for_missing_username_env_var(self) -> None:
        with self.assertRaises(MissingEnvironmentVariableError) as context:
            perform_form_login(
                build_form_auth_config(),
                environ={"SECURITY_TEST_PASSWORD": "hunter2"},
            )

        self.assertIn("SECURITY_TEST_USERNAME", str(context.exception))

    def test_perform_form_login_raises_for_blank_password(self) -> None:
        with self.assertRaises(BlankSecretValueError) as context:
            perform_form_login(
                build_form_auth_config(),
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "   ",
                },
            )

        self.assertIn("SECURITY_TEST_PASSWORD", str(context.exception))
        self.assertNotIn("hunter2", str(context.exception))

    def test_perform_form_login_raises_for_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("password hunter2 should not leak", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        with self.assertRaises(LoginRequestError) as context:
            perform_form_login(
                build_form_auth_config(),
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
                client=client,
            )

        self.assertNotIn("hunter2", str(context.exception))
        self.assertIn("<redacted>", str(context.exception))

    def test_perform_form_login_rejects_unsupported_sso_or_mfa_flows(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=HTTPStatus.OK,
                text="MFA required before continuing.",
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        with self.assertRaises(UnsupportedAuthFlowError) as context:
            perform_form_login(
                build_form_auth_config(),
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
                client=client,
            )

        self.assertIn("Unsupported authentication flow.", str(context.exception))
        self.assertNotIn("hunter2", str(context.exception))

    def test_perform_form_login_requires_reusable_session_material(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=HTTPStatus.OK,
                text="Welcome back, alice.",
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        with self.assertRaises(MissingSessionMaterialError) as context:
            perform_form_login(
                build_form_auth_config(),
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
                client=client,
            )

        self.assertIn("No reusable cookies were returned", str(context.exception))
        self.assertNotIn("hunter2", str(context.exception))

    def test_perform_form_login_preserves_duplicate_cookie_names_as_cookie_header(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=HTTPStatus.FOUND,
                    headers=[
                        ("Location", "https://staging.internal.example/dashboard"),
                        ("Set-Cookie", "wordpress_cookie=root-cookie; Path=/; HttpOnly"),
                        (
                            "Set-Cookie",
                            "wordpress_cookie=admin-cookie; Path=/wp-admin; HttpOnly",
                        ),
                    ],
                    request=request,
                )
            return httpx.Response(
                status_code=HTTPStatus.OK,
                text="dashboard",
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = perform_form_login(
            build_form_auth_config(),
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
            client=client,
        )

        self.assertEqual(session.cookies, {})
        self.assertEqual(
            session.cookie_header, "wordpress_cookie=admin-cookie; wordpress_cookie=root-cookie"
        )
        self.assertEqual(
            session.headers["Cookie"],
            "wordpress_cookie=admin-cookie; wordpress_cookie=root-cookie",
        )
        self.assertEqual(session.provenance["cookie_transport"], "header")
