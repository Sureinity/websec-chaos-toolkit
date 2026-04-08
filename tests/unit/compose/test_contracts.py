"""Tests for the Compose workflow contract."""

import unittest

from toolkit.compose.contracts import (
    APP_SERVICE_DEFAULT,
    COMPOSE_CONFIG_MOUNT_PATH,
    COMPOSE_NETWORK_NAME,
    COMPOSE_OUTPUTS_MOUNT_PATH,
    COMPOSE_WORKDIR,
    PENTEST_ONLY_SERVICES,
    PENTEST_PLUS_CHAOS_SERVICES,
    REQUIRED_CONFIG_FILES,
    TOOLKIT_RUNNER_SERVICE,
    TOXIPROXY_SERVICE,
    ComposeOperatorMode,
    required_services_for,
)


class ComposeContractTests(unittest.TestCase):
    def test_service_names_are_dns_safe(self) -> None:
        for name in (
            TOOLKIT_RUNNER_SERVICE,
            APP_SERVICE_DEFAULT,
            TOXIPROXY_SERVICE,
        ):
            self.assertTrue(name.replace("-", "").isalnum())
            self.assertNotIn(" ", name)
            self.assertNotIn("_", name)

    def test_pentest_only_mode_does_not_require_toxiproxy(self) -> None:
        services = required_services_for(ComposeOperatorMode.PENTEST_ONLY)
        self.assertIn(TOOLKIT_RUNNER_SERVICE, services)
        self.assertIn(APP_SERVICE_DEFAULT, services)
        self.assertNotIn(TOXIPROXY_SERVICE, services)

    def test_pentest_plus_chaos_mode_requires_toxiproxy(self) -> None:
        services = required_services_for(ComposeOperatorMode.PENTEST_PLUS_CHAOS)
        self.assertIn(TOOLKIT_RUNNER_SERVICE, services)
        self.assertIn(APP_SERVICE_DEFAULT, services)
        self.assertIn(TOXIPROXY_SERVICE, services)

    def test_pentest_plus_chaos_is_superset_of_pentest_only(self) -> None:
        self.assertTrue(
            PENTEST_ONLY_SERVICES.issubset(PENTEST_PLUS_CHAOS_SERVICES)
        )

    def test_mount_paths_are_absolute(self) -> None:
        self.assertTrue(COMPOSE_CONFIG_MOUNT_PATH.startswith("/"))
        self.assertTrue(COMPOSE_OUTPUTS_MOUNT_PATH.startswith("/"))
        self.assertTrue(COMPOSE_WORKDIR.startswith("/"))

    def test_config_and_outputs_mount_under_workdir(self) -> None:
        self.assertTrue(
            COMPOSE_CONFIG_MOUNT_PATH.startswith(COMPOSE_WORKDIR)
        )
        self.assertTrue(
            COMPOSE_OUTPUTS_MOUNT_PATH.startswith(COMPOSE_WORKDIR)
        )

    def test_required_config_files_match_yaml_bundle(self) -> None:
        self.assertEqual(
            REQUIRED_CONFIG_FILES,
            (
                "apps.yaml",
                "pentest-profiles.yaml",
                "chaos-profiles.yaml",
            ),
        )

    def test_network_name_is_dns_safe(self) -> None:
        self.assertTrue(COMPOSE_NETWORK_NAME.replace("-", "").isalnum())

    def test_required_services_for_unknown_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            required_services_for("unknown")  # type: ignore[arg-type]
