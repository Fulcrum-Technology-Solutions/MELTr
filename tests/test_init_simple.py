"""Simple test to verify init command structure."""

import re

from typer.testing import CliRunner

from meltr.cli.main import app

# Stable help rendering in CI/narrow terminals (Rich may split flag names across ANSI spans).
_HELP_ENV = {"COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}
_PLAIN_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _help_stdout(result) -> str:
    return _PLAIN_ANSI.sub("", result.stdout)


def test_init_command_exists():
    """Test that init command is accessible."""
    runner = CliRunner()
    result = runner.invoke(app, ["init", "--help"], env=_HELP_ENV)
    out = _help_stdout(result)
    assert result.exit_code == 0
    assert "init" in out.lower() or "Initialize" in out or "directory" in out


def test_templates_install_supports_non_interactive_flags_for_common_actions():
    """Install/update subcommands expose flags for scripting (Task 8 parity)."""
    runner = CliRunner()
    r = runner.invoke(app, ["templates", "install", "--help"], env=_HELP_ENV)
    assert r.exit_code == 0
    install_help = _help_stdout(r)
    for flag in ("--vendor", "--product", "--overwrite", "--list-vendors", "--json", "--yes", "-y"):
        assert flag in install_help
    r2 = runner.invoke(app, ["templates", "install"])
    assert r2.exit_code == 1

    ru = runner.invoke(app, ["templates", "update", "--help"], env=_HELP_ENV)
    assert ru.exit_code == 0
    update_help = _help_stdout(ru)
    assert "--yes" in update_help and "-y" in update_help
