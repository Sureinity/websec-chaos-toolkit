"""Filesystem-backed operator-host locking for chaos runs."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Iterator

LOCKS_DIR_NAME = ".toolkit-locks"
CHAOS_LOCKS_DIR_NAME = "chaos"


@dataclass(slots=True, frozen=True)
class ChaosLockAcquisitionError(RuntimeError):
    """Raised when a chaos experiment lock is already held."""

    app_id: str
    environment: str
    lock_path: Path

    def __str__(self) -> str:
        return (
            "A chaos experiment is already active for "
            f"app={self.app_id!r}, env={self.environment!r}: {self.lock_path}"
        )


@dataclass(slots=True, frozen=True)
class ChaosRunLock:
    """Resolved lock metadata for one app/environment pair."""

    app_id: str
    environment: str
    key: str
    path: Path


def chaos_locks_dir(project_root: Path) -> Path:
    """Return the repository-local chaos lock directory."""

    return project_root / LOCKS_DIR_NAME / CHAOS_LOCKS_DIR_NAME


def build_chaos_lock_key(*, app_id: str, environment: str) -> str:
    """Build a filesystem-safe lock key for one app/environment pair."""

    safe_app_id = _slugify(app_id) or "app"
    safe_environment = _slugify(environment) or "env"
    digest = sha256(f"{app_id}\n{environment}".encode("utf-8")).hexdigest()[:12]
    return f"{safe_app_id}-{safe_environment}-{digest}"


def chaos_lock_path(
    project_root: Path,
    *,
    app_id: str,
    environment: str,
) -> Path:
    """Return the lock file path for one app/environment pair."""

    key = build_chaos_lock_key(app_id=app_id, environment=environment)
    return chaos_locks_dir(project_root) / f"{key}.lock"


def acquire_chaos_lock(
    project_root: Path,
    *,
    app_id: str,
    environment: str,
) -> ChaosRunLock:
    """Acquire an exclusive operator-host lock for a chaos run."""

    path = chaos_lock_path(
        project_root,
        app_id=app_id,
        environment=environment,
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "app_id": app_id,
        "environment": environment,
        "pid": os.getpid(),
        "acquired_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise ChaosLockAcquisitionError(
            app_id=app_id,
            environment=environment,
            lock_path=path,
        ) from exc

    with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
        lock_file.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    return ChaosRunLock(
        app_id=app_id,
        environment=environment,
        key=path.stem,
        path=path,
    )


def release_chaos_lock(lock: ChaosRunLock) -> None:
    """Release a previously acquired chaos run lock."""

    if lock.path.exists():
        lock.path.unlink()


@contextmanager
def hold_chaos_lock(
    project_root: Path,
    *,
    app_id: str,
    environment: str,
) -> Iterator[ChaosRunLock]:
    """Acquire and automatically release a chaos run lock."""

    lock = acquire_chaos_lock(
        project_root,
        app_id=app_id,
        environment=environment,
    )
    try:
        yield lock
    finally:
        release_chaos_lock(lock)


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
