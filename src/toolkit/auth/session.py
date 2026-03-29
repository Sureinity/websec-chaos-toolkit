"""Authentication placeholder types.

The runtime auth contract is fixed before implementation:

- ``none`` resolves to explicit unauthenticated behavior
- ``bearer_token`` resolves only from ``token_env_var``
- ``cookie`` resolves only from ``cookie_name`` + ``cookie_value_env_var``
- ``session`` resolves only from ``session_header`` + ``session_value_env_var``
- ``form`` resolves credentials from env vars and performs direct HTTP login

All auth resolution is fail-closed. Missing env vars, blank env var values, and
unsupported SSO or MFA flows must fail explicitly. Secret values must never
appear in logs or exception strings.
"""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SessionSeed:
    """Minimal reference to externally supplied auth material.

    This placeholder remains intentionally narrow until the runtime auth layer
    is implemented in later checkpoints.
    """

    method: str
    secret_ref: str | None = None
