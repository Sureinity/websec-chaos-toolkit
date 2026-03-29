from pathlib import Path
import unittest


class BootstrapLayoutTests(unittest.TestCase):
    def test_bootstrap_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[2]

        self.assertTrue((root / "src" / "toolkit" / "cli.py").is_file())
        self.assertTrue((root / "apps.yaml").is_file())
        self.assertTrue((root / "pentest-profiles.yaml").is_file())
        self.assertTrue((root / "chaos-profiles.yaml").is_file())
        self.assertTrue((root / "docs" / "reference" / "cli.md").is_file())
        self.assertTrue((root / "tests" / "integration" / "test_validate_command.py").is_file())
        self.assertTrue((root / "tests" / "integration" / "test_report_command.py").is_file())
        self.assertTrue((root / "tests" / "integration" / "test_form_login.py").is_file())
        self.assertTrue((root / "tests" / "integration" / "test_auth_resolution.py").is_file())
