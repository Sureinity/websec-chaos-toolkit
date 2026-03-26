"""Bootstrap configuration models."""

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
    """Authentication seed material references."""

    method: AuthMethod = "none"
    token_env_var: str | None = None
    cookie_name: str | None = None
    session_header: str | None = None
    login_url: HttpUrl | None = None
    username_env_var: str | None = None
    password_env_var: str | None = None


class AppConfig(BaseModel):
    """Application/environment target configuration."""

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
    """Common safe scanner settings."""

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
    """Chaos profile description."""

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
