import re
import shutil
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from toolkit.cli import app
from toolkit.core.exits import ExitCode

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "examples" / "configs"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
RUNNER = CliRunner()


def stage_example_config_pack(source_dir: Path, target_dir: Path) -> None:
    for name in ("apps.yaml", "pentest-profiles.yaml", "chaos-profiles.yaml"):
        shutil.copy2(source_dir / name, target_dir / name)


def copy_adapter_fixtures(target_dir: Path) -> None:
    tests_root = target_dir / "tests" / "fixtures"
    for tool_name in ("zap", "nuclei", "nmap"):
        destination_dir = tests_root / tool_name
        destination_dir.mkdir(parents=True, exist_ok=True)
        source_dir = FIXTURE_ROOT / tool_name
        for path in source_dir.iterdir():
            shutil.copy2(path, destination_dir / path.name)


def copy_chaos_fixture_scenario(
    target_dir: Path,
    *,
    source_name: str,
    destination_name: str = "passing-latency",
) -> None:
    destination_dir = target_dir / "tests" / "fixtures" / "chaos" / destination_name
    destination_dir.mkdir(parents=True, exist_ok=True)
    source_dir = FIXTURE_ROOT / "chaos" / source_name
    for path in source_dir.iterdir():
        shutil.copy2(path, destination_dir / path.name)


def extract_run_id(output: str) -> str:
    match = re.search(r"Run: (\S+)", output)
    if match is None:
        raise AssertionError(f"Command output did not include a run id:\n{output}")
    return match.group(1)


class ExampleConfigSmokeTests(unittest.TestCase):
    def test_sample_webapp_pack_supports_validate_pentest_chaos_and_report(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            stage_example_config_pack(EXAMPLES_ROOT / "sample-webapp", project_root)
            copy_adapter_fixtures(project_root)
            copy_chaos_fixture_scenario(project_root, source_name="passing-latency")

            with chdir(project_root):
                validate_result = RUNNER.invoke(
                    app,
                    ["validate", "--app", "sample-internal-app", "--env", "local"],
                    catch_exceptions=False,
                )
                pentest_result = RUNNER.invoke(
                    app,
                    [
                        "pentest",
                        "run",
                        "--app",
                        "sample-internal-app",
                        "--env",
                        "local",
                        "--profile",
                        "safe-web-baseline",
                    ],
                    catch_exceptions=False,
                )
                pentest_run_id = extract_run_id(pentest_result.stdout)
                report_result = RUNNER.invoke(
                    app,
                    ["report", "build", "--run-id", pentest_run_id],
                    catch_exceptions=False,
                )
                chaos_result = RUNNER.invoke(
                    app,
                    [
                        "chaos",
                        "run",
                        "--app",
                        "sample-internal-app",
                        "--env",
                        "local",
                        "--profile",
                        "dependency-latency-baseline",
                    ],
                    catch_exceptions=False,
                )
                chaos_run_id = extract_run_id(chaos_result.stdout)

            pentest_run_dir = project_root / "outputs" / pentest_run_id
            chaos_run_dir = project_root / "outputs" / chaos_run_id

            self.assertTrue((pentest_run_dir / "manifest.json").is_file())
            self.assertTrue((pentest_run_dir / "normalized" / "findings.json").is_file())
            self.assertTrue((pentest_run_dir / "reports" / "executive-summary.md").is_file())
            self.assertTrue((chaos_run_dir / "manifest.json").is_file())
            self.assertTrue((chaos_run_dir / "normalized" / "findings.json").is_file())
            self.assertTrue((chaos_run_dir / "reports" / "executive-summary.md").is_file())
            self.assertTrue(
                (chaos_run_dir / "raw" / "chaos" / "baseline-observations.json").is_file()
            )
            self.assertTrue(
                (chaos_run_dir / "raw" / "chaos" / "experiment-observations.json").is_file()
            )

        self.assertEqual(validate_result.exit_code, ExitCode.SUCCESS)
        self.assertEqual(pentest_result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertEqual(report_result.exit_code, ExitCode.SUCCESS)
        self.assertEqual(chaos_result.exit_code, ExitCode.SUCCESS)
        self.assertIn("Configuration is valid.", validate_result.stdout)
        self.assertIn("Pentest run completed.", pentest_result.stdout)
        self.assertIn("Status: findings", pentest_result.stdout)
        self.assertIn("Report generated.", report_result.stdout)
        self.assertIn("Chaos run completed.", chaos_result.stdout)
        self.assertIn("Status: success", chaos_result.stdout)

    def test_sample_api_pack_supports_validate_and_authenticated_pentest(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            stage_example_config_pack(EXAMPLES_ROOT / "sample-api", project_root)
            copy_adapter_fixtures(project_root)

            with chdir(project_root):
                validate_result = RUNNER.invoke(
                    app,
                    ["validate", "--app", "sample-api-bearer-app", "--env", "staging"],
                    catch_exceptions=False,
                )
                pentest_result = RUNNER.invoke(
                    app,
                    [
                        "pentest",
                        "run",
                        "--app",
                        "sample-api-bearer-app",
                        "--env",
                        "staging",
                        "--profile",
                        "safe-api-baseline",
                    ],
                    env={"SAMPLE_API_BEARER_TOKEN": "placeholder-token"},
                    catch_exceptions=False,
                )
                pentest_run_id = extract_run_id(pentest_result.stdout)

            pentest_run_dir = project_root / "outputs" / pentest_run_id
            self.assertTrue((pentest_run_dir / "manifest.json").is_file())
            self.assertTrue((pentest_run_dir / "normalized" / "findings.json").is_file())
            self.assertTrue((pentest_run_dir / "reports" / "executive-summary.md").is_file())

        self.assertEqual(validate_result.exit_code, ExitCode.SUCCESS)
        self.assertEqual(pentest_result.exit_code, ExitCode.FINDINGS_OR_FAILURE)
        self.assertIn("Configuration is valid.", validate_result.stdout)
        self.assertIn("App: sample-api-bearer-app", validate_result.stdout)
        self.assertIn("Pentest run completed.", pentest_result.stdout)
        self.assertIn("Status: findings", pentest_result.stdout)
