from pathlib import Path
from tempfile import TemporaryDirectory

import unittest

import yaml

from toolkit.config.loader import ConfigLoadError, load_bootstrap_config
from toolkit.config.paths import APPS_FILE, CHAOS_PROFILES_FILE, PENTEST_PROFILES_FILE

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "configs"


def copy_fixture_tree(source_dir: Path, target_dir: Path) -> None:
    for name in (APPS_FILE, PENTEST_PROFILES_FILE, CHAOS_PROFILES_FILE):
        (target_dir / name).write_text(
            (source_dir / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def read_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, payload: object) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


class ConfigLoaderTests(unittest.TestCase):
    def test_load_bootstrap_config_returns_validated_bundle(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        bundle = load_bootstrap_config(
            fixture_dir,
            app_id="local-no-auth-app",
            environment="local",
        )

        self.assertEqual(bundle.root, fixture_dir)
        self.assertEqual(bundle.require_app("local-no-auth-app", "local").id, "local-no-auth-app")
        self.assertIsNotNone(bundle.find_pentest_profile("safe-web-baseline"))
        self.assertIsNotNone(bundle.find_chaos_profile("dependency-latency-baseline"))

    def test_requested_app_environment_pair_must_exist(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        with self.assertRaises(ConfigLoadError) as context:
            load_bootstrap_config(
                fixture_dir,
                app_id="missing-app",
                environment="local",
            )

        self.assertEqual(context.exception.path, fixture_dir / APPS_FILE)
        self.assertEqual(context.exception.section, "selection")

    def test_loader_keeps_file_and_logical_context_for_model_failures(self) -> None:
        fixture_dir = FIXTURE_ROOT / "invalid" / "auth-none-with-secret"

        with self.assertRaises(ConfigLoadError) as context:
            load_bootstrap_config(fixture_dir)

        self.assertEqual(context.exception.path, fixture_dir / APPS_FILE)
        self.assertEqual(context.exception.section, "apps.0.auth")
        self.assertIn("auth_none_forbids_secret_refs", str(context.exception))

    def test_bundle_rejects_missing_pentest_profiles_for_enabled_module(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            copy_fixture_tree(fixture_dir, temp_dir)
            write_yaml(temp_dir / PENTEST_PROFILES_FILE, {"profiles": []})

            with self.assertRaises(ConfigLoadError) as context:
                load_bootstrap_config(temp_dir)

        self.assertEqual(context.exception.path, temp_dir / PENTEST_PROFILES_FILE)
        self.assertIn("enables 'pentest'", str(context.exception))

    def test_bundle_rejects_duplicate_app_environment_pairs(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            copy_fixture_tree(fixture_dir, temp_dir)

            payload = read_yaml(temp_dir / APPS_FILE)
            payload["apps"].append(payload["apps"][0])
            write_yaml(temp_dir / APPS_FILE, payload)

            with self.assertRaises(ConfigLoadError) as context:
                load_bootstrap_config(temp_dir)

        self.assertEqual(context.exception.path, temp_dir / APPS_FILE)
        self.assertIn("Duplicate app/environment pair", str(context.exception))

    def test_bundle_rejects_duplicate_pentest_profile_names(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            copy_fixture_tree(fixture_dir, temp_dir)

            payload = read_yaml(temp_dir / PENTEST_PROFILES_FILE)
            payload["profiles"].append(payload["profiles"][0])
            write_yaml(temp_dir / PENTEST_PROFILES_FILE, payload)

            with self.assertRaises(ConfigLoadError) as context:
                load_bootstrap_config(temp_dir)

        self.assertEqual(context.exception.path, temp_dir / PENTEST_PROFILES_FILE)
        self.assertEqual(context.exception.section, "profiles")
        self.assertIn("Duplicate pentest profile name", str(context.exception))
