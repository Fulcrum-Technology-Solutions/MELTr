"""Version comparison utilities for template updates."""

import re


def compare_versions(version1: str | None, version2: str | None) -> int:
    """Compare two semantic version strings.

    Args:
        version1: First version string (e.g., "1.0.0")
        version2: Second version string (e.g., "1.0.1")

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2

    Raises:
        ValueError: If version strings are invalid
    """
    if version1 is None:
        version1 = "0.0.0"
    if version2 is None:
        version2 = "0.0.0"

    v1_parts = _parse_version(version1)
    v2_parts = _parse_version(version2)

    for v1_part, v2_part in zip(v1_parts, v2_parts, strict=False):
        if v1_part < v2_part:
            return -1
        elif v1_part > v2_part:
            return 1

    return 0


def _parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse semantic version string into (major, minor, patch) tuple.

    Args:
        version_str: Version string (e.g., "1.2.3" or "1.2")

    Returns:
        Tuple of (major, minor, patch) integers

    Raises:
        ValueError: If version string is invalid
    """
    # Remove leading/trailing whitespace
    version_str = version_str.strip()

    # Extract version numbers (handle formats like "1.0.0", "1.0", "v1.2.3")
    match = re.match(r"^v?(\d+)(?:\.(\d+)(?:\.(\d+))?)?", version_str)
    if not match:
        raise ValueError(f"Invalid version string: {version_str}")

    major = int(match.group(1))
    minor = int(match.group(2)) if match.group(2) else 0
    patch = int(match.group(3)) if match.group(3) else 0

    return (major, minor, patch)


def is_update_available(local_version: str | None, remote_version: str | None) -> bool:
    """Check if remote version is newer than local version.

    Args:
        local_version: Local version string
        remote_version: Remote version string

    Returns:
        True if remote version is newer
    """
    return compare_versions(local_version, remote_version) < 0


def format_version_status(local_version: str | None, remote_version: str | None) -> str:
    """Format version status for display.

    Args:
        local_version: Local version string
        remote_version: Remote version string

    Returns:
        Status string like "1.0.0 → 1.0.1" or "Up to date"
    """
    if not local_version:
        local_version = "not installed"

    if not remote_version:
        return f"{local_version} (remote version unknown)"

    comparison = compare_versions(local_version, remote_version)

    if comparison < 0:
        return f"{local_version} → {remote_version} (update available)"
    elif comparison > 0:
        return f"{local_version} (local is newer than remote {remote_version})"
    else:
        return f"{local_version} (up to date)"
