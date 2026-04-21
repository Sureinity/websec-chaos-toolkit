import unittest

import httpx

from toolkit.auth.session import (
    AuthSession,
    extract_cookie_material,
    resolve_cookie_header,
    unauthenticated_session,
)


class AuthSessionTests(unittest.TestCase):
    def test_unauthenticated_session_is_canonical_and_not_authenticated(self) -> None:
        session = unauthenticated_session()

        self.assertEqual(session.method, "none")
        self.assertEqual(session.headers, {})
        self.assertEqual(session.cookies, {})
        self.assertEqual(session.provenance, {"source": "none"})
        self.assertFalse(session.is_authenticated)

    def test_authenticated_session_reports_true(self) -> None:
        session = AuthSession(
            method="bearer_token",
            headers={"Authorization": "Bearer secret-token"},
            provenance={"source": "env", "token_env_var": "SECURITY_TEST_BEARER_TOKEN"},
        )

        self.assertTrue(session.is_authenticated)
        self.assertEqual(session.provenance["token_env_var"], "SECURITY_TEST_BEARER_TOKEN")

    def test_resolve_cookie_header_prefers_explicit_cookie_header(self) -> None:
        session = AuthSession(
            method="form",
            headers={"Cookie": "a=1; a=2"},
            cookie_header="a=1; a=2",
        )

        self.assertEqual(resolve_cookie_header(session), "a=1; a=2")

    def test_extract_cookie_material_falls_back_to_header_for_duplicate_names(self) -> None:
        client = httpx.Client()
        self.addCleanup(client.close)
        client.cookies.set("wordpress_cookie", "root", domain="example.com", path="/")
        client.cookies.set("wordpress_cookie", "admin", domain="example.com", path="/wp-admin")

        cookies, cookie_header = extract_cookie_material(client.cookies.jar)

        self.assertEqual(cookies, {})
        self.assertEqual(cookie_header, "wordpress_cookie=admin; wordpress_cookie=root")
