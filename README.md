# MELTr

MELTr is a synthetic event log generator for SOC, DFIR, and platform teams who need realistic data to test detections and integrations.

> **Formerly LogForge OSS.** The engine lives here now. Community templates still sync from [logforge.io](https://logforge.io) during the transition; other LogForge repos will migrate later.

## Features

- FastAPI management plane + Typer CLI (`meltr`)
- Jinja2 templates with Faker + entity registry
- Community template install (`default/` / `custom/`)
- Pluggable outputs: file, console, HTTP, TCP, syslog
- Prometheus metrics and resilient output buffering
- Multiple **generators** (one template → one or more outputs); optional schedule gates (`continuous`, `window`, `burst`)

## Generators

Each **generator** renders one template and sends events to one or more **outputs**. Run multiple generators when you need multiple templates.

```yaml
generators:
  - name: identity-lab
    template: vendor/product/source/event
    enabled: true
    outputs: [file-out, http-cribl]
    # schedule omitted → continuous (default)
```

```bash
meltr generators list
meltr generators start identity-lab
meltr generators status identity-lab
meltr generators stop identity-lab
```

Configure under `generators:` in `config.yaml`, or use `meltr config edit` for an interactive flow. A reserved **`internal-logs`** generator forwards application logs (not a Jinja template); it is always present and cannot be removed.

## Schedule (optional)

Generators run **continuously** by default. Add an optional `schedule` block to gate emission — frequency/variation still controls rate; the schedule decides whether emission is allowed.

| Mode | Behavior |
|------|----------|
| `continuous` | Emit whenever started (default) |
| `window` | Emit only inside tz-aware `days` + `time`; stay running but emit zero outside the window |
| `burst` | Emit until `count` events **or** `duration`, then auto-stop |

Example:

```yaml
generators:
  - name: business-hours
    template: vendor/product/source/event
    enabled: true
    outputs: [file-out]
    schedule:
      mode: window
      days: [mon, tue, wed, thu, fri]
      time: "09:00-17:00"
      timezone: America/New_York
```

## Install

### From source (development)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
meltr init --force
meltr start --foreground
```

### PyPI

```bash
pip install meltr
meltr init --force
meltr start --foreground
```

Requires **Python ≥3.10**. The `logforge` name was taken on PyPI; **`meltr` is the published package name**. Pre-release builds may be tagged `v2.0.0a*` before the stable v2.0.0 release.

## Quick start

```bash
export MELTR_HOME=~/.meltr   # optional; defaults to ~/.meltr
meltr init --force
meltr templates browse
meltr generators list
meltr start                  # daemon on POSIX; use --foreground / -f to stay attached
```

Compat: `LOGFORGE_HOME` and `LOGFORGE_API_KEY` still work if `MELTR_*` is unset. The `logforge` CLI entry point is a temporary alias for `meltr`.

## Templates: preview and updates

Preview renders sample events **without** starting generators (service must be running for CLI; API works standalone):

```bash
meltr start --foreground          # or daemonized: meltr start
meltr templates preview testvendor/testproduct/events/preview --count 3
# API: POST /api/templates/{id}/preview  {"count": 3}
```

Check installed community packages against the registry ([logforge.io](https://logforge.io) by default):

```bash
meltr templates check-updates
# API: GET /api/community/updates
```

Registry errors exit non-zero from the CLI and return 502 from the API — local installs are never modified.

## What's not in OSS

MELTr is the **single-node** open-source product. These capabilities live in **LogForge Enterprise** (or a future MELTr Enterprise) only:

- Distributed **worker fleet** and leader–worker job dispatch
- **LLM-assisted** template authoring in the web UI
- Postgres-backed manager and multi-tenant UI

See [ecosystem glossary](docs/ecosystem-glossary.md) for shared terminology.

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

- [Ecosystem glossary](docs/ecosystem-glossary.md)
- [HTTP destination presets (Cribl / Splunk HEC)](docs/deployment/destination-presets.md)
- [Development setup](docs/development/setup.md)
- [Linux tarball deployment](docs/deployment/linux-tarball.md)
- [v2.0 completion plan](docs/superpowers/plans/2026-08-29-meltr-v2-completion.md)
- [v2.0.0 release notes](docs/release-notes-2.0.0.md)

## Development

```bash
pytest   # requires MELTR_HOME (temp dir is fine); coverage gate is 50% on full src/meltr (no whole-file omits)
```

Phase 6 ships with **interim honest coverage (~50%)**; tracked follow-up is **≥60% without omits** (see [release notes](docs/release-notes-2.0.0.md)).

## License

Apache-2.0
