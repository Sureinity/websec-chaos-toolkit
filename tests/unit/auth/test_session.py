import unittest

from toolkit.auth.session import AuthSession, unauthenticated_session


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
