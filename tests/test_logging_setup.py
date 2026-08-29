"""Tests for application logging setup and precedence."""

import logging
from pathlib import Path
from unittest.mock import patch

from meltr.core.config import create_default_config
from meltr.utils.logging import setup_logging


def test_setup_logging_env_log_file_overrides_config(tmp_path, monkeypatch):
    """MELTR_LOG_FILE wins over config.logging.file."""
    monkeypatch.delenv("MELTR_LOG_FILE", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    override = tmp_path / "from_env.log"
    cfg_path = tmp_path / "from_config.log"
    monkeypatch.setenv("MELTR_LOG_FILE", str(override))

    cfg = create_default_config(home)
    cfg = cfg.model_copy(update={"logging": cfg.logging.model_copy(update={"file": str(cfg_path)})})
    setup_logging(cfg)

    root = logging.getLogger("meltr")
    paths = [Path(h.baseFilename) for h in root.handlers if hasattr(h, "baseFilename")]
    root.handlers.clear()

    assert override in paths
    assert cfg_path not in paths


def test_setup_logging_default_uses_default_application_log_file(tmp_path, monkeypatch):
    """Empty config logging.file uses default_application_log_file."""
    monkeypatch.delenv("MELTR_LOG_FILE", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    expect_log = (tmp_path / "opt" / "bundle" / "logs" / "meltr.log").resolve()

    cfg = create_default_config(home)
    cfg = cfg.model_copy(update={"logging": cfg.logging.model_copy(update={"file": None})})

    with patch("meltr.utils.logging.default_application_log_file", return_value=expect_log):
        setup_logging(cfg)

    root = logging.getLogger("meltr")
    written = [Path(h.baseFilename) for h in root.handlers if hasattr(h, "baseFilename")]
    root.handlers.clear()

    assert written == [expect_log]
