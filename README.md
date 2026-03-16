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

## Quick Start

### Prerequisites

- Python 3.9+
- Optional: `uvicorn`, `poetry`/`pipx`/`pip` for execution, curl/httpie for API tests.

### Installation

```bash
git clone https://github.com/your-org/logforge.git
cd logforge
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Initialize

After installing the wheel (or from source), run init to create the directory layout, default configuration, sample entities, and template scaffolding. Optionally create the `logmgr` service user and set ownership (requires root).

**Where config/data lives (LOGFORGE_HOME):**
- **Repo / dev:** To use a local data dir in the repo, set `LOGFORGE_HOME=./.logforge` or run `logforge init --directory ./.logforge`; that creates `./.logforge` (or use an existing `./logforge`). Otherwise init uses `~/.logforge` (interactive) or `/var/lib/logforge` (service).
- **Installed (system):** Set `LOGFORGE_HOME` to a path the process can write (e.g. `/var/lib/logforge` for the service, or `/opt/LogForge/data` if you keep data next to the install). Service accounts (e.g. `logmgr`) default to `/var/lib/logforge` when `LOGFORGE_HOME` is not set; have root create and chown that dir first if needed.

```bash
# Repo/dev: init in current dir (creates ./.logforge or uses existing ./logforge)
logforge init --force

# Installed + service user: use /var/lib/logforge (create once as root)
sudo mkdir -p /var/lib/logforge && sudo chown logmgr:logmgr /var/lib/logforge
sudo logforge init --directory /var/lib/logforge --user logmgr --group logmgr --force

# Or set LOGFORGE_HOME and init (no root required for layout)
export LOGFORGE_HOME=/var/lib/logforge
logforge init --directory $LOGFORGE_HOME --no-create-user --force
```

Init creates `config.yaml`, `entities.yaml` (with sample organization, users, devices, services), and `templates/default`, `templates/custom`, `outputs`. Use `--user logmgr --create-user` (with sudo) to create the service user and set directory ownership.

### Start the Service 

**Foreground mode (development/testing):**
```bash
logforge start
```

**As a systemd service (production):**
```bash
# Install systemd service (runs as logmgr by default; use --no-create-user if user exists)
sudo logforge service install --user logmgr --home /var/lib/logforge

# Start the service
sudo systemctl start logforge
# or use the wrapper:
sudo logforge service start

# Enable on boot
sudo systemctl enable logforge
```

The service embeds the management API server and starts enabled generators automatically. The CLI health-checks the API before performing operations.

### CLI Examples

```bash
# Service management
logforge start                    # Start service (foreground)
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
logforge templates customize <id>    # Create custom template override
logforge templates diff <id>         # Compare local vs remote template

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

### Tests

```bash
pytest           # full suite
pytest -k tcp    # focused tests
```

The suite includes unit, API, CLI, output, and end-to-end scenarios.

### Formatting & Linting

```bash
ruff check .
black .
mypy src
```

### Directory Layout

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

# LogForge OSS

LogForge is a synthetic event log generator tailored for security engineering teams.

## Development Status

The project is under active construction. See `Tasks.md` for phase planning and progress notes.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## CLI Usage

**Entity Management**:
- `logforge entities list` — show registry summary or `--type users|devices|services` for detailed listings.
- `logforge entities show <type> <name>` — view specific entity details.
- `logforge entities add <type>` — interactively add new entity.
- `logforge entities import <file>` — import entities from YAML file.

**Generator Management**:
- `logforge generators list` — fetch generator status from the management API.
- `logforge generators start <name>` / `stop <name>` — control generator lifecycles.

**Template Management**:
- `logforge templates` — interactive menu for browsing, searching, and installing templates.
- All template commands support pagination for large result sets.
- Hierarchical browsing: vendor → product → template selection.

## API Quick Start

The management API runs on `http://127.0.0.1:8080` by default.

```bash
# Generator overview
curl http://127.0.0.1:8080/api/generators | jq

# Start or stop a generator
curl -X POST http://127.0.0.1:8080/api/generators/windows_security/start
curl -X POST http://127.0.0.1:8080/api/generators/windows_security/stop

# Entity summary
curl http://127.0.0.1:8080/api/entities | jq
```

## Troubleshooting

### Installation Issues

**Error: `No module named pip` in venv**

Upgrade pip in your virtual environment:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

**Error: Editable install fails with older pip**

Upgrade pip to version 21.3+ (PEP 660 support required):

```bash
python -m pip install --upgrade pip
```

## License

Apache License 2.0

