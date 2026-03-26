"""Core safety checks that can be reused across workflows."""

from collections.abc import Sequence

PRODUCTION_LIKE_ENVIRONMENTS = frozenset({"prod", "production", "live"})


def require_explicit_allowlist(values: Sequence[str], label: str) -> None:
    """Reject empty allowlists."""

    if not values:
        raise ValueError(f"{label} allowlist must not be empty.")


def refuse_production_like_environment(environment: str, allow_production: bool = False) -> None:
    """Refuse production-like targets unless explicitly allowed."""

    if environment.strip().lower() in PRODUCTION_LIKE_ENVIRONMENTS and not allow_production:
        raise ValueError("Production-like targets are refused by default.")
