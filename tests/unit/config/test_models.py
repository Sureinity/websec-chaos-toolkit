import unittest
from pathlib import Path

import yaml
from pydantic import ValidationError

from toolkit.config.errors import ConfigValidationCode
from toolkit.config.models import AppRegistry, ChaosProfileRegistry, PentestProfileRegistry

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "configs"


def load_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class ConfigModelValidationTests(unittest.TestCase):
    def test_valid_auth_method_matrix_parses(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        apps = AppRegistry.model_validate(load_yaml(fixture_dir / "apps.yaml"))
        pentest_profiles = PentestProfileRegistry.model_validate(
            load_yaml(fixture_dir / "pentest-profiles.yaml")
        )
        chaos_profiles = ChaosProfileRegistry.model_validate(
            load_yaml(fixture_dir / "chaos-profiles.yaml")
        )

        self.assertEqual(len(apps.apps), 5)
        self.assertEqual(len(pentest_profiles.profiles), 1)
        self.assertEqual(len(chaos_profiles.profiles), 1)

    def test_auth_none_forbids_secret_refs(self) -> None:
        payload = load_yaml(FIXTURE_ROOT / "invalid" / "auth-none-with-secret" / "apps.yaml")

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_NONE_FORBIDS_SECRET_REFS,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_cookie_auth_requires_cookie_value_env_var(self) -> None:
        payload = load_yaml(
            FIXTURE_ROOT / "invalid" / "auth-cookie-missing-value-ref" / "apps.yaml"
        )

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_COOKIE_REQUIRES_COOKIE_VALUE_ENV_VAR,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_bearer_auth_requires_token_env_var(self) -> None:
        payload = {
            "apps": [
                {
                    "id": "bearer-token-missing-ref",
                    "environment": "local",
                    "base_url": "http://localhost:8000",
                    "host_targets": ["localhost"],
                    "target_allowlist": ["localhost", "127.0.0.1"],
                    "auth": {"method": "bearer_token"},
                    "health_endpoint": "/health",
                    "enabled_modules": ["pentest"],
                }
            ]
        }

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_BEARER_TOKEN_REQUIRES_TOKEN_ENV_VAR,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_session_auth_requires_header(self) -> None:
        payload = load_yaml(FIXTURE_ROOT / "invalid" / "auth-session-missing-header" / "apps.yaml")

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_SESSION_REQUIRES_SESSION_HEADER,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_form_auth_requires_password(self) -> None:
        payload = load_yaml(FIXTURE_ROOT / "invalid" / "auth-form-missing-password" / "apps.yaml")

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_FORM_REQUIRES_PASSWORD_ENV_VAR,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_form_auth_requires_username_field(self) -> None:
        payload = {
            "apps": [
                {
                    "id": "form-missing-username-field",
                    "environment": "staging",
                    "base_url": "https://staging.internal.example",
                    "host_targets": ["staging.internal.example"],
                    "target_allowlist": ["staging.internal.example"],
                    "auth": {
                        "method": "form",
                        "login_url": "https://staging.internal.example/login",
                        "username_env_var": "TEST_USERNAME",
                        "password_env_var": "TEST_PASSWORD",
                        "login_password_field": "password",
                    },
                    "health_endpoint": "/health",
                    "enabled_modules": ["pentest"],
                }
            ]
        }

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_FORM_REQUIRES_USERNAME_FIELD,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_api_login_requires_auth_result(self) -> None:
        payload = {
            "apps": [
                {
                    "id": "api-login-missing-result",
                    "environment": "local",
                    "base_url": "http://localhost:8000",
                    "host_targets": ["localhost"],
                    "target_allowlist": ["localhost"],
                    "auth": {
                        "method": "api_login",
                        "login_url": "http://localhost:8000/api/login",
                        "username_env_var": "TEST_USERNAME",
                        "password_env_var": "TEST_PASSWORD",
                        "login_content_type": "json",
                        "login_username_field": "username",
                        "login_password_field": "password",
                    },
                    "health_endpoint": "/health",
                    "enabled_modules": ["pentest"],
                }
            ]
        }

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_API_LOGIN_REQUIRES_AUTH_RESULT,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_api_login_session_json_requires_session_header(self) -> None:
        payload = {
            "apps": [
                {
                    "id": "api-login-session-json-missing-header",
                    "environment": "local",
                    "base_url": "http://localhost:8000",
                    "host_targets": ["localhost"],
                    "target_allowlist": ["localhost"],
                    "auth": {
                        "method": "api_login",
                        "login_url": "http://localhost:8000/api/login",
                        "username_env_var": "TEST_USERNAME",
                        "password_env_var": "TEST_PASSWORD",
                        "login_content_type": "json",
                        "login_username_field": "username",
                        "login_password_field": "password",
                        "auth_result": "session_json",
                        "auth_result_path": "data.session_id",
                    },
                    "health_endpoint": "/health",
                    "enabled_modules": ["pentest"],
                }
            ]
        }

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.AUTH_API_LOGIN_SESSION_JSON_REQUIRES_SESSION_HEADER,
        )

        self.assertEqual(error["loc"], ("apps", 0, "auth"))

    def test_base_url_host_must_be_allowlisted(self) -> None:
        payload = {
            "apps": [
                {
                    "id": "host-not-allowlisted",
                    "environment": "local",
                    "base_url": "http://localhost:9000",
                    "host_targets": ["localhost"],
                    "target_allowlist": ["127.0.0.1"],
                    "auth": {"method": "none"},
                    "health_endpoint": "/health",
                    "enabled_modules": ["pentest"],
                }
            ]
        }

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.BASE_URL_HOST_NOT_ALLOWLISTED,
        )

        self.assertEqual(error["loc"], ("apps", 0))

    def test_missing_target_allowlist_remains_invalid(self) -> None:
        payload = load_yaml(FIXTURE_ROOT / "invalid" / "missing-target-allowlist" / "apps.yaml")

        with self.assertRaises(ValidationError) as context:
            AppRegistry.model_validate(payload)

        self.assertEqual(context.exception.errors()[0]["loc"], ("apps", 0, "target_allowlist"))

    def test_missing_health_endpoint_remains_invalid(self) -> None:
        payload = load_yaml(FIXTURE_ROOT / "invalid" / "missing-health-endpoint" / "apps.yaml")

        with self.assertRaises(ValidationError) as context:
            AppRegistry.model_validate(payload)

        self.assertEqual(context.exception.errors()[0]["loc"], ("apps", 0, "health_endpoint"))

    def test_health_endpoint_must_be_absolute_path(self) -> None:
        payload = {
            "apps": [
                {
                    "id": "relative-health-endpoint",
                    "environment": "local",
                    "base_url": "http://localhost:8000",
                    "host_targets": ["localhost"],
                    "target_allowlist": ["localhost", "127.0.0.1"],
                    "auth": {"method": "none"},
                    "health_endpoint": "health",
                    "enabled_modules": ["pentest"],
                }
            ]
        }

        error = self.assert_validation_error(
            lambda: AppRegistry.model_validate(payload),
            ConfigValidationCode.HEALTH_ENDPOINT_MUST_BE_ABSOLUTE_PATH,
        )

        self.assertEqual(error["loc"], ("apps", 0, "health_endpoint"))

    def test_enabled_tool_requires_allowlist(self) -> None:
        payload = load_yaml(
            FIXTURE_ROOT / "invalid" / "pentest-tool-missing-allowlist" / "pentest-profiles.yaml"
        )

        error = self.assert_validation_error(
            lambda: PentestProfileRegistry.model_validate(payload),
            ConfigValidationCode.ENABLED_TOOL_REQUIRES_ALLOWLIST,
        )

        self.assertEqual(error["loc"], ("profiles", 0, "tools", "zap"))

    def test_optional_pentest_tools_parse_when_explicitly_configured(self) -> None:
        payload = {
            "profiles": [
                {
                    "name": "optional-tool-profile",
                    "assessment_mode": "source_tree",
                    "tools": {
                        "zap": {
                            "enabled": True,
                            "safe_mode": True,
                            "profile": "baseline",
                            "allowlisted_rules": ["headers"],
                        },
                        "trivy": {
                            "enabled": True,
                            "safe_mode": True,
                            "profile": "config-audit",
                            "allowlisted_rules": ["config/secrets"],
                        },
                        "semgrep": {
                            "enabled": False,
                            "safe_mode": True,
                            "profile": "default",
                            "allowlisted_rules": [],
                        },
                    },
                }
            ]
        }

        registry = PentestProfileRegistry.model_validate(payload)

        self.assertEqual(len(registry.profiles), 1)
        self.assertEqual(registry.profiles[0].assessment_mode, "source_tree")
        self.assertTrue(registry.profiles[0].tools.trivy.enabled)
        self.assertFalse(registry.profiles[0].tools.semgrep.enabled)
        self.assertIsNone(registry.profiles[0].tools.nmap)

    def test_missing_rollback_remains_invalid(self) -> None:
        payload = load_yaml(
            FIXTURE_ROOT / "invalid" / "chaos-missing-rollback" / "chaos-profiles.yaml"
        )

        with self.assertRaises(ValidationError) as context:
            ChaosProfileRegistry.model_validate(payload)

        self.assertEqual(context.exception.errors()[0]["loc"], ("profiles", 0, "rollback"))

    def test_production_like_environment_is_rejected_by_literal_contract(self) -> None:
        payload = load_yaml(FIXTURE_ROOT / "invalid" / "production-like-environment" / "apps.yaml")

        with self.assertRaises(ValidationError) as context:
            AppRegistry.model_validate(payload)

        self.assertEqual(context.exception.errors()[0]["loc"], ("apps", 0, "environment"))

    def test_controlled_restart_fault_is_rejected(self) -> None:
        payload = load_yaml(
            FIXTURE_ROOT / "invalid" / "controlled-restart-fault" / "chaos-profiles.yaml"
        )

        error = self.assert_validation_error(
            lambda: ChaosProfileRegistry.model_validate(payload),
            ConfigValidationCode.CONTROLLED_RESTART_NOT_IMPLEMENTED,
        )

        self.assertEqual(error["loc"], ("profiles", 0))

    def assert_validation_error(
        self,
        fn: object,
        code: ConfigValidationCode,
    ) -> dict[str, object]:
        with self.assertRaises(ValidationError) as context:
            fn()

        for error in context.exception.errors():
            if error["type"] == str(code):
                return error

        self.fail(f"Expected validation error code {code!s}, got {context.exception.errors()!r}")
