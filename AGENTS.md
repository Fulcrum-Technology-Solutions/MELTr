# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

LogForge is a single-package Python application (FastAPI + Typer CLI) for synthetic log generation. No external services, databases, or Docker are required. All state is stored in YAML files under `LOGFORGE_HOME` (defaults to `~/.logforge`).

### Development setup

See `README.md` "Development / from source" section. The standard workflow is:

```
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

The venv must be activated (`source /workspace/.venv/bin/activate`) before running any commands.

### Running the application

```bash
logforge init --force   # Initialize ~/.logforge (config.yaml, entities.yaml, dirs)
logforge start          # Start FastAPI server on 127.0.0.1:8080 (foreground)
```

### Key commands (see README.md for full list)

| Task | Command |
|------|---------|
| Lint | `ruff check .` |
| Format check | `black --check .` |
| Type check | `mypy src` |
| Tests | `pytest` |
| Start service | `logforge start` |

### Non-obvious caveats

- `pytest` exits non-zero even when all tests pass because `--cov-fail-under=80` is configured in `pyproject.toml` and current coverage is ~24%. All 48 tests do pass.
- `python3.12-venv` system package must be installed for `python3 -m venv` to work (not pre-installed on Ubuntu 24.04 minimal).
- The entity import API (`POST /api/entities/import`) expects a JSON body with the full entity schema (organization, users, devices, services), not a file path. Users require `full_name`, devices require `ip_address` and `mac_address`, services require `port` and `protocol`.
- `ruff`, `black`, and `mypy` all report pre-existing issues in the codebase — this is expected.
- The `logforge start` command runs in the foreground; background it with `&` for non-interactive use.
