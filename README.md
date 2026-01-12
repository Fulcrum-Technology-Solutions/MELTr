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

```bash
export LOGFORGE_HOME=/opt/logforge
logforge init --force
```

This creates the directory layout, default configuration, entity registry, and template scaffolding under `LOGFORGE_HOME`.

### Start the Service) 

**Foreground mode (development/testing):**
```bash
logforge start
```

**As a systemd service (production):**
```bash
# Install systemd service (creates user, directories, service file)
sudo logforge service install

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
logforge templates list
logforge templates info vendor/product/datasource/name
logforge templates customize vendor/product/datasource/name
logforge templates diff vendor/product/datasource/name
logforge templates install vendor/product/datasource/name

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

- `logforge entities list` — show registry summary or `--type users|devices|services` for detailed listings.
- `logforge generators list` — fetch generator status from the management API.
- `logforge generators start <name>` / `stop <name>` — control generator lifecycles.

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

