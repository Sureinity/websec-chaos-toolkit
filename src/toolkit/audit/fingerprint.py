"""HTTPX-backed preflight fingerprinting for URL-first audit."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True, frozen=True)
class RedirectHop:
    """One redirect hop observed during URL fingerprinting."""

    url: str
    status_code: int


@dataclass(slots=True, frozen=True)
class TlsFingerprint:
    """Basic TLS metadata captured by the HTTPX preflight stage."""

    enabled: bool
    http_version: str | None = None
    strict_transport_security: str | None = None


@dataclass(slots=True, frozen=True)
class HttpxFingerprint:
    """Structured preflight fingerprint for one URL-first audit target."""

    requested_url: str
    final_url: str
    reachable: bool
    status_code: int | None
    redirect_chain: tuple[RedirectHop, ...]
    title: str | None
    server: str | None
    technology_hints: tuple[str, ...]
    tls: TlsFingerprint | None = None


class AuditFingerprintError(RuntimeError):
    """Raised when HTTPX preflight fingerprinting cannot complete safely."""


def capture_httpx_fingerprint(
    url: str,
    *,
    timeout_seconds: float = 5.0,
) -> HttpxFingerprint:
    """Capture one deterministic fingerprint for a URL-first audit target."""

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise AuditFingerprintError(f"HTTPX fingerprinting failed for {url}: {exc}") from exc

    headers = response.headers
    technology_hints = tuple(
        f"{name}: {headers[name]}"
        for name in ("server", "x-powered-by", "x-generator", "via")
        if name in headers and headers[name].strip()
    )

    tls = None
    if response.url.scheme == "https":
        tls = TlsFingerprint(
            enabled=True,
            http_version=response.http_version or None,
            strict_transport_security=headers.get("strict-transport-security"),
        )

    return HttpxFingerprint(
        requested_url=url,
        final_url=str(response.url),
        reachable=True,
        status_code=response.status_code,
        redirect_chain=tuple(
            RedirectHop(url=str(item.url), status_code=item.status_code)
            for item in response.history
        ),
        title=_extract_title(response.text),
        server=headers.get("server"),
        technology_hints=technology_hints,
        tls=tls,
    )


def fingerprint_artifact_path(raw_dir: Path) -> Path:
    """Return the canonical HTTPX fingerprint artifact path for one run."""

    return raw_dir / "httpx" / "fingerprint.json"


def write_httpx_fingerprint(raw_dir: Path, fingerprint: HttpxFingerprint) -> Path:
    """Write the structured HTTPX fingerprint artifact to raw output."""

    path = fingerprint_artifact_path(raw_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(fingerprint), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_httpx_fingerprint(run_dir: Path) -> HttpxFingerprint | None:
    """Load the HTTPX fingerprint artifact when present for report enrichment."""

    path = run_dir / "raw" / "httpx" / "fingerprint.json"
    if not path.is_file():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    tls_payload = payload.get("tls")
    tls = None
    if isinstance(tls_payload, dict):
        tls = TlsFingerprint(**tls_payload)

    return HttpxFingerprint(
        requested_url=payload["requested_url"],
        final_url=payload["final_url"],
        reachable=payload["reachable"],
        status_code=payload["status_code"],
        redirect_chain=tuple(RedirectHop(**item) for item in payload.get("redirect_chain", ())),
        title=payload.get("title"),
        server=payload.get("server"),
        technology_hints=tuple(payload.get("technology_hints", ())),
        tls=tls,
    )


def _extract_title(body: str) -> str | None:
    match = _TITLE_RE.search(body)
    if match is None:
        return None
    collapsed = " ".join(match.group(1).split()).strip()
    return collapsed or None
