"""Bootstrap configuration models.

Strict field and cross-file validation land in follow-up work. Until then, this
module also carries the locked v1 contract so the code, docs, and fixtures all
target the same schema and safety rules.
"""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from toolkit.config.errors import ConfigValidationCode, config_error

EnvironmentName = Literal["local", "staging"]
ModuleName = Literal["pentest", "chaos"]
AuthMethod = Literal["none", "bearer_token", "cookie", "session", "form"]
PentestAssessmentModeName = Literal["remote_web", "source_tree", "artifact_image"]
FaultType = Literal[
    "latency",
    "bandwidth",
    "packet_loss",
    "timeout",
    "connection_refused",
    "controlled_restart",
]


class MetricsConfig(BaseModel):
    """Optional metrics source description."""

    endpoint: HttpUrl | None = None
    query: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Metrics query must not be blank.",
            )
        return stripped


class AuthConfig(BaseModel):
    """Authentication seed material references.

    Locked v1 auth contract:
    - ``none``: no auth-specific secret reference fields are allowed
    - ``bearer_token``: requires ``token_env_var``
    - ``cookie``: requires ``cookie_name`` and ``cookie_value_env_var``
    - ``session``: requires ``session_header`` and ``session_value_env_var``
    - ``form``: requires ``login_url``, ``username_env_var``, and
      ``password_env_var``

    The config stores references only. Real secrets and session material must
    be supplied from the runtime environment, never committed to YAML.
    """

    method: AuthMethod = "none"
    token_env_var: str | None = None
    cookie_name: str | None = None
    cookie_value_env_var: str | None = None
    session_header: str | None = None
    session_value_env_var: str | None = None
    login_url: HttpUrl | None = None
    username_env_var: str | None = None
    password_env_var: str | None = None

    @field_validator(
        "token_env_var",
        "cookie_name",
        "cookie_value_env_var",
        "session_header",
        "session_value_env_var",
        "username_env_var",
        "password_env_var",
    )
    @classmethod
    def validate_optional_string_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Config string values must not be blank.",
            )
        return stripped

    @model_validator(mode="after")
    def validate_auth_contract(self) -> "AuthConfig":
        secret_ref_fields = {
            "token_env_var": self.token_env_var,
            "cookie_name": self.cookie_name,
            "cookie_value_env_var": self.cookie_value_env_var,
            "session_header": self.session_header,
            "session_value_env_var": self.session_value_env_var,
            "login_url": self.login_url,
            "username_env_var": self.username_env_var,
            "password_env_var": self.password_env_var,
        }

        if self.method == "none":
            populated_fields = [
                name for name, value in secret_ref_fields.items() if value is not None
            ]
            if populated_fields:
                raise config_error(
                    ConfigValidationCode.AUTH_NONE_FORBIDS_SECRET_REFS,
                    "Auth method 'none' does not allow secret reference fields: {fields}.",
                    fields=", ".join(populated_fields),
                )
            return self

        if self.method == "bearer_token" and self.token_env_var is None:
            raise config_error(
                ConfigValidationCode.AUTH_BEARER_TOKEN_REQUIRES_TOKEN_ENV_VAR,
                "Auth method 'bearer_token' requires token_env_var.",
            )
        if self.method == "cookie":
            if self.cookie_name is None:
                raise config_error(
                    ConfigValidationCode.AUTH_COOKIE_REQUIRES_COOKIE_NAME,
                    "Auth method 'cookie' requires cookie_name.",
                )
            if self.cookie_value_env_var is None:
                raise config_error(
                    ConfigValidationCode.AUTH_COOKIE_REQUIRES_COOKIE_VALUE_ENV_VAR,
                    "Auth method 'cookie' requires cookie_value_env_var.",
                )
        if self.method == "session":
            if self.session_header is None:
                raise config_error(
                    ConfigValidationCode.AUTH_SESSION_REQUIRES_SESSION_HEADER,
                    "Auth method 'session' requires session_header.",
                )
            if self.session_value_env_var is None:
                raise config_error(
                    ConfigValidationCode.AUTH_SESSION_REQUIRES_SESSION_VALUE_ENV_VAR,
                    "Auth method 'session' requires session_value_env_var.",
                )
        if self.method == "form":
            if self.login_url is None:
                raise config_error(
                    ConfigValidationCode.AUTH_FORM_REQUIRES_LOGIN_URL,
                    "Auth method 'form' requires login_url.",
                )
            if self.username_env_var is None:
                raise config_error(
                    ConfigValidationCode.AUTH_FORM_REQUIRES_USERNAME_ENV_VAR,
                    "Auth method 'form' requires username_env_var.",
                )
            if self.password_env_var is None:
                raise config_error(
                    ConfigValidationCode.AUTH_FORM_REQUIRES_PASSWORD_ENV_VAR,
                    "Auth method 'form' requires password_env_var.",
                )

        return self


class AppConfig(BaseModel):
    """Application/environment target configuration.

    Locked v1 application rules:
    - ``environment`` is limited to ``local`` or ``staging``
    - ``health_endpoint`` must be a non-empty absolute path starting with ``/``
    - ``host_targets`` and ``target_allowlist`` must both be non-empty
    - the ``base_url`` host must be covered by ``target_allowlist``
    - ``enabled_modules`` must contain one or both of ``pentest`` and
      ``chaos``
    """

    id: str
    environment: EnvironmentName
    base_url: HttpUrl
    host_targets: list[str] = Field(min_length=1)
    target_allowlist: list[str] = Field(min_length=1)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    health_endpoint: str
    metrics: MetricsConfig | None = None
    enabled_modules: list[ModuleName] = Field(min_length=1)

    @field_validator("id", "health_endpoint")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Config string values must not be blank.",
            )
        return stripped

    @field_validator("health_endpoint")
    @classmethod
    def validate_health_endpoint(cls, value: str) -> str:
        if not value.startswith("/"):
            raise config_error(
                ConfigValidationCode.HEALTH_ENDPOINT_MUST_BE_ABSOLUTE_PATH,
                "Health endpoint must start with '/'.",
            )
        return value

    @field_validator("host_targets", "target_allowlist", mode="after")
    @classmethod
    def validate_target_lists(cls, values: list[str]) -> list[str]:
        normalized_values = []
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise config_error(
                    ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                    "Target lists must not include blank values.",
                )
            normalized_values.append(stripped)
        return normalized_values

    @field_validator("enabled_modules", mode="after")
    @classmethod
    def validate_enabled_modules(cls, values: list[ModuleName]) -> list[ModuleName]:
        if len(set(values)) != len(values):
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Enabled modules must not contain duplicates.",
            )
        return values

    @model_validator(mode="after")
    def validate_base_url_host_coverage(self) -> "AppConfig":
        base_host = self.base_url.host
        if base_host not in self.target_allowlist:
            raise config_error(
                ConfigValidationCode.BASE_URL_HOST_NOT_ALLOWLISTED,
                "Base URL host '{host}' must be present in target_allowlist.",
                host=base_host,
            )
        return self


class AppRegistry(BaseModel):
    """Top-level apps.yaml document."""

    apps: list[AppConfig] = Field(default_factory=list)


class PentestToolSettings(BaseModel):
    """Common safe scanner settings.

    Locked v1 pentest profile rules:
    - enabled tools must declare at least one allowlisted rule or template
    - safe mode stays enabled by default
    - adapters may skip disabled tools cleanly without failing the run
    """

    enabled: bool = True
    safe_mode: bool = True
    profile: str = "baseline"
    allowlisted_rules: list[str] = Field(default_factory=list)

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Tool profile names must not be blank.",
            )
        return stripped

    @field_validator("allowlisted_rules", mode="after")
    @classmethod
    def validate_allowlisted_rules(cls, values: list[str]) -> list[str]:
        normalized_values = []
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise config_error(
                    ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                    "Allowlisted rules must not include blank values.",
                )
            normalized_values.append(stripped)
        return normalized_values

    @model_validator(mode="after")
    def validate_enabled_tool_contract(self) -> "PentestToolSettings":
        if self.enabled and not self.allowlisted_rules:
            raise config_error(
                ConfigValidationCode.ENABLED_TOOL_REQUIRES_ALLOWLIST,
                "Enabled pentest tools must declare at least one allowlisted rule or template.",
            )
        return self


class PentestToolsConfig(BaseModel):
    """Pentest tool enablement map.

    Core tools stay first-class in the default DAST-first product shape:
    - ``zap``
    - ``nuclei``
    - ``nmap``

    Optional tools may be configured explicitly without changing the default
    flow:
    - ``trivy``
    - ``semgrep``
    """

    zap: PentestToolSettings | None = None
    nuclei: PentestToolSettings | None = None
    nmap: PentestToolSettings | None = None
    trivy: PentestToolSettings | None = None
    semgrep: PentestToolSettings | None = None


class PentestProfile(BaseModel):
    """Pentest profile description.

    Core tool ordering must remain deterministic. Optional adapters appear in
    plans only when explicitly configured in a profile.

    assessment_mode locks the intended target type:
    - remote_web
    - source_tree
    - artifact_image
    """

    name: str
    assessment_mode: PentestAssessmentModeName = "remote_web"
    schedule_labels: list[str] = Field(default_factory=list)
    tools: PentestToolsConfig

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Profile names must not be blank.",
            )
        return stripped

    @field_validator("schedule_labels", mode="after")
    @classmethod
    def validate_schedule_labels(cls, values: list[str]) -> list[str]:
        normalized_values = []
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise config_error(
                    ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                    "Schedule labels must not include blank values.",
                )
            normalized_values.append(stripped)
        return normalized_values


class PentestProfileRegistry(BaseModel):
    """Top-level pentest-profiles.yaml document."""

    profiles: list[PentestProfile] = Field(default_factory=list)


class AbortThresholds(BaseModel):
    """Health and metrics guardrails."""

    consecutive_health_failures: int = Field(default=1, ge=1)
    max_error_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class RollbackConfig(BaseModel):
    """Rollback definition for a chaos experiment."""

    method: str
    description: str | None = None

    @field_validator("method", "description")
    @classmethod
    def validate_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Rollback values must not be blank.",
            )
        return stripped


class ChaosProfile(BaseModel):
    """Chaos profile description.

    Locked v1 chaos rules:
    - every injectable fault requires ``abort_thresholds`` and ``rollback``
    - only one reversible fault is intended to run at a time
    - ``controlled_restart`` remains schema-reserved but should be rejected by
      validation until a dedicated implementation exists
    """

    name: str
    fault_type: FaultType
    target_service: str
    baseline_duration_seconds: int = Field(ge=1)
    experiment_duration_seconds: int = Field(ge=1)
    abort_thresholds: AbortThresholds
    rollback: RollbackConfig

    @field_validator("name", "target_service")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise config_error(
                ConfigValidationCode.EMPTY_STRING_NOT_ALLOWED,
                "Config string values must not be blank.",
            )
        return stripped

    @model_validator(mode="after")
    def validate_supported_fault_type(self) -> "ChaosProfile":
        if self.fault_type == "controlled_restart":
            raise config_error(
                ConfigValidationCode.CONTROLLED_RESTART_NOT_IMPLEMENTED,
                "Fault type 'controlled_restart' is reserved but not implemented in v1.",
            )
        return self


class ChaosProfileRegistry(BaseModel):
    """Top-level chaos-profiles.yaml document."""

    profiles: list[ChaosProfile] = Field(default_factory=list)
