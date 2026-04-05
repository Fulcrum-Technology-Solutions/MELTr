"""Simple test to verify init command structure."""

from typer.testing import CliRunner

from logforge.cli.main import app


def test_init_command_exists():
    """Test that init command is accessible."""
    runner = CliRunner()
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout.lower() or "Initialize" in result.stdout or "directory" in result.stdout


def test_templates_install_supports_non_interactive_flags_for_common_actions():
    """Install/update subcommands expose flags for scripting (Task 8 parity)."""
    runner = CliRunner()
    r = runner.invoke(app, ["templates", "install", "--help"])
    assert r.exit_code == 0
    for flag in ("--vendor", "--product", "--overwrite", "--list-vendors", "--json", "--yes", "-y"):
        assert flag in r.stdout
    r2 = runner.invoke(app, ["templates", "install"])
    assert r2.exit_code == 1

    ru = runner.invoke(app, ["templates", "update", "--help"])
    assert ru.exit_code == 0
    assert "--yes" in ru.stdout and "-y" in ru.stdout









