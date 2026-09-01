"""Tests for operator PATH helpers."""

from pathlib import Path

import pytest

from meltr.cli.path_helpers import (
    profile_d_contents,
    usr_local_wrapper_contents,
    write_operator_path_helpers,
)


def _fake_install(tmp_path: Path) -> Path:
    root = tmp_path / "opt" / "meltr"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "meltr").write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    (root / "bin" / "meltr").chmod(0o755)
    return root


def test_profile_d_contents_uses_install_bin(tmp_path):
    root = _fake_install(tmp_path)
    text = profile_d_contents(root)
    assert f'export PATH="{root.resolve()}/bin:${{PATH}}"' in text


def test_usr_local_wrapper_execs_facade(tmp_path):
    root = _fake_install(tmp_path)
    text = usr_local_wrapper_contents(root)
    assert f'exec "{root.resolve()}/bin/meltr" "$@"' in text


def test_write_operator_path_helpers(tmp_path):
    root = _fake_install(tmp_path)
    profile = tmp_path / "etc" / "profile.d" / "meltr.sh"
    wrapper = tmp_path / "usr" / "local" / "bin" / "meltr"
    got_profile, got_wrapper = write_operator_path_helpers(
        root, profile_d_path=profile, wrapper_path=wrapper
    )
    assert got_profile == profile
    assert got_wrapper == wrapper
    assert profile.read_text(encoding="utf-8") == profile_d_contents(root)
    assert wrapper.read_text(encoding="utf-8") == usr_local_wrapper_contents(root)
    assert wrapper.stat().st_mode & 0o111


def test_write_operator_path_helpers_requires_facade(tmp_path):
    root = tmp_path / "opt" / "meltr"
    root.mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="Operator facade"):
        write_operator_path_helpers(
            root,
            profile_d_path=tmp_path / "p.sh",
            wrapper_path=tmp_path / "w",
        )
