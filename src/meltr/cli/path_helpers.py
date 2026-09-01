"""Operator PATH helpers (profile.d + /usr/local/bin wrapper)."""

from __future__ import annotations

from pathlib import Path


def profile_d_contents(install_root: Path) -> str:
    """Shell snippet that prepends ``<install_root>/bin`` to PATH."""
    root = install_root.resolve()
    return f'export PATH="{root}/bin:${{PATH}}"\n'


def usr_local_wrapper_contents(install_root: Path) -> str:
    """Thin wrapper that execs the product façade at ``<install_root>/bin/meltr``."""
    root = install_root.resolve()
    facade = root / "bin" / "meltr"
    return f"""#!/bin/sh
exec "{facade}" "$@"
"""


def write_operator_path_helpers(
    install_root: Path,
    *,
    profile_d_path: Path | None = None,
    wrapper_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write ``/etc/profile.d/meltr.sh`` and ``/usr/local/bin/meltr`` (idempotent).

    Paths are overridable for tests. Returns ``(profile_d_path, wrapper_path)``.
    """
    root = install_root.resolve()
    facade = root / "bin" / "meltr"
    if not facade.is_file():
        raise FileNotFoundError(
            f"Operator facade not found at {facade}; unpack the official tarball or skip PATH helpers"
        )

    profile = profile_d_path if profile_d_path is not None else Path("/etc/profile.d/meltr.sh")
    wrapper = wrapper_path if wrapper_path is not None else Path("/usr/local/bin/meltr")

    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(profile_d_contents(root), encoding="utf-8")

    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(usr_local_wrapper_contents(root), encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | 0o111)

    return profile, wrapper
