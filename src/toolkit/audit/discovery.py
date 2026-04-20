"""Katana-backed route discovery for URL-first audit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from toolkit.auth.session import AuthSession
from toolkit.runtime.base import RuntimeBackend
from toolkit.runtime.models import RuntimeRequest


@dataclass(slots=True, frozen=True)
class KatanaDiscoveryResult:
    """Discovery artifacts and deduplicated same-origin routes for one seed URL."""

    raw_output_path: Path
    route_manifest_path: Path
    routes: tuple[str, ...]


class AuditDiscoveryError(RuntimeError):
    """Raised when route discovery cannot complete safely."""


def run_katana_discovery(
    *,
    seed_url: str,
    raw_dir: Path,
    runtime: RuntimeBackend,
    auth_session: AuthSession | None = None,
) -> KatanaDiscoveryResult:
    """Discover same-origin routes for one audit seed URL via katana."""

    availability = runtime.check_tool_available("katana")
    if not availability.available:
        raise AuditDiscoveryError(
            f"katana is required for audit discovery but is not available: {availability.reason}"
        )

    output_path = raw_dir / "katana" / "results.jsonl"
    request = RuntimeRequest(
        tool="katana",
        command=_build_katana_command(
            seed_url=seed_url,
            output_path=output_path,
            auth_session=auth_session,
        ),
        output_path=output_path,
        timeout_seconds=120.0,
    )

    result = runtime.execute(request)
    if not result.succeeded:
        detail = (
            f"katana timed out after {request.timeout_seconds}s"
            if result.timed_out
            else f"katana exited with code {result.returncode}"
        )
        raise AuditDiscoveryError(detail)

    if not output_path.is_file():
        raise AuditDiscoveryError("katana did not produce the expected discovery artifact.")

    routes = _load_same_origin_routes(output_path, seed_url=seed_url)
    route_manifest_path = output_path.parent / "discovered-routes.txt"
    route_manifest_path.write_text("\n".join(routes) + "\n", encoding="utf-8")

    return KatanaDiscoveryResult(
        raw_output_path=output_path,
        route_manifest_path=route_manifest_path,
        routes=tuple(routes),
    )


def _build_katana_command(
    *,
    seed_url: str,
    output_path: Path,
    auth_session: AuthSession | None,
) -> tuple[str, ...]:
    command: list[str] = [
        "katana",
        "-u",
        seed_url,
        "-jsonl",
        "-silent",
        "-o",
        str(output_path),
    ]
    for header in _auth_headers(auth_session).values():
        command.extend(["-H", header])
    return tuple(command)


def _auth_headers(auth_session: AuthSession | None) -> dict[str, str]:
    if auth_session is None:
        return {}

    headers = {name: f"{name}: {value}" for name, value in auth_session.headers.items()}
    if auth_session.cookies:
        cookie_header = "; ".join(f"{name}={value}" for name, value in auth_session.cookies.items())
        headers["Cookie"] = f"Cookie: {cookie_header}"
    return headers


def _load_same_origin_routes(output_path: Path, *, seed_url: str) -> list[str]:
    seed = urlsplit(seed_url)
    same_origin: set[str] = {seed_url}

    for line in output_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        candidate = _extract_discovered_url(payload)
        if candidate is None:
            continue
        parsed = urlsplit(candidate)
        if parsed.scheme == seed.scheme and parsed.netloc == seed.netloc:
            same_origin.add(candidate)

    return [seed_url, *sorted(route for route in same_origin if route != seed_url)]


def load_discovered_routes(run_dir: Path) -> tuple[str, ...]:
    """Load the deterministic discovered-route manifest when present."""

    path = run_dir / "raw" / "katana" / "discovered-routes.txt"
    if not path.is_file():
        return ()
    return tuple(
        line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def _extract_discovered_url(payload: dict[str, object]) -> str | None:
    request = payload.get("request")
    if isinstance(request, dict):
        for key in ("endpoint", "url"):
            value = request.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    value = payload.get("url")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
