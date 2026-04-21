import unittest
from http import HTTPStatus

import httpx

from toolkit.auth.api_login import perform_api_login
from toolkit.auth.errors import (
    LoginRequestError,
    MissingSessionMaterialError,
)
from toolkit.config.models import AuthConfig


def build_api_login_config(
    *,
    auth_result: str = "bearer_json",
    auth_result_path: str | None = "token",
    session_header: str | None = None,
) -> AuthConfig:
    return AuthConfig(
        method="api_login",
        login_url="https://staging.internal.example/api/login",
        username_env_var="SECURITY_TEST_USERNAME",
        password_env_var="SECURITY_TEST_PASSWORD",
        login_content_type="json",
        login_username_field="username",
        login_password_field="password",
        auth_result=auth_result,
        auth_result_path=auth_result_path,
        session_header=session_header,
    )


class ApiLoginUnitTests(unittest.TestCase):
    def test_perform_api_login_returns_bearer_header_from_json(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=HTTPStatus.OK,
                    json={"token": "api-token"},
                    request=request,
                )
            return httpx.Response(status_code=HTTPStatus.NOT_FOUND, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = perform_api_login(
            build_api_login_config(),
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
            client=client,
        )

        self.assertEqual(session.method, "api_login")
        self.assertEqual(session.headers, {"Authorization": "Bearer api-token"})
        self.assertEqual(session.provenance["auth_result"], "bearer_json")

    def test_perform_api_login_returns_reusable_cookies(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=HTTPStatus.OK,
                    headers={"Set-Cookie": "sessionid=session-cookie; Path=/; HttpOnly"},
                    json={"message": "ok"},
                    request=request,
                )
            return httpx.Response(status_code=HTTPStatus.NOT_FOUND, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = perform_api_login(
            build_api_login_config(auth_result="cookie", auth_result_path=None),
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
            client=client,
        )

        self.assertEqual(session.cookies, {"sessionid": "session-cookie"})
        self.assertEqual(session.provenance["auth_result"], "cookie")
        self.assertEqual(session.provenance["cookie_transport"], "mapping")

    def test_perform_api_login_preserves_duplicate_cookie_names_as_cookie_header(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=HTTPStatus.OK,
                    headers=[
                        ("Set-Cookie", "wordpress_cookie=root-cookie; Path=/; HttpOnly"),
                        (
                            "Set-Cookie",
                            "wordpress_cookie=admin-cookie; Path=/wp-admin; HttpOnly",
                        ),
                    ],
                    json={"message": "ok"},
                    request=request,
                )
            return httpx.Response(status_code=HTTPStatus.NOT_FOUND, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = perform_api_login(
            build_api_login_config(auth_result="cookie", auth_result_path=None),
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

    def test_perform_api_login_returns_session_header_from_json(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    status_code=HTTPStatus.OK,
                    json={"data": {"session_id": "session-value"}},
                    request=request,
                )
            return httpx.Response(status_code=HTTPStatus.NOT_FOUND, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        session = perform_api_login(
            build_api_login_config(
                auth_result="session_json",
                auth_result_path="data.session_id",
                session_header="X-Session-ID",
            ),
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
            client=client,
        )

        self.assertEqual(session.headers, {"X-Session-ID": "session-value"})
        self.assertEqual(session.provenance["session_header"], "X-Session-ID")

    def test_perform_api_login_fails_for_unreachable_login_api(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("password hunter2 should not leak", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        with self.assertRaises(LoginRequestError) as context:
            perform_api_login(
                build_api_login_config(),
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
                client=client,
            )

        self.assertNotIn("hunter2", str(context.exception))
        self.assertIn("<redacted>", str(context.exception))

    def test_perform_api_login_fails_for_unusable_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=HTTPStatus.OK,
                text="not-json",
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        self.addCleanup(client.close)

        with self.assertRaises(MissingSessionMaterialError) as context:
            perform_api_login(
                build_api_login_config(),
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
                client=client,
            )

        self.assertIn("could not be parsed as JSON", str(context.exception))
        self.assertNotIn("hunter2", str(context.exception))
