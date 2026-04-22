"""Integration tests for the Compose workflow assets and contract.

These tests verify the static contract of the Compose files: presence,
service definitions, mount points, network model, and alignment with
the example Compose-aware config pack. They do NOT spin up real
containers — that would require Docker on the test host.
"""

import unittest
from pathlib import Path

import yaml

from toolkit.compose.contracts import (
    APP_SERVICE_DEFAULT,
    COMPOSE_CONFIG_MOUNT_PATH,
    COMPOSE_NETWORK_NAME,
    COMPOSE_OUTPUTS_MOUNT_PATH,
    COMPOSE_WORKDIR,
    REQUIRED_CONFIG_FILES,
    TOOLKIT_RUNNER_SERVICE,
    TOXIPROXY_SERVICE,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
COMPOSE_ENV_EXAMPLE = REPO_ROOT / "compose" / "toolkit-runner.env.example"
COMPOSE_EXAMPLE_OVERLAY = (
    REPO_ROOT / "compose" / "examples" / "sample-webapp-compose" / "docker-compose.override.yml"
)
COMPOSE_CONFIG_PACK = REPO_ROOT / "examples" / "configs" / "sample-webapp-compose"
FIXTURE_FILE = REPO_ROOT / "tests" / "fixtures" / "compose" / "expected-services.yaml"


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


class ComposeFilePresenceTests(unittest.TestCase):
    def test_root_compose_file_exists(self) -> None:
        self.assertTrue(COMPOSE_FILE.is_file())

    def test_env_example_file_exists(self) -> None:
        self.assertTrue(COMPOSE_ENV_EXAMPLE.is_file())

    def test_overlay_example_exists(self) -> None:
        self.assertTrue(COMPOSE_EXAMPLE_OVERLAY.is_file())

    def test_compose_aware_config_pack_exists(self) -> None:
        self.assertTrue(COMPOSE_CONFIG_PACK.is_dir())
        for name in REQUIRED_CONFIG_FILES:
            self.assertTrue(
                (COMPOSE_CONFIG_PACK / name).is_file(),
                f"missing {name} in Compose-aware config pack",
            )


class ComposeServiceDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.compose = _load_compose()
        self.services = self.compose.get("services", {})

    def test_required_services_defined(self) -> None:
        self.assertIn(TOOLKIT_RUNNER_SERVICE, self.services)
        self.assertIn(APP_SERVICE_DEFAULT, self.services)
        self.assertIn(TOXIPROXY_SERVICE, self.services)

    def test_toolkit_runner_uses_expected_workdir(self) -> None:
        runner = self.services[TOOLKIT_RUNNER_SERVICE]
        self.assertEqual(runner.get("working_dir"), COMPOSE_WORKDIR)

    def test_toolkit_runner_mounts_config_and_outputs(self) -> None:
        runner = self.services[TOOLKIT_RUNNER_SERVICE]
        volumes = runner.get("volumes", [])
        mount_targets = [vol.split(":")[1] for vol in volumes if ":" in vol]
        self.assertIn(COMPOSE_CONFIG_MOUNT_PATH, mount_targets)
        self.assertIn(COMPOSE_OUTPUTS_MOUNT_PATH, mount_targets)

    def test_toxiproxy_is_chaos_profile_gated(self) -> None:
        toxiproxy = self.services[TOXIPROXY_SERVICE]
        profiles = toxiproxy.get("profiles", [])
        self.assertIn("chaos", profiles)

    def test_all_services_join_shared_network(self) -> None:
        for name, service in self.services.items():
            networks = service.get("networks", [])
            self.assertIn(
                COMPOSE_NETWORK_NAME,
                networks,
                f"service {name} not on {COMPOSE_NETWORK_NAME}",
            )

    def test_shared_network_defined(self) -> None:
        networks = self.compose.get("networks", {})
        self.assertIn(COMPOSE_NETWORK_NAME, networks)


class ComposeAwareConfigPackTests(unittest.TestCase):
    def test_apps_yaml_uses_service_name_base_url(self) -> None:
        apps_yaml = COMPOSE_CONFIG_PACK / "apps.yaml"
        payload = yaml.safe_load(apps_yaml.read_text(encoding="utf-8"))
        first_app = payload["apps"][0]
        self.assertIn(
            APP_SERVICE_DEFAULT,
            first_app["base_url"],
            "Compose config pack must use service name as base_url host",
        )

    def test_apps_yaml_allowlist_includes_service_name(self) -> None:
        apps_yaml = COMPOSE_CONFIG_PACK / "apps.yaml"
        payload = yaml.safe_load(apps_yaml.read_text(encoding="utf-8"))
        first_app = payload["apps"][0]
        self.assertIn(APP_SERVICE_DEFAULT, first_app["target_allowlist"])

    def test_chaos_profile_target_service_aligns_with_compose_service(
        self,
    ) -> None:
        chaos_yaml = COMPOSE_CONFIG_PACK / "chaos-profiles.yaml"
        payload = yaml.safe_load(chaos_yaml.read_text(encoding="utf-8"))
        first_profile = payload["profiles"][0]
        self.assertEqual(
            first_profile["target_service"],
            APP_SERVICE_DEFAULT,
            "chaos target_service should match the Compose app service name",
        )


class ComposeFixtureTests(unittest.TestCase):
    """Verify the test fixture matches the actual Compose file."""

    def test_fixture_lists_all_required_services(self) -> None:
        fixture = yaml.safe_load(FIXTURE_FILE.read_text(encoding="utf-8"))
        compose = _load_compose()
        compose_services = set(compose.get("services", {}).keys())
        fixture_services = {
            entry["name"] for entry in fixture["services"] if entry.get("required", False)
        }
        self.assertTrue(fixture_services.issubset(compose_services))
