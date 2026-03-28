"""Helpers for stable per-run output directories and manifest metadata."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path

OUTPUTS_DIR_NAME = "outputs"
RAW_DIR_NAME = "raw"
NORMALIZED_DIR_NAME = "normalized"
REPORTS_DIR_NAME = "reports"
MANIFEST_FILE_NAME = "manifest.json"


class RunStatus(StrEnum):
    """High-level lifecycle states recorded in a run manifest."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(slots=True, frozen=True)
class RunRequest:
    """Stable input values used to prepare a run directory."""

    app_id: str
    environment: str
    profile: str
    modules: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class RunContext:
    """Resolved filesystem paths and metadata for a single run."""

    project_root: Path
    run_id: str
    app_id: str
    environment: str
    profile: str
    modules: tuple[str, ...]
    outputs_root: Path
    run_dir: Path
    raw_dir: Path
    normalized_dir: Path
    reports_dir: Path
    manifest_path: Path
    existed: bool = False


@dataclass(slots=True, frozen=True)
class RunManifest:
    """Serializable manifest content stored at the root of a run directory."""

    run_id: str
    app_id: str
    environment: str
    profile: str
    modules: tuple[str, ...]
    start_time: str
    end_time: str | None
    status: str
    exit_code: int | None


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def format_utc_timestamp(value: datetime) -> str:
    """Format a UTC timestamp using a stable ISO 8601 representation."""

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def build_run_id(
    *,
    app_id: str,
    environment: str,
    profile: str,
    when: datetime | None = None,
) -> str:
    """Build a stable run identifier from the request tuple."""

    timestamp = (when or utc_now()).astimezone(UTC)
    digest_source = "\n".join((app_id, environment, profile)).encode("utf-8")
    short_hash = sha256(digest_source).hexdigest()[:8]
    return f"{timestamp:%Y%m%d-%H%M%S}-{short_hash}"


def outputs_root(project_root: Path) -> Path:
    """Return the repository-local outputs directory."""

    return project_root / OUTPUTS_DIR_NAME


def prepare_run_context(
    project_root: Path,
    request: RunRequest,
    *,
    when: datetime | None = None,
    run_id: str | None = None,
    allow_existing: bool = False,
) -> RunContext:
    """Create or reopen a run directory and return its resolved paths."""

    resolved_run_id = run_id or build_run_id(
        app_id=request.app_id,
        environment=request.environment,
        profile=request.profile,
        when=when,
    )
    resolved_outputs_root = outputs_root(project_root)
    run_dir = resolved_outputs_root / resolved_run_id
    run_dir_exists = run_dir.exists()

    if run_dir_exists and not allow_existing:
        raise FileExistsError(f"Run directory already exists: {run_dir}")

    resolved_outputs_root.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = run_dir / RAW_DIR_NAME
    normalized_dir = run_dir / NORMALIZED_DIR_NAME
    reports_dir = run_dir / REPORTS_DIR_NAME
    raw_dir.mkdir(exist_ok=True)
    normalized_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    return RunContext(
        project_root=project_root,
        run_id=resolved_run_id,
        app_id=request.app_id,
        environment=request.environment,
        profile=request.profile,
        modules=request.modules,
        outputs_root=resolved_outputs_root,
        run_dir=run_dir,
        raw_dir=raw_dir,
        normalized_dir=normalized_dir,
        reports_dir=reports_dir,
        manifest_path=run_dir / MANIFEST_FILE_NAME,
        existed=run_dir_exists,
    )


def build_run_manifest(
    context: RunContext,
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    status: RunStatus = RunStatus.PENDING,
    exit_code: int | None = None,
) -> RunManifest:
    """Build manifest data for the provided run context."""

    return RunManifest(
        run_id=context.run_id,
        app_id=context.app_id,
        environment=context.environment,
        profile=context.profile,
        modules=context.modules,
        start_time=format_utc_timestamp(start_time or utc_now()),
        end_time=format_utc_timestamp(end_time) if end_time is not None else None,
        status=status.value,
        exit_code=exit_code,
    )


def write_run_manifest(
    context: RunContext,
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    status: RunStatus = RunStatus.PENDING,
    exit_code: int | None = None,
) -> Path:
    """Write the run manifest to disk using stable JSON formatting."""

    manifest = build_run_manifest(
        context,
        start_time=start_time,
        end_time=end_time,
        status=status,
        exit_code=exit_code,
    )
    context.manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return context.manifest_path
