"""Default configuration file names."""

from pathlib import Path

APPS_FILE = Path("apps.yaml")
PENTEST_PROFILES_FILE = Path("pentest-profiles.yaml")
CHAOS_PROFILES_FILE = Path("chaos-profiles.yaml")

BOOTSTRAP_CONFIG_FILES = (
    APPS_FILE,
    PENTEST_PROFILES_FILE,
    CHAOS_PROFILES_FILE,
)
