import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from toolkit.audit.fingerprint import (
    AuditFingerprintError,
    HttpxFingerprint,
    TlsFingerprint,
    capture_httpx_fingerprint,
    load_httpx_fingerprint,
    write_httpx_fingerprint,
)


class HttpxFingerprintTests(unittest.TestCase):
    def test_capture_httpx_fingerprint_collects_redirects_and_metadata(self) -> None:
        response = httpx.Response(
            status_code=200,
            text="<html><title>Dashboard</title></html>",
            headers={
                "server": "nginx",
                "x-powered-by": "FastAPI",
                "strict-transport-security": "max-age=31536000",
            },
            request=httpx.Request("GET", "https://target.internal/dashboard"),
            history=[
                httpx.Response(
                    status_code=302,
                    headers={"Location": "https://target.internal/dashboard"},
                    request=httpx.Request("GET", "https://target.internal/"),
                    extensions={"http_version": b"HTTP/1.1"},
                )
            ],
            extensions={"http_version": b"HTTP/1.1"},
        )

        client = unittest.mock.Mock()
        client.get.return_value = response
        client.__enter__ = unittest.mock.Mock(return_value=client)
        client.__exit__ = unittest.mock.Mock(return_value=False)

        with patch("toolkit.audit.fingerprint.httpx.Client", return_value=client):
            fingerprint = capture_httpx_fingerprint("https://target.internal/")

        self.assertTrue(fingerprint.reachable)
        self.assertEqual(fingerprint.status_code, 200)
        self.assertEqual(fingerprint.title, "Dashboard")
        self.assertEqual(fingerprint.server, "nginx")
        self.assertEqual(fingerprint.redirect_chain[0].status_code, 302)
        self.assertEqual(fingerprint.tls.http_version, "HTTP/1.1")

    def test_capture_httpx_fingerprint_fails_closed_on_http_error(self) -> None:
        client = unittest.mock.Mock()
        client.get.side_effect = httpx.ConnectError(
            "connection refused",
            request=httpx.Request("GET", "https://target.internal/"),
        )
        client.__enter__ = unittest.mock.Mock(return_value=client)
        client.__exit__ = unittest.mock.Mock(return_value=False)

        with patch("toolkit.audit.fingerprint.httpx.Client", return_value=client):
            with self.assertRaises(AuditFingerprintError):
                capture_httpx_fingerprint("https://target.internal/")

    def test_write_and_load_httpx_fingerprint_round_trip(self) -> None:
        fingerprint = HttpxFingerprint(
            requested_url="https://target.internal/",
            final_url="https://target.internal/dashboard",
            reachable=True,
            status_code=200,
            redirect_chain=(),
            title="Dashboard",
            server="nginx",
            technology_hints=("server: nginx",),
            tls=TlsFingerprint(
                enabled=True,
                http_version="HTTP/1.1",
                strict_transport_security="max-age=31536000",
            ),
        )

        with TemporaryDirectory() as tmp_dir_name:
            raw_dir = Path(tmp_dir_name) / "raw"
            path = write_httpx_fingerprint(raw_dir, fingerprint)
            run_dir = raw_dir.parent
            loaded = load_httpx_fingerprint(run_dir)

        self.assertEqual(path.name, "fingerprint.json")
        self.assertEqual(loaded, fingerprint)
