import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from toolkit.core.run_context import (
    MANIFEST_FILE_NAME,
    OUTPUTS_DIR_NAME,
    RunRequest,
    RunStatus,
    build_run_id,
    prepare_run_context,
    write_run_manifest,
)


class RunContextTests(unittest.TestCase):
    def test_build_run_id_is_stable_for_same_request_tuple(self) -> None:
        when = datetime(2026, 3, 28, 2, 3, 4, tzinfo=UTC)

        first = build_run_id(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            when=when,
        )
        second = build_run_id(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            when=when,
        )

        self.assertEqual(first, second)
        self.assertRegex(first, r"^20260328-020304-[0-9a-f]{8}$")

    def test_build_run_id_changes_when_request_tuple_changes(self) -> None:
        when = datetime(2026, 3, 28, 2, 3, 4, tzinfo=UTC)

        first = build_run_id(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            when=when,
        )
        second = build_run_id(
            app_id="sample-app",
            environment="staging",
            profile="safe-baseline",
            when=when,
        )

        self.assertNotEqual(first, second)

    def test_prepare_run_context_creates_expected_directory_layout(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest", "chaos"),
        )

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            self.assertEqual(context.outputs_root, project_root / OUTPUTS_DIR_NAME)
            self.assertTrue(context.run_dir.is_dir())
            self.assertTrue(context.raw_dir.is_dir())
            self.assertTrue(context.normalized_dir.is_dir())
            self.assertTrue(context.reports_dir.is_dir())
            self.assertEqual(context.manifest_path.name, MANIFEST_FILE_NAME)
            self.assertFalse(context.existed)

    def test_prepare_run_context_detects_existing_run_directory(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest",),
        )

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            first = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )

            with self.assertRaisesRegex(FileExistsError, "Run directory already exists"):
                prepare_run_context(
                    project_root,
                    request,
                    run_id=first.run_id,
                )

            reopened = prepare_run_context(
                project_root,
                request,
                run_id=first.run_id,
                allow_existing=True,
            )

            self.assertTrue(reopened.existed)
            self.assertEqual(reopened.run_dir, first.run_dir)

    def test_write_run_manifest_writes_stable_json_content(self) -> None:
        request = RunRequest(
            app_id="sample-app",
            environment="local",
            profile="safe-baseline",
            modules=("pentest", "chaos"),
        )
        started_at = datetime(2026, 3, 28, 2, 3, 4, tzinfo=UTC)
        finished_at = datetime(2026, 3, 28, 2, 5, 6, tzinfo=UTC)

        with TemporaryDirectory() as temp_dir_name:
            project_root = Path(temp_dir_name)
            context = prepare_run_context(
                project_root,
                request,
                run_id="20260328-020304-deadbeef",
            )
            manifest_path = write_run_manifest(
                context,
                start_time=started_at,
                end_time=finished_at,
                status=RunStatus.SUCCESS,
                exit_code=0,
            )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["run_id"], "20260328-020304-deadbeef")
        self.assertEqual(manifest["app_id"], "sample-app")
        self.assertEqual(manifest["environment"], "local")
        self.assertEqual(manifest["profile"], "safe-baseline")
        self.assertEqual(manifest["modules"], ["pentest", "chaos"])
        self.assertEqual(manifest["start_time"], "2026-03-28T02:03:04Z")
        self.assertEqual(manifest["end_time"], "2026-03-28T02:05:06Z")
        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["exit_code"], 0)
