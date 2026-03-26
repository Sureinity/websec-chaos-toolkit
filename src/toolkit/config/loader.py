"""YAML loading helpers for the scaffold."""

from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from toolkit.config.models import (
    AppRegistry,
    ChaosProfileRegistry,
    PentestProfileRegistry,
)
from toolkit.config.paths import APPS_FILE, CHAOS_PROFILES_FILE, PENTEST_PROFILES_FILE

ModelT = TypeVar("ModelT", bound=BaseModel)


class ConfigLoadError(RuntimeError):
    """Raised when a configuration file cannot be parsed or validated."""


def _load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigLoadError(f"Unable to read configuration file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"Invalid YAML in configuration file: {path}") from exc

    try:
        return model_type.model_validate(payload)
    except Exception as exc:  # pragma: no cover - exercised once schema work begins
        raise ConfigLoadError(f"Configuration validation failed for: {path}") from exc


def load_bootstrap_config(root: Path) -> tuple[AppRegistry, PentestProfileRegistry, ChaosProfileRegistry]:
    """Load the bootstrap configuration trio from the provided directory."""

    return (
        _load_model(root / APPS_FILE, AppRegistry),
        _load_model(root / PENTEST_PROFILES_FILE, PentestProfileRegistry),
        _load_model(root / CHAOS_PROFILES_FILE, ChaosProfileRegistry),
    )
