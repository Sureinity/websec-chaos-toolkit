import unittest

from toolkit.config.paths import (
    APPS_FILE,
    BOOTSTRAP_CONFIG_FILES,
    CHAOS_PROFILES_FILE,
    PENTEST_PROFILES_FILE,
)


class ConfigPathContractTests(unittest.TestCase):
    def test_bootstrap_config_file_names_match_contract(self) -> None:
        self.assertEqual(APPS_FILE.name, "apps.yaml")
        self.assertEqual(PENTEST_PROFILES_FILE.name, "pentest-profiles.yaml")
        self.assertEqual(CHAOS_PROFILES_FILE.name, "chaos-profiles.yaml")
        self.assertEqual(
            BOOTSTRAP_CONFIG_FILES,
            (
                APPS_FILE,
                PENTEST_PROFILES_FILE,
                CHAOS_PROFILES_FILE,
            ),
        )
