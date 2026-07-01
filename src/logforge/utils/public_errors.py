"""Client-safe error messages for API and status responses."""

from typing import Optional


def public_failure_message(action: str) -> str:
    """Return a generic failure message safe to expose over HTTP."""
    return f"{action} failed"


def sanitize_stored_error(error: Optional[str]) -> Optional[str]:
    """Redact internal exception text from persisted status fields."""
    if error is None:
        return None
    return "An error occurred"
