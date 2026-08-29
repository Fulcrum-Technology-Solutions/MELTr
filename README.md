# MELTr

MELTr is a synthetic event log generator for SOC, DFIR, and platform teams who need realistic data to test pipelines, detections, and integrations.

> **Formerly LogForge OSS.** The engine lives here now. Community templates still sync from [logforge.io](https://logforge.io) during the transition; other LogForge repos will migrate later.

## Features

- FastAPI management plane + Typer CLI (`meltr`)
- Jinja2 templates with Faker + entity registry
- Community template install (`default/` / `custom/`)
- Pluggable outputs: file, console, HTTP, TCP, syslog
- Prometheus metrics and resilient output buffering

## Install

### From source (development)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
meltr init --force
meltr start --foreground
```

### PyPI (coming with v2.0)

```bash
pip install meltr
```

The `logforge` name was taken on PyPI; **`meltr` is the published package name**.

## Quick start

```bash
export MELTR_HOME=~/.meltr   # optional; defaults to ~/.meltr
meltr init --force
meltr templates browse
meltr generators list
meltr start                  # daemon on POSIX; use --foreground / -f to stay attached
```

Compat: `LOGFORGE_HOME` and `LOGFORGE_API_KEY` still work if `MELTR_*` is unset. The `logforge` CLI entry point is a temporary alias for `meltr`.

## Environment

| Variable | Purpose |
|----------|---------|
| `MELTR_HOME` | Config/data root (default `~/.meltr`) |
| `MELTR_API_URL` | Management API base URL |
| `MELTR_API_KEY` | Bearer token when API auth is enabled |
| `MELTR_TELEMETRY` | Set `0` / `false` to disable telemetry |

## Docs

- [Development setup](docs/development/setup.md)
- [Linux tarball deployment](docs/deployment/linux-tarball.md)
- [v2.0 completion plan](docs/superpowers/plans/2026-08-29-meltr-v2-completion.md)

## License

Apache-2.0
