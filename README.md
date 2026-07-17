# LogForge OSS

LogForge is a synthetic event log generator designed for SOC engineers, DFIR analysts, and platform operators who need realistic data to test pipelines, detections, and integrations. The OSS edition delivers the core pipeline: a FastAPI management plane, a Typer-based CLI, a pluggable template engine, entity registry, resilient outputs, and observability.

## Features

- **API-first architecture** – FastAPI server exposes health, status, metrics, template, entity, and generator operations. Optional API key auth supported.
- **Typer CLI** – Thin wrapper around the API with health gating, JSON/table output, and commands for entities, templates, and generators.
- **Template system** – Jinja2 renderer with Faker integration, metadata validation, precedence (`default/` vs `custom/`), diff/merge helpers, and community client hooks.
- **Entity registry** – YAML-backed storage with auto-save, CRUD API/CLI, import/export/validate, and backups.
- **Generation engine** – Async lifecycle management, exponential backoff retries, pluggable outputs, structured state-transition logging, and Prometheus metrics.
- **Outputs** – File, console, HTTP, TCP, and syslog handlers share buffered retry logic with per-handler metrics and backlog tracking.
- **Observability** – Prometheus-compatible metrics, structured logs, template/engine telemetry, and end-to-end test coverage.

## Quick start (production)

Recommended path for **Linux x86_64**: download the official **`logforge-{version}-linux-x86_64.tar.gz`** from [GitHub Releases](https://github.com/Fulcrum-Technology-Solutions/LogForge/releases), unpack under `/opt`, put the CLI on `PATH`, then initialize and run:

```bash
sudo tar xzf logforge-{version}-linux-x86_64.tar.gz -C /opt
export PATH=/opt/logforge/app/bin:$PATH
export LOGFORGE_HOME=/opt/logforge
logforge init --force
logforge start          # backgrounds on POSIX (Splunk-style); use --foreground / -f to stay attached
logforge stop           # SIGTERM via $LOGFORGE_HOME/run/logforge.pid; optional --timeout
```

Full operator details: **[docs/deployment/linux-tarball.md](docs/deployment/linux-tarball.md)** (filesystem, systemd, checksums). Broader Linux layout (including systemd): **[docs/deployment/linux-single-instance.md](docs/deployment/linux-single-instance.md)**.

**Other install options:** Install from a **wheel** downloaded from [GitHub Releases](https://github.com/Fulcrum-Technology-Solutions/LogForge/releases) into a venv (`pip install ./logforge-*.whl`), or run from a **source checkout** for development—see [linux-single-instance.md](docs/deployment/linux-single-instance.md). PyPI publishing is not available for this project (the `logforge` name is already taken).

- **Data location:** Config and entities live under **`LOGFORGE_HOME`**. For the **`/opt/logforge`** bundle, the default **`LOGFORGE_HOME`** is **`/opt/logforge`** (product root; same for local runs and `service install` without `--home`). Application logs default to **`/opt/logforge/logs/`**. Override with `LOGFORGE_HOME` / `LOGFORGE_LOG_FILE` or `--home` on install. Service user is typically **`logmgr`**.
- **Upgrades / backups:** [DEPLOYMENT.md](DEPLOYMENT.md). **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### CLI examples

```bash
# Service management
logforge start                    # Start API + engine (daemon on POSIX unless -f)
logforge stop                     # Stop process in run/logforge.pid (same LOGFORGE_HOME as start)
logforge service install          # Install systemd service (requires root)
logforge service start            # Start systemd service
logforge service stop             # Stop systemd service
logforge service restart          # Restart systemd service
logforge service status           # Show service status

# Entity operations
logforge entities list
logforge entities show users alice
logforge entities add users
logforge entities import ./samples/entities.yaml

# Template operations
logforge templates                    # Interactive menu (browse, search, install, view)
logforge templates list               # List local templates (paginated)
logforge templates browse             # Browse remote templates (hierarchical, paginated)
logforge templates search <query>     # Search templates (interactive, paginated)
logforge templates install <id>      # Install template package
logforge templates info <id>         # View template details
logforge templates customize <id>    # Copy installed default → custom for editing
logforge templates diff <id>         # Unified diff: installed default vs custom (4-part ID)
logforge templates merge <id>        # Overwrite custom from default (--yes, --force)
logforge templates create <id>       # New minimal custom .j2 + .meta under templates/custom/

# Generator operations
logforge generators list
logforge generators start testgen
logforge generators stop testgen
```

All commands accept `--output json` for machine-friendly output and `--skip-health-check` for emergency bypasses.

### Metrics & Health

- `GET /api/health` – overall status.
- `GET /api/status` – generator/system telemetry.
- `GET /api/metrics` – Prometheus exposition format with counters/gauges/histograms for templates, outputs, and engine state.

## Development

Environment setup, tests, and formatting: **[docs/development/setup.md](docs/development/setup.md)**.

### Security (local pre-commit)

After cloning, run once to enable secret scanning on commit:

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
brew install gitleaks   # if not installed
```

CI runs TruffleHog via `.github/workflows/security-checks.yml` on push and pull request.

### Directory layout

```
src/logforge/
├── api/           # FastAPI server, routers, models, auth
├── cli/           # Typer entrypoint and command groups
├── community/     # Community API client
├── core/          # Engine, configuration, telemetry, runtime models
├── entities/      # Models, registry, storage, CLI helpers
├── outputs/       # Output handlers (file, console, http, tcp, syslog)
├── templates/     # Loader, metadata validation, renderer, manager
├── utils/         # Logging, metrics helpers
└── ...
```

Tests mirror this structure under `tests/`.

## Configuration

The generated `config.yaml` controls API parameters, engine behavior, entity registry options, template paths, output definitions, and generator configurations. Paths are validated to stay under `LOGFORGE_HOME`.

### Internal log generator

A built-in generator named `internal-logs` forwards application logs (the `logforge.*` logger) to the same output destinations as synthetic events. Enable it in `config.yaml` and start it like any other generator:

```yaml
internal_logs:
  enabled: true
  outputs: [stdout]  # or file, http, etc.
```

Then `logforge generators start internal-logs` (or let the service start it automatically when `internal_logs.enabled` is true). The name `internal-logs` is reserved.

### Generator Timezone Override

Generators support an optional `timezone` field that overrides the organization timezone from the entity registry. This is useful when generating events for different geographic regions or when you need timezone-specific behavior for frequency calculations (business hours, time patterns).

**Configuration**:

```yaml
generators:
  - name: us-east-generator
    template: microsoft/azure-active-directory/authentication/signin_logs
    timezone: America/New_York  # Overrides organization timezone
    enabled: true
    outputs:
      - http-output
  
  - name: eu-west-generator
    template: paloalto/pan-os/firewall/traffic
    timezone: Europe/London  # Different timezone for this generator
    enabled: true
    outputs:
      - http-output
```

**Timezone Resolution**:
1. **Generator config timezone** (if set) - highest priority
2. **Organization timezone** (from `entities.yaml`) - fallback

**Impact**:
- Template rendering: `now()`, `current_timestamp()` functions use generator timezone
- Frequency calculations: Business hours, time patterns, multipliers calculated in generator timezone
- Output handler metadata: `generated_at` timestamps use generator timezone
- Statistics: `last_event` timestamps use generator timezone

**Timezone Format**: Use IANA timezone names (e.g., `America/New_York`, `Europe/London`, `Asia/Tokyo`, `UTC`).

### HTTP Output Metadata Wrapping

HTTP outputs support an optional `include_metadata` setting that wraps events with routing metadata. This is useful when sending events to routing systems like Cribl that need to route based on vendor/product information.

**Configuration**:

```yaml
outputs:
  definitions:
    - name: http-collector
      type: http
      url: https://collector.example.com/events
      method: POST
      headers:
        Authorization: "Bearer ${API_TOKEN}"
        Content-Type: "application/json"
      batch_size: 100
      batch_interval: 5
      timeout: 30
      include_metadata: true  # Enable metadata wrapping
```

**When `include_metadata: false` (default)**:
Events are sent as raw JSON:
```json
{
  "metadata": { ... },
  "time": 1732995095,
  "api": { ... }
}
```

**When `include_metadata: true`**:
Events are wrapped with routing metadata:
```json
{
  "event": {
    "metadata": { ... },
    "time": 1732995095,
    "api": { ... }
  },
  "logforge_metadata": {
    "generated_at": "2025-11-30T16:31:35.797Z",
    "generator": "aws-cloudtrail-generator",
    "template_id": "aws/cloudtrail/management/delete_trail",
    "vendor": "aws",
    "product": "cloudtrail",
    "data_source": "management"
  }
}
```

**Use Cases**:
- **Cribl Routing**: Route events based on `logforge_metadata.vendor` or `logforge_metadata.product`
- **SIEM Parsing**: Extract clean events from `event` field while maintaining routing context
- **Multi-Destination**: Fork events to different destinations based on metadata

**Configuration via CLI**:

**Quick Operations**:
```bash
# Quick-add generator with auto-naming
logforge config edit --add-generator microsoft/azure/signin --name my-gen --outputs http-out

# Quick-edit generator
logforge config edit --edit-generator my-gen --enable
logforge config edit --edit-generator my-gen --outputs http-out,file-out
logforge config edit --edit-generator my-gen --timezone America/New_York
```

**Interactive Mode** (full-featured editor):
```bash
logforge config edit                 # Interactive editor with:
                                      # - Hierarchical template selection (vendor → product → template)
                                      # - Auto-naming generators based on template metadata
                                      # - Batch creation (all/remaining templates)
                                      # - Filter existing generators
                                      # - Pagination for large lists
```

**Output Configuration**:
- When creating HTTP outputs: `logforge config edit` → Manage Outputs → Add new output → HTTP
- When editing generators: `logforge config edit` → Manage Generators → Edit generator → Edit outputs → Configure metadata for HTTP outputs

## License

Apache 2.0. See `LICENSE` for details.

