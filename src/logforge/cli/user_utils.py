"""Shared helpers for service user/group creation (init and service install)."""

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional, Tuple

try:
    import grp
    import pwd
except ImportError:
    grp = None
    pwd = None


def ensure_service_user_and_group(
    service_user: str,
    service_group: str,
    home_path: Path,
    create_user: bool,
    *,
    on_user_created: Optional[Callable[[str], None]] = None,
    on_group_created: Optional[Callable[[str], None]] = None,
    on_user_exists: Optional[Callable[[str], None]] = None,
    on_no_pwd_grp: Optional[Callable[[], None]] = None,
    on_useradd_missing: Optional[Callable[[], None]] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """Create service user/group if requested and they don't exist; return (uid, gid).

    Args:
        service_user: Username to create or use.
        service_group: Group name to create or use.
        home_path: Home directory for the user (used with useradd -d).
        create_user: If True, run useradd/groupadd when user/group don't exist.
        on_user_created: Optional callback(message) when user is created.
        on_group_created: Optional callback(message) when group is created.
        on_user_exists: Optional callback(message) when user already exists.
        on_no_pwd_grp: Optional callback() when pwd/grp not available.
        on_useradd_missing: Optional callback() when useradd/groupadd not found.

    Returns:
        (uid, gid) for the service user. (0, 0) or (None, None) on failure/fallback.
    """
    if pwd is None or grp is None:
        if on_no_pwd_grp:
            on_no_pwd_grp()
        return (0, 0)

    if create_user:
        try:
            try:
                pwd.getpwnam(service_user)
                if on_user_exists:
                    on_user_exists(f"User {service_user} already exists")
            except KeyError:
                try:
                    subprocess.run(
                        [
                            'useradd',
                            '-r',
                            '-s', '/bin/false',
                            '-d', str(home_path),
                            '-c', 'LogForge Service',
                            service_user,
                        ],
                        check=True,
                        capture_output=True,
                    )
                    if on_user_created:
                        on_user_created(f"Created service user: {service_user}")
                except subprocess.CalledProcessError as e:
                    if on_user_created:
                        on_user_created(f"Could not create user {service_user}: {e}")
                except FileNotFoundError:
                    if on_useradd_missing:
                        on_useradd_missing()

            try:
                grp.getgrnam(service_group)
            except KeyError:
                try:
                    subprocess.run(
                        ['groupadd', '-r', service_group],
                        check=True,
                        capture_output=True,
                    )
                    if on_group_created:
                        on_group_created(f"Created service group: {service_group}")
                except subprocess.CalledProcessError:
                    pass
                except FileNotFoundError:
                    if on_useradd_missing:
                        on_useradd_missing()
        except FileNotFoundError:
            if on_useradd_missing:
                on_useradd_missing()

    try:
        uid = pwd.getpwnam(service_user).pw_uid
        try:
            gid = grp.getgrnam(service_group).gr_gid
        except KeyError:
            gid = pwd.getpwnam(service_user).pw_gid
        return (uid, gid)
    except KeyError:
        return (0, 0)


def service_user_and_group_exist(service_user: str, service_group: str) -> bool:
    """Return True if both the service user and group exist (no root needed to init)."""
    if pwd is None or grp is None:
        return False
    try:
        pwd.getpwnam(service_user)
        grp.getgrnam(service_group)
        return True
    except KeyError:
        return False


def check_root() -> bool:
    """Return True if running as root (euid 0)."""
    try:
        return os.geteuid() == 0
    except (AttributeError, OSError):
        return False
