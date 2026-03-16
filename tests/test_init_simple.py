"""Simple test to verify init command structure."""

from typer.testing import CliRunner

from logforge.cli.main import app


def test_init_command_exists():
    """Test that init command is accessible."""
    runner = CliRunner()
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout.lower() or "Initialize" in result.stdout or "directory" in result.stdout









