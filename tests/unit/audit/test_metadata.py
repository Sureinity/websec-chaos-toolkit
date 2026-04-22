import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from toolkit.audit.metadata import write_audit_auth_context
from toolkit.auth.session import AuthSession


class AuditMetadataTests(unittest.TestCase):
    def test_write_audit_auth_context_filters_unsafe_provenance_keys(self) -> None:
        auth_session = AuthSession(
            method="form",
            headers={"Cookie": "sessionid=session-cookie"},
            cookie_header="sessionid=session-cookie",
            provenance={
                "source": "form_login",
                "login_url": "https://target.internal/login",
                "cookie_transport": "header",
                "cookie_header": "sessionid=session-cookie",
                "authorization": "Bearer secret-token",
            },
        )

        with TemporaryDirectory() as tmp_dir_name:
            raw_dir = Path(tmp_dir_name) / "raw"
            path = write_audit_auth_context(raw_dir, auth_session)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["auth_mode"], "form")
        self.assertTrue(payload["is_authenticated"])
        self.assertEqual(payload["provenance"]["source"], "form_login")
        self.assertEqual(payload["provenance"]["cookie_transport"], "header")
        self.assertNotIn("cookie_header", payload["provenance"])
        self.assertNotIn("authorization", payload["provenance"])
        self.assertNotIn("session-cookie", json.dumps(payload))
        self.assertNotIn("secret-token", json.dumps(payload))
