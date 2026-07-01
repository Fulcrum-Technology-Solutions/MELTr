"""API error handling helpers."""

import logging

from logforge.utils.public_errors import public_failure_message


def log_api_exception(logger: logging.Logger, action: str, exc: BaseException) -> str:
    """Log the full exception server-side and return a safe client message."""
    logger.error("%s: %s", action, exc, exc_info=True)
    return public_failure_message(action)
