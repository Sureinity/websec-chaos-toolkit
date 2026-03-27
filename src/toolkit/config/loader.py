"""YAML loading helpers for the configuration bundle."""

from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from toolkit.config.models import (
    AppRegistry,
    ChaosProfileRegistry,
    PentestProfileRegistry,
)
from toolkit.config.paths import APPS_FILE, CHAOS_PROFILES_FILE, PENTEST_PROFILES_FILE
from toolkit.config.validators import (
    BundleValidationError,
    ValidatedConfigBundle,
    build_validated_config_bundle,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class ConfigLoadError(RuntimeError):
    """Raised when a configuration file cannot be parsed or validated."""

    def __init__(
        self,
        message: str,
        *,
        path: Path | None = None,
        section: str | None = None,
    ) -> None:
        self.path = path
        self.section = section

        context_parts: list[str] = []
        if path is not None:
            context_parts.append(f"path={path}")
        if section is not None:
            context_parts.append(f"section={section}")

        full_message = message
        if context_parts:
            full_message = f"{message} ({', '.join(context_parts)})"

        super().__init__(full_message)


def _format_validation_error(error: ValidationError) -> tuple[str | None, str]:
    formatted_errors: list[str] = []
    first_section: str | None = None

    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        if first_section is None:
            first_section = location
        formatted_errors.append(f"{location}: {item['msg']} [{item['type']}]")

    return first_section, "; ".join(formatted_errors)


def _load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigLoadError("Unable to read configuration file.", path=path) from exc
    except yaml.YAMLError as exc:
        raise ConfigLoadError("Invalid YAML in configuration file.", path=path) from exc

    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        section, details = _format_validation_error(exc)
        raise ConfigLoadError(
            f"Configuration validation failed: {details}",
            path=path,
            section=section,
        ) from exc


def load_bootstrap_config(
    root: Path,
    *,
    app_id: str | None = None,
    environment: str | None = None,
) -> ValidatedConfigBundle:
    """Load the bootstrap configuration trio and return a validated bundle."""

    apps = _load_model(root / APPS_FILE, AppRegistry)
    pentest_profiles = _load_model(root / PENTEST_PROFILES_FILE, PentestProfileRegistry)
    chaos_profiles = _load_model(root / CHAOS_PROFILES_FILE, ChaosProfileRegistry)

    try:
        return build_validated_config_bundle(
            root=root,
            apps=apps,
            pentest_profiles=pentest_profiles,
            chaos_profiles=chaos_profiles,
            app_id=app_id,
            environment=environment,
        )
    except BundleValidationError as exc:
        raise ConfigLoadError(str(exc), path=exc.path, section=exc.section) from exc
