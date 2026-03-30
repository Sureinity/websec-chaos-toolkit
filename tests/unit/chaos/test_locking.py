import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from toolkit.chaos.locking import (
    LOCKS_DIR_NAME,
    CHAOS_LOCKS_DIR_NAME,
    ChaosLockAcquisitionError,
    acquire_chaos_lock,
    build_chaos_lock_key,
    chaos_locks_dir,
    hold_chaos_lock,
    release_chaos_lock,
)


class ChaosLockingTests(unittest.TestCase):
    def test_acquire_chaos_lock_creates_lock_file_with_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            lock = acquire_chaos_lock(
                project_root,
                app_id="sample-app",
                environment="local",
            )

            self.assertEqual(
                lock.path,
                project_root / LOCKS_DIR_NAME / CHAOS_LOCKS_DIR_NAME / f"{lock.key}.lock",
            )
            self.assertTrue(lock.path.exists())
            payload = json.loads(lock.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["app_id"], "sample-app")
            self.assertEqual(payload["environment"], "local")
            self.assertIn("pid", payload)
            self.assertIn("acquired_at", payload)

    def test_acquire_chaos_lock_rejects_second_lock_for_same_app_environment(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            lock = acquire_chaos_lock(
                project_root,
                app_id="sample-app",
                environment="local",
            )

            with self.assertRaises(ChaosLockAcquisitionError):
                acquire_chaos_lock(
                    project_root,
                    app_id="sample-app",
                    environment="local",
                )

            release_chaos_lock(lock)

    def test_different_environment_uses_different_lock_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            local_lock = acquire_chaos_lock(
                project_root,
                app_id="sample-app",
                environment="local",
            )
            staging_lock = acquire_chaos_lock(
                project_root,
                app_id="sample-app",
                environment="staging",
            )

            self.assertNotEqual(local_lock.path, staging_lock.path)
            self.assertTrue(local_lock.path.exists())
            self.assertTrue(staging_lock.path.exists())

    def test_hold_chaos_lock_releases_file_after_context_exit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            with hold_chaos_lock(
                project_root,
                app_id="sample-app",
                environment="local",
            ) as lock:
                self.assertTrue(lock.path.exists())

            self.assertFalse(lock.path.exists())

    def test_build_chaos_lock_key_is_stable_and_safe(self) -> None:
        key = build_chaos_lock_key(
            app_id="payments api/internal",
            environment="local",
        )

        self.assertEqual(
            key,
            build_chaos_lock_key(
                app_id="payments api/internal",
                environment="local",
            ),
        )
        self.assertNotIn("/", key)
        self.assertIn("payments-api-internal-local-", key)

    def test_chaos_locks_dir_uses_hidden_repo_local_runtime_path(self) -> None:
        project_root = Path("/tmp/example-project")

        self.assertEqual(
            chaos_locks_dir(project_root),
            project_root / LOCKS_DIR_NAME / CHAOS_LOCKS_DIR_NAME,
        )
