"""Helpers for masking secrets in logs and user-facing error messages."""

from collections.abc import Iterable

REDACTED_MARKER = "<redacted>"


def redact_secret(value: str | None, *, visible_prefix: int = 2, visible_suffix: int = 2) -> str:
    """Return a masked representation of a secret value."""

    if value is None:
        return REDACTED_MARKER

    stripped = value.strip()
    if not stripped:
        return REDACTED_MARKER

    if len(stripped) <= visible_prefix + visible_suffix:
        return REDACTED_MARKER

    return (
        f"{stripped[:visible_prefix]}"
        f"{REDACTED_MARKER}"
        f"{stripped[-visible_suffix:]}"
    )


def redact_known_secrets(text: str, secrets: Iterable[str | None]) -> str:
    """Replace any known secret values found in text with redacted markers."""

    redacted_text = text
    for secret in secrets:
        if secret is None:
            continue
        stripped = secret.strip()
        if not stripped:
            continue
        redacted_text = redacted_text.replace(stripped, redact_secret(stripped))
    return redacted_text
