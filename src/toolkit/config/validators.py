"""Cross-file validation for the configuration bundle."""

from dataclasses import dataclass
from pathlib import Path

from toolkit.config.models import (
    AppConfig,
    AppRegistry,
    ChaosProfile,
    ChaosProfileRegistry,
    PentestProfile,
    PentestProfileRegistry,
)
from toolkit.config.paths import APPS_FILE, CHAOS_PROFILES_FILE, PENTEST_PROFILES_FILE
from toolkit.safety.guards import refuse_production_like_environment


@dataclass(slots=True, frozen=True)
class BundleValidationError(RuntimeError):
    """Raised when cross-file or selection-level config validation fails."""

    message: str
    path: Path
    section: str

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True, frozen=True)
class ValidatedConfigBundle:
    """Fully parsed configuration bundle with convenience selection helpers."""

    root: Path
    apps: AppRegistry
    pentest_profiles: PentestProfileRegistry
    chaos_profiles: ChaosProfileRegistry

    def find_app(self, app_id: str, environment: str) -> AppConfig | None:
        """Return the app matching the requested id/environment pair if present."""

        for app in self.apps.apps:
            if app.id == app_id and app.environment == environment:
                return app
        return None

    def require_app(self, app_id: str, environment: str) -> AppConfig:
        """Return the requested app or raise a bundle validation error."""

        app = self.find_app(app_id=app_id, environment=environment)
        if app is None:
            raise BundleValidationError(
                f"Requested app/environment pair not found: app={app_id!r}, env={environment!r}.",
                path=self.root / APPS_FILE,
                section="selection",
            )
        return app

    def find_pentest_profile(self, name: str) -> PentestProfile | None:
        """Return a pentest profile by name if present."""

        for profile in self.pentest_profiles.profiles:
            if profile.name == name:
                return profile
        return None

    def find_chaos_profile(self, name: str) -> ChaosProfile | None:
        """Return a chaos profile by name if present."""

        for profile in self.chaos_profiles.profiles:
            if profile.name == name:
                return profile
        return None


def build_validated_config_bundle(
    *,
    root: Path,
    apps: AppRegistry,
    pentest_profiles: PentestProfileRegistry,
    chaos_profiles: ChaosProfileRegistry,
    app_id: str | None = None,
    environment: str | None = None,
) -> ValidatedConfigBundle:
    """Build and validate the cross-file configuration bundle."""

    bundle = ValidatedConfigBundle(
        root=root,
        apps=apps,
        pentest_profiles=pentest_profiles,
        chaos_profiles=chaos_profiles,
    )
    validate_config_bundle(bundle)
    if app_id is not None or environment is not None:
        if app_id is None or environment is None:
            raise BundleValidationError(
                "Both app_id and environment are required when selecting an app.",
                path=root / APPS_FILE,
                section="selection",
            )
        bundle.require_app(app_id=app_id, environment=environment)
    return bundle


def validate_config_bundle(bundle: ValidatedConfigBundle) -> None:
    """Run cross-file and safety checks on the parsed configuration bundle."""

    _validate_unique_app_pairs(bundle)
    _validate_unique_profile_names(
        profiles=bundle.pentest_profiles.profiles,
        path=bundle.root / PENTEST_PROFILES_FILE,
        section="profiles",
        profile_type="pentest",
    )
    _validate_unique_profile_names(
        profiles=bundle.chaos_profiles.profiles,
        path=bundle.root / CHAOS_PROFILES_FILE,
        section="profiles",
        profile_type="chaos",
    )

    for app in bundle.apps.apps:
        _validate_app_safety(bundle, app)
        _validate_enabled_module_profile_coverage(bundle, app)


def _validate_unique_app_pairs(bundle: ValidatedConfigBundle) -> None:
    seen_pairs: set[tuple[str, str]] = set()
    for app in bundle.apps.apps:
        key = (app.id, app.environment)
        if key in seen_pairs:
            raise BundleValidationError(
                "Duplicate app/environment pair found in apps.yaml.",
                path=bundle.root / APPS_FILE,
                section=f"apps[{app.id!r}, {app.environment!r}]",
            )
        seen_pairs.add(key)


def _validate_unique_profile_names(
    *,
    profiles: list[PentestProfile] | list[ChaosProfile],
    path: Path,
    section: str,
    profile_type: str,
) -> None:
    seen_names: set[str] = set()
    for profile in profiles:
        if profile.name in seen_names:
            raise BundleValidationError(
                f"Duplicate {profile_type} profile name found: {profile.name!r}.",
                path=path,
                section=section,
            )
        seen_names.add(profile.name)


def _validate_app_safety(bundle: ValidatedConfigBundle, app: AppConfig) -> None:
    try:
        refuse_production_like_environment(app.environment)
    except ValueError as exc:
        raise BundleValidationError(
            str(exc),
            path=bundle.root / APPS_FILE,
            section=f"apps[{app.id!r}, {app.environment!r}]",
        ) from exc


def _validate_enabled_module_profile_coverage(
    bundle: ValidatedConfigBundle, app: AppConfig
) -> None:
    if "pentest" in app.enabled_modules and not bundle.pentest_profiles.profiles:
        raise BundleValidationError(
            f"App {app.id!r} enables 'pentest' but no pentest profiles are defined.",
            path=bundle.root / PENTEST_PROFILES_FILE,
            section=f"apps[{app.id!r}, {app.environment!r}]",
        )
    if "chaos" in app.enabled_modules and not bundle.chaos_profiles.profiles:
        raise BundleValidationError(
            f"App {app.id!r} enables 'chaos' but no chaos profiles are defined.",
            path=bundle.root / CHAOS_PROFILES_FILE,
            section=f"apps[{app.id!r}, {app.environment!r}]",
        )
