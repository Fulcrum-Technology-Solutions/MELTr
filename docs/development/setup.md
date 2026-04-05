# Development environment

Use this guide to run LogForge from a **source checkout**. Production installs that mirror a Cribl-style layout use the **official Linux `.tar.gz`** from [GitHub Releases](https://github.com/Fulcrum-Technology-Solutions/LogForge/releases); see [linux-tarball.md](../deployment/linux-tarball.md).

## Requirements

- **Python:** `>=3.9` (see `requires-python` in [`pyproject.toml`](../../pyproject.toml)).
- **Git** for cloning the repository.

## Runtime dependencies

Declared under `[project.dependencies]` in [`pyproject.toml`](../../pyproject.toml):

| Package | Purpose (summary) |
|---------|---------------------|
| jinja2 | Templates |
| pyyaml | Config / entities |
| typer | CLI |
| requests | HTTP client |
| python-dateutil | Date handling |
| fastapi | API server |
| uvicorn | ASGI server |
| prometheus-client | Metrics |
| pydantic | Models |
| faker | Synthetic data |
| rich | Terminal UI |
| psutil | System info |

Exact version constraints are in `pyproject.toml`.

## Development (optional) dependencies

`[project.optional-dependencies] dev` adds tooling used for tests and quality checks, including:

- **pytest**, **pytest-cov**, **pytest-asyncio**, **pytest-mock**
- **black**, **ruff**, **mypy**
- **httpx**, **jsonschema**
- **pip-licenses** (also used when building the Linux release bundle)

## Recommended setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

This performs an **editable install** of LogForge and installs runtime + dev dependencies.

**Alternative (uv):** `uv pip install -e ".[dev]"` after creating a venv with `uv venv`, if you use [uv](https://github.com/astral-sh/uv).

## Tests

```bash
pytest              # full suite
pytest -k tcp       # focused subset
```

## Formatting and linting

```bash
ruff check .
black .
mypy src
```

Align with `[tool.ruff]`, `[tool.black]`, and `[tool.mypy]` in [`pyproject.toml`](../../pyproject.toml).

## Building the Linux release bundle

Maintainers building **`logforge-*-linux-x86_64.tar.gz`** should read [building-linux-tarball.md](building-linux-tarball.md) (Linux x86_64 host or CI).

## See also

- [README.md](../../README.md) — overview and CLI examples
- [README: Directory layout](../../README.md#development) — source tree summary
