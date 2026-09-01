"""Sanity checks for tarball launcher snippets in the build script."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = (ROOT / "scripts" / "build_linux_tgz.sh").read_text(encoding="utf-8")


def test_build_script_launcher_is_symlink_safe():
    assert 'SCRIPT="$(readlink -f "$0")"' in BUILD
    assert 'ROOT="$(cd "$(dirname "$SCRIPT")/../.." && pwd)"' in BUILD


def test_build_script_emits_facade_and_install_sh():
    assert "OUT_ROOT/bin/meltr" in BUILD or '"$OUT_ROOT/bin/meltr"' in BUILD
    assert "install.sh" in BUILD
    assert "/etc/profile.d/meltr.sh" in BUILD
    assert "/usr/local/bin/meltr" in BUILD
