"""Tests for path resolution."""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from meltr.core.paths import (
    default_application_log_file,
    get_config_path,
    get_data_home_from_install_binary,
    get_entities_path,
    get_install_root_from_binary,
    get_logforge_home,
    get_templates_path,
    validate_path_within_home,
)


def test_get_logforge_home_from_env():
    """Test MELTR_HOME resolution from environment variable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"MELTR_HOME": tmpdir}, clear=False):
            home = get_logforge_home()
            assert home == Path(tmpdir).resolve()
            assert home.exists()


def test_get_logforge_home_local_directory(tmp_path, monkeypatch):
    """Test MELTR_HOME resolution from local ./logforge directory (backward compat)."""
    logforge_dir = tmp_path / "logforge"
    logforge_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MELTR_HOME", raising=False)
    monkeypatch.delenv("LOGFORGE_HOME", raising=False)
    home = get_logforge_home()
    assert home == logforge_dir.resolve()


def test_get_logforge_home_prefers_dot_logforge(tmp_path, monkeypatch):
    """Test that ./.logforge is preferred over ./logforge when both exist."""
    dot_meltr = tmp_path / ".logforge"
    logforge_dir = tmp_path / "logforge"
    dot_meltr.mkdir()
    logforge_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MELTR_HOME", raising=False)
    monkeypatch.delenv("LOGFORGE_HOME", raising=False)
    home = get_logforge_home()
    assert home == dot_meltr.resolve()


def test_get_logforge_home_service_account_uses_opt_without_bundle(tmp_path, monkeypatch):
    """Service accounts fall back to /opt/meltr when bundle layout cannot be resolved."""
    from meltr.core import paths as paths_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MELTR_HOME", raising=False)
    monkeypatch.delenv("LOGFORGE_HOME", raising=False)
    with patch("os.getuid", return_value=999):
        with patch.object(shutil, "which", return_value=None):
            with patch.object(paths_module, "_ensure_directory"):
                home = get_logforge_home()
    assert home == Path("/opt/meltr")


def test_get_data_home_from_install_binary_opt_layout(tmp_path):
    """Tar-style layout: …/opt/meltr/app/bin/meltr → …/opt/meltr/data."""
    bindir = tmp_path / "opt" / "logforge" / "app" / "bin"
    bindir.mkdir(parents=True)
    binfile = bindir / "logforge"
    binfile.write_bytes(b"")
    data = tmp_path / "opt" / "logforge" / "data"
    data.mkdir()
    assert get_data_home_from_install_binary(binfile) == data.resolve()


def test_get_install_root_from_binary_opt_layout(tmp_path):
    bindir = tmp_path / "opt" / "logforge" / "app" / "bin"
    bindir.mkdir(parents=True)
    binfile = bindir / "logforge"
    binfile.write_bytes(b"")
    (tmp_path / "opt" / "logforge" / "data").mkdir(parents=True, exist_ok=True)
    expect_root = (tmp_path / "opt" / "logforge").resolve()
    assert get_install_root_from_binary(binfile) == expect_root


def test_default_application_log_file_uses_install_logs(tmp_path):
    bindir = tmp_path / "opt" / "logforge" / "app" / "bin"
    bindir.mkdir(parents=True)
    binfile = bindir / "logforge"
    binfile.write_bytes(b"")
    (tmp_path / "opt" / "logforge" / "data").mkdir(parents=True, exist_ok=True)
    expect = (tmp_path / "opt" / "logforge" / "logs" / "meltr.log").resolve()
    assert default_application_log_file(binfile) == expect


def test_get_logforge_home_service_account_prefers_opt_install_root(tmp_path, monkeypatch):
    """Low-uid user uses …/opt/meltr (product root) when `which` finds that bundle binary."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MELTR_HOME", raising=False)
    monkeypatch.delenv("LOGFORGE_HOME", raising=False)
    bindir = tmp_path / "opt" / "logforge" / "app" / "bin"
    bindir.mkdir(parents=True)
    binfile = bindir / "logforge"
    binfile.write_bytes(b"")
    (tmp_path / "opt" / "logforge" / "data").mkdir(parents=True, exist_ok=True)
    with patch("os.getuid", return_value=999):
        with patch.object(shutil, "which", return_value=str(binfile)):
            home = get_logforge_home()
    assert home == (tmp_path / "opt" / "logforge").resolve()


def test_get_logforge_home_uses_argv0_when_which_missing(tmp_path, monkeypatch):
    """Bundle home resolves from sys.argv[0] when meltr is not on PATH (e.g. sudo)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MELTR_HOME", raising=False)
    monkeypatch.delenv("LOGFORGE_HOME", raising=False)
    bindir = tmp_path / "opt" / "logforge" / "app" / "bin"
    bindir.mkdir(parents=True)
    binfile = bindir / "logforge"
    binfile.write_bytes(b"")
    (tmp_path / "opt" / "logforge" / "data").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "argv", [str(binfile), "init"])
    with patch("os.getuid", return_value=1000):
        with patch.object(shutil, "which", return_value=None):
            home = get_logforge_home()
    assert home == (tmp_path / "opt" / "logforge").resolve()


def test_default_application_log_file_uses_argv0_when_which_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bindir = tmp_path / "opt" / "logforge" / "app" / "bin"
    bindir.mkdir(parents=True)
    binfile = bindir / "logforge"
    binfile.write_bytes(b"")
    (tmp_path / "opt" / "logforge" / "data").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "argv", [str(binfile), "init"])
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    expect = (tmp_path / "opt" / "logforge" / "logs" / "meltr.log").resolve()
    assert default_application_log_file() == expect


def test_get_logforge_home_default(monkeypatch):
    """Test default MELTR_HOME resolution when no env or local dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("HOME", tmpdir)
        monkeypatch.delenv("MELTR_HOME", raising=False)
        monkeypatch.delenv("LOGFORGE_HOME", raising=False)
        monkeypatch.chdir(tmpdir)
        with patch("os.getuid", return_value=1000):
            with patch.object(shutil, "which", return_value=None):
                home = get_logforge_home()
        assert home == Path(tmpdir) / ".meltr"


def test_get_config_path():
    """Test config path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        config_path = get_config_path(home)
        assert config_path == home / "config.yaml"


def test_get_entities_path():
    """Test entities path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        entities_path = get_entities_path(home)
        assert entities_path == home / "entities.yaml"


def test_get_templates_path():
    """Test templates path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        templates_path = get_templates_path(home)
        assert templates_path == home / "templates"


def test_validate_path_within_home():
    """Test path validation within MELTR_HOME."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)

        # Valid paths
        assert validate_path_within_home(home / "config.yaml", home) is True
        assert validate_path_within_home(home / "templates" / "default", home) is True

        # Invalid paths
        assert validate_path_within_home(Path("/etc/passwd"), home) is False
        assert validate_path_within_home(Path("/tmp"), home) is False
