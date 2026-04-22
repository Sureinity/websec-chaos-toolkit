"""Katana-backed route discovery for URL-first audit."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from toolkit.auth.session import AuthSession, resolve_cookie_header
from toolkit.runtime.base import RuntimeBackend
from toolkit.runtime.models import RuntimeRequest

_DISCOVERED_URL_PATTERN = re.compile(r'"(?:endpoint|url)":"((?:\\.|[^"\\])*)"')
_STATIC_ASSET_EXTENSIONS = frozenset(
    {
        ".7z",
        ".avi",
        ".bmp",
        ".css",
        ".csv",
        ".doc",
        ".docx",
        ".eot",
        ".gif",
        ".gz",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".map",
        ".mp3",
        ".mp4",
        ".pdf",
        ".png",
        ".ppt",
        ".pptx",
        ".rar",
        ".svg",
        ".tar",
        ".tgz",
        ".ttf",
        ".txt",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".xls",
        ".xlsx",
        ".xml",
        ".zip",
    }
)
_HIGH_VALUE_ROUTE_HINTS = (
    "api",
    "graphql",
    "login",
    "register",
    "forgot-password",
    "reset-password",
    "contact",
    "report-problem",
    "account",
    "profile",
    "dashboard",
    "admin",
    "apply",
    "checkout",
    "payment",
    "wp-json",
    "xmlrpc",
)
_DEFAULT_ZAP_ROUTE_LIMIT = 8
_DEFAULT_NUCLEI_ROUTE_LIMIT = 8
_LOW_VALUE_NUCLEI_SEGMENTS = (
    "/feed",
    "/oembed/",
)
_LOW_VALUE_NUCLEI_FILENAMES = frozenset(
    {
        "load-scripts.php",
        "load-styles.php",
    }
)
_INVALID_ROUTE_CHARACTERS = frozenset({"'", '"', "`"})


@dataclass(slots=True, frozen=True)
class KatanaDiscoveryResult:
    """Discovery artifacts and deduplicated same-origin routes for one seed URL."""

    raw_output_path: Path
    route_manifest_path: Path
    routes: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class AuditTargetScope:
    """Curated discovery scope for downstream runtime-backed audit tools."""

    seed_url: str
    discovered_routes: tuple[str, ...]
    zap_routes: tuple[str, ...]
    nuclei_routes: tuple[str, ...]


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
    output_path.parent.mkdir(parents=True, exist_ok=True)
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

    headers = {
        name: f"{name}: {value}"
        for name, value in auth_session.headers.items()
        if name.lower() != "cookie"
    }
    cookie_header = resolve_cookie_header(auth_session)
    if cookie_header:
        headers["Cookie"] = f"Cookie: {cookie_header}"
    return headers


def _load_same_origin_routes(output_path: Path, *, seed_url: str) -> list[str]:
    seed = urlsplit(seed_url)
    same_origin: set[str] = {seed_url}

    for line in output_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        candidate = _extract_discovered_url_from_line(stripped)
        if candidate is None:
            continue
        parsed = urlsplit(candidate)
        if (
            parsed.scheme == seed.scheme
            and parsed.netloc == seed.netloc
            and _is_valid_discovered_route(candidate)
        ):
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


def plan_discovered_audit_scope(
    *,
    seed_url: str,
    discovered_routes: tuple[str, ...],
    zap_route_limit: int = _DEFAULT_ZAP_ROUTE_LIMIT,
    nuclei_route_limit: int = _DEFAULT_NUCLEI_ROUTE_LIMIT,
) -> AuditTargetScope:
    """Plan downstream audit tool scope from discovered same-origin routes.

    ZAP gets a curated subset so URL-first runs stay practical on medium sites.
    Nuclei gets a larger but still curated same-origin route set with static
    assets, noisy helper endpoints, and query variants removed so batched scans
    stay practical on medium sites.
    """

    normalized_routes = _deduplicate_routes(discovered_routes, seed_url=seed_url)
    zap_candidates = [route for route in normalized_routes if _is_zap_candidate(route)]
    nuclei_candidates = [route for route in normalized_routes if _is_nuclei_candidate(route)]
    zap_routes = _select_zap_routes(
        seed_url=seed_url,
        routes=tuple(zap_candidates),
        limit=zap_route_limit,
    )
    nuclei_routes = _select_nuclei_routes(
        seed_url=seed_url,
        routes=tuple(nuclei_candidates),
        limit=nuclei_route_limit,
    )

    return AuditTargetScope(
        seed_url=seed_url,
        discovered_routes=normalized_routes,
        zap_routes=zap_routes,
        nuclei_routes=nuclei_routes,
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


def _extract_discovered_url_from_line(line: str) -> str | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        match = _DISCOVERED_URL_PATTERN.search(line)
        if match is None:
            return None
        try:
            return json.loads(f'"{match.group(1)}"')
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    return _extract_discovered_url(payload)


def _deduplicate_routes(routes: tuple[str, ...], *, seed_url: str) -> tuple[str, ...]:
    canonical_to_route: dict[str, str] = {_canonical_route(seed_url): seed_url}
    for route in routes:
        if not _is_valid_discovered_route(route):
            continue
        canonical_to_route.setdefault(_canonical_route(route), route)

    ordered_routes = [seed_url]
    ordered_routes.extend(
        route
        for canonical, route in sorted(canonical_to_route.items(), key=lambda item: item[1])
        if canonical != _canonical_route(seed_url)
    )
    return tuple(ordered_routes)


def _canonical_route(route: str) -> str:
    parsed = urlsplit(route)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return parsed._replace(path=path, query=parsed.query, fragment="").geturl()


def _canonical_nuclei_route(route: str) -> str:
    parsed = urlsplit(route)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return parsed._replace(path=path, query="", fragment="").geturl()


def _is_valid_discovered_route(route: str) -> bool:
    if any(character in route for character in _INVALID_ROUTE_CHARACTERS):
        return False
    if any(character.isspace() for character in route):
        return False
    return True


def _is_zap_candidate(route: str) -> bool:
    parsed = urlsplit(route)
    path = parsed.path or "/"
    if path != "/" and "." in Path(path).name:
        suffix = Path(path).suffix.lower()
        if suffix in _STATIC_ASSET_EXTENSIONS:
            return False
    if parsed.query:
        return False
    if _is_low_value_helper_path(path):
        return False
    return True


def _is_nuclei_candidate(route: str) -> bool:
    parsed = urlsplit(route)
    path = parsed.path or "/"
    filename = Path(path.lower()).name
    if not _is_zap_candidate(route):
        return False
    if filename in _LOW_VALUE_NUCLEI_FILENAMES:
        return False
    return True


def _is_low_value_helper_path(path: str) -> bool:
    lowered = path.lower()
    if Path(lowered).name in _LOW_VALUE_NUCLEI_FILENAMES:
        return True
    return any(segment in lowered for segment in _LOW_VALUE_NUCLEI_SEGMENTS)


def _select_zap_routes(
    *,
    seed_url: str,
    routes: tuple[str, ...],
    limit: int,
) -> tuple[str, ...]:
    seed_canonical = _canonical_route(seed_url)
    ranked = tuple(
        route
        for _canonical, route in sorted(
            (
                (_canonical_route(route), route)
                for route in routes
                if _canonical_route(route) != seed_canonical
            ),
            key=lambda item: (
                _route_priority(item[1]),
                _route_depth(item[1]),
                len(item[1]),
                item[1],
            ),
        )
    )
    return _select_diversified_routes(seed_url=seed_url, ranked_routes=ranked, limit=limit)


def _select_nuclei_routes(
    *,
    seed_url: str,
    routes: tuple[str, ...],
    limit: int,
) -> tuple[str, ...]:
    seed_canonical = _canonical_nuclei_route(seed_url)
    normalized_routes: dict[str, str] = {seed_canonical: seed_url}
    for route in routes:
        normalized_routes.setdefault(_canonical_nuclei_route(route), _canonical_nuclei_route(route))

    ranked = tuple(
        route
        for _canonical, route in sorted(
            (
                (canonical, route)
                for canonical, route in normalized_routes.items()
                if canonical != seed_canonical
            ),
            key=lambda item: (
                _route_priority(item[1]),
                _route_depth(item[1]),
                len(item[1]),
                item[1],
            ),
        )
    )
    return _select_diversified_routes(seed_url=seed_url, ranked_routes=ranked, limit=limit)


def _select_diversified_routes(
    *,
    seed_url: str,
    ranked_routes: tuple[str, ...],
    limit: int,
) -> tuple[str, ...]:
    selected: list[str] = [seed_url]
    selected_families: set[str] = set()
    deferred: list[str] = []

    for route in ranked_routes:
        family = _route_family(route)
        if family in selected_families:
            deferred.append(route)
            continue
        selected.append(route)
        selected_families.add(family)
        if len(selected) >= max(1, limit):
            return tuple(selected)

    for route in deferred:
        if len(selected) >= max(1, limit):
            break
        selected.append(route)

    return tuple(selected)


def _route_family(route: str) -> str:
    path = urlsplit(route).path.strip("/")
    if not path:
        return "/"
    return path.split("/", 1)[0]


def _route_priority(route: str) -> int:
    lowered = route.lower()
    if any(hint in lowered for hint in _HIGH_VALUE_ROUTE_HINTS):
        return 0
    parsed = urlsplit(route)
    if (parsed.path or "/") == "/":
        return 0
    return 1


def _route_depth(route: str) -> int:
    path = urlsplit(route).path.strip("/")
    if not path:
        return 0
    return len([segment for segment in path.split("/") if segment])
