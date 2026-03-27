"""Bootstrap configuration models.

Strict field and cross-file validation land in follow-up work. Until then, this
module also carries the locked v1 contract so the code, docs, and fixtures all
target the same schema and safety rules.
"""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

EnvironmentName = Literal["local", "staging"]
ModuleName = Literal["pentest", "chaos"]
AuthMethod = Literal["none", "bearer_token", "cookie", "session", "form"]
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


class PentestToolsConfig(BaseModel):
    """Pentest tool enablement map."""

    zap: PentestToolSettings | None = None
    nuclei: PentestToolSettings | None = None
    nmap: PentestToolSettings | None = None
    trivy: PentestToolSettings | None = None
    semgrep: PentestToolSettings | None = None


class PentestProfile(BaseModel):
    """Pentest profile description."""

    name: str
    schedule_labels: list[str] = Field(default_factory=list)
    tools: PentestToolsConfig


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


class ChaosProfileRegistry(BaseModel):
    """Top-level chaos-profiles.yaml document."""

    profiles: list[ChaosProfile] = Field(default_factory=list)
