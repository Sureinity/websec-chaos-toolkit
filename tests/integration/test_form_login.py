import unittest
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from toolkit.auth.errors import UnsupportedAuthFlowError
from toolkit.auth.form_login import perform_form_login
from toolkit.config.models import AuthConfig


class _LoginHandler(BaseHTTPRequestHandler):
    mode = "success"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/dashboard":
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            self.wfile.write(b"dashboard")
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/login":
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        parsed_body = urllib.parse.parse_qs(body)

        if parsed_body.get("username", [""])[0] != "alice":
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.end_headers()
            self.wfile.write(b"invalid credentials")
            return

        if self.mode == "success":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/dashboard")
            self.send_header("Set-Cookie", "sessionid=session-cookie; Path=/; HttpOnly")
            self.end_headers()
            return

        self.send_response(HTTPStatus.OK)
        self.end_headers()
        self.wfile.write(b"MFA required before continuing.")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class FormLoginIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), _LoginHandler)
        except PermissionError as exc:
            self.skipTest(f"Local socket binding is unavailable in this environment: {exc}")
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def test_form_login_succeeds_against_local_server(self) -> None:
        _LoginHandler.mode = "success"
        auth_config = AuthConfig(
            method="form",
            login_url=f"{self.base_url}/login",
            username_env_var="SECURITY_TEST_USERNAME",
            password_env_var="SECURITY_TEST_PASSWORD",
            login_username_field="username",
            login_password_field="password",
        )

        session = perform_form_login(
            auth_config,
            environ={
                "SECURITY_TEST_USERNAME": "alice",
                "SECURITY_TEST_PASSWORD": "hunter2",
            },
        )

        self.assertEqual(session.cookies, {"sessionid": "session-cookie"})
        self.assertEqual(session.provenance["final_url"], f"{self.base_url}/dashboard")
        self.assertEqual(session.provenance["status_code"], "200")

    def test_form_login_rejects_mfa_page_from_local_server(self) -> None:
        _LoginHandler.mode = "mfa"
        auth_config = AuthConfig(
            method="form",
            login_url=f"{self.base_url}/login",
            username_env_var="SECURITY_TEST_USERNAME",
            password_env_var="SECURITY_TEST_PASSWORD",
            login_username_field="username",
            login_password_field="password",
        )

        with self.assertRaises(UnsupportedAuthFlowError) as context:
            perform_form_login(
                auth_config,
                environ={
                    "SECURITY_TEST_USERNAME": "alice",
                    "SECURITY_TEST_PASSWORD": "hunter2",
                },
            )

        self.assertIn("Unsupported authentication flow.", str(context.exception))
        self.assertNotIn("hunter2", str(context.exception))
