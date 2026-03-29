import unittest

from toolkit.auth.errors import (
    BlankSecretValueError,
    LoginRequestError,
    MissingEnvironmentVariableError,
    MissingSessionMaterialError,
    UnsupportedAuthFlowError,
)


class AuthErrorTests(unittest.TestCase):
    def test_missing_environment_variable_error_is_specific_and_safe(self) -> None:
        error = MissingEnvironmentVariableError(
            "SECURITY_TEST_BEARER_TOKEN",
            method="bearer_token",
        )

        text = str(error)
        self.assertIn("SECURITY_TEST_BEARER_TOKEN", text)
        self.assertIn("method=bearer_token", text)

    def test_blank_secret_value_error_uses_env_var_name_not_secret_value(self) -> None:
        error = BlankSecretValueError(
            "SECURITY_TEST_PASSWORD",
            method="form",
        )

        text = str(error)
        self.assertIn("SECURITY_TEST_PASSWORD", text)
        self.assertNotIn("hunter2", text)

    def test_unsupported_auth_flow_error_preserves_safe_detail(self) -> None:
        error = UnsupportedAuthFlowError(
            method="form",
            detail="SSO redirect detected; MFA required.",
        )

        text = str(error)
        self.assertIn("Unsupported authentication flow.", text)
        self.assertIn("SSO redirect detected", text)
        self.assertIn("method=form", text)

    def test_login_request_error_redacts_secrets_from_detail(self) -> None:
        error = LoginRequestError(
            "https://staging.internal.example/login",
            detail="Received password hunter2 and token secret-token during failure.",
            secrets=("hunter2", "secret-token"),
        )

        text = str(error)
        self.assertIn("https://staging.internal.example/login", text)
        self.assertNotIn("hunter2", text)
        self.assertNotIn("secret-token", text)
        self.assertIn("<redacted>", text)

    def test_missing_session_material_error_redacts_sensitive_response_detail(self) -> None:
        error = MissingSessionMaterialError(
            method="form",
            detail="Response body included session=session-cookie but no reusable auth state.",
            secrets=("session-cookie",),
        )

        text = str(error)
        self.assertIn("method=form", text)
        self.assertNotIn("session-cookie", text)
        self.assertIn("<redacted>", text)
