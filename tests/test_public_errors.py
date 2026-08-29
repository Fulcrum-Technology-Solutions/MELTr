"""Tests for client-safe API error helpers."""

from meltr.utils.public_errors import public_failure_message, sanitize_stored_error


def test_public_failure_message() -> None:
    assert public_failure_message("Restart generator") == "Restart generator failed"


def test_sanitize_stored_error_none() -> None:
    assert sanitize_stored_error(None) is None


def test_sanitize_stored_error_redacts_internal_text() -> None:
    internal = "FileNotFoundError: /home/user/.logforge/templates/secret.j2"
    assert sanitize_stored_error(internal) == "An error occurred"
