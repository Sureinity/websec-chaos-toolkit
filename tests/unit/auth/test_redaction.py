import unittest

from toolkit.auth.redaction import REDACTED_MARKER, redact_known_secrets, redact_secret


class RedactionTests(unittest.TestCase):
    def test_redact_secret_masks_middle_of_long_secret(self) -> None:
        masked = redact_secret("super-secret-token")

        self.assertNotEqual(masked, "super-secret-token")
        self.assertTrue(masked.startswith("su"))
        self.assertTrue(masked.endswith("en"))
        self.assertIn(REDACTED_MARKER, masked)

    def test_redact_secret_fully_masks_short_or_blank_values(self) -> None:
        self.assertEqual(redact_secret("abc"), REDACTED_MARKER)
        self.assertEqual(redact_secret("   "), REDACTED_MARKER)
        self.assertEqual(redact_secret(None), REDACTED_MARKER)

    def test_redact_known_secrets_replaces_multiple_secret_values(self) -> None:
        redacted = redact_known_secrets(
            "token=secret-token cookie=session-cookie user=alice",
            ["secret-token", "session-cookie", "alice"],
        )

        self.assertNotIn("secret-token", redacted)
        self.assertNotIn("session-cookie", redacted)
        self.assertNotIn("alice", redacted)
        self.assertGreaterEqual(redacted.count(REDACTED_MARKER), 3)
