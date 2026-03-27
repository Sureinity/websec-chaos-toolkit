from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory

import unittest

from typer.testing import CliRunner

from toolkit.cli import app
from toolkit.config.paths import APPS_FILE, CHAOS_PROFILES_FILE, PENTEST_PROFILES_FILE
from toolkit.core.exits import ExitCode

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "configs"
RUNNER = CliRunner()


def copy_fixture_tree(source_dir: Path, target_dir: Path) -> None:
    for name in (APPS_FILE, PENTEST_PROFILES_FILE, CHAOS_PROFILES_FILE):
        (target_dir / name).write_text(
            (source_dir / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


class ValidateCommandTests(unittest.TestCase):
    def test_validate_command_succeeds_for_valid_selected_app(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            copy_fixture_tree(fixture_dir, temp_dir)

            with chdir(temp_dir):
                result = RUNNER.invoke(
                    app,
                    ["validate", "--app", "local-no-auth-app", "--env", "local"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Configuration is valid.", result.stdout)
        self.assertIn("App: local-no-auth-app", result.stdout)
        self.assertIn("Environment: local", result.stdout)

    def test_validate_command_reports_selection_errors(self) -> None:
        fixture_dir = FIXTURE_ROOT / "valid" / "auth-method-matrix"

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            copy_fixture_tree(fixture_dir, temp_dir)

            with chdir(temp_dir):
                result = RUNNER.invoke(
                    app,
                    ["validate", "--app", "missing-app", "--env", "local"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Configuration validation failed.", result.stderr)
        self.assertIn("Requested app/environment pair not found", result.stderr)

    def test_validate_command_reports_model_validation_errors(self) -> None:
        fixture_dir = FIXTURE_ROOT / "invalid" / "auth-none-with-secret"

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            copy_fixture_tree(fixture_dir, temp_dir)

            with chdir(temp_dir):
                result = RUNNER.invoke(
                    app,
                    ["validate", "--app", "auth-none-with-secret", "--env", "local"],
                    catch_exceptions=False,
                )

        self.assertEqual(result.exit_code, ExitCode.CONFIG_OR_RUNTIME_ERROR)
        self.assertIn("Configuration validation failed.", result.stderr)
        self.assertIn("auth_none_forbids_secret_refs", result.stderr)
