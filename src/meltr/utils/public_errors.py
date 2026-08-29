"""Client-safe error messages for API and status responses."""


def public_failure_message(action: str) -> str:
    """Return a generic failure message safe to expose over HTTP."""
    return f"{action} failed"


def sanitize_stored_error(error: str | None) -> str | None:
    """Redact internal exception text from persisted status fields."""
    if error is None:
        return None
    return "An error occurred"
