"""Config editor --section save prompt behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from meltr.cli import config_editor as ce
from meltr.core.config import create_default_config


def test_section_edit_offers_save(tmp_path: Path):
    config = create_default_config(tmp_path)

    with (
        patch.object(ce, "load_config", return_value=config),
        patch.object(ce, "_edit_outputs_section", side_effect=lambda c: c) as edit,
        patch.object(ce, "_save_config", return_value=True) as save,
        patch.object(ce.Confirm, "ask", return_value=True) as confirm,
    ):
        ce.config_editor(section="outputs", edit_existing=True)

    edit.assert_called_once()
    confirm.assert_called_once_with("\nSave changes?", default=True)
    save.assert_called_once_with(config)


def test_section_edit_skips_save_when_declined(tmp_path: Path):
    config = create_default_config(tmp_path)

    with (
        patch.object(ce, "load_config", return_value=config),
        patch.object(ce, "_edit_outputs_section", side_effect=lambda c: c),
        patch.object(ce, "_save_config", return_value=True) as save,
        patch.object(ce.Confirm, "ask", return_value=False),
    ):
        ce.config_editor(section="outputs", edit_existing=True)

    save.assert_not_called()
