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

## API authentication

Management routes require a Bearer token when authentication is active. **Key-implies-auth:** setting `MELTR_API_KEY` (or `LOGFORGE_API_KEY`) enables auth even if `api.auth.enabled` is false in config.

| Route | Auth required |
|-------|---------------|
| `GET /api/health` | No (public liveness) |
| All other `/api/*` routes | Yes, when auth is active |

Configure in `config.yaml`:

```yaml
api:
  auth:
    enabled: true   # requires a key at startup
    key: "your-secret"  # optional if MELTR_API_KEY is set
```

If `api.auth.enabled: true` and no key is configured (env or config), the API refuses to start. Send requests with `Authorization: Bearer <key>`.

## Environment

| Variable | Purpose |
|----------|---------|
| `MELTR_HOME` | Config/data root (default `~/.meltr`) |
| `MELTR_API_URL` | Management API base URL |
| `MELTR_API_KEY` | Bearer token when API auth is enabled |
| `MELTR_TELEMETRY` | Set `0` / `false` to disable telemetry |

## Publishing

PyPI releases use [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) — no long-lived API tokens in GitHub secrets.

- Create an empty **`meltr`** project on [pypi.org](https://pypi.org) (or claim it if reserved).
- In project settings → **Publishing**, add a Trusted Publisher: GitHub, org/repo **`Fulcrum-Technology-Solutions/MELTr`**, workflow **`publish-pypi.yml`**, environment **`pypi`**.
- In this repo, add a GitHub **environment** named `pypi` (Settings → Environments); optional protection rules for production releases.
- Push a tag matching `v*` (e.g. `v2.0.0a1`) or run **Publish to PyPI** manually via workflow dispatch after Trusted Publisher is linked.

## Docs

- [Development setup](docs/development/setup.md)
- [Linux tarball deployment](docs/deployment/linux-tarball.md)
- [v2.0 completion plan](docs/superpowers/plans/2026-08-29-meltr-v2-completion.md)

## License

Apache-2.0
