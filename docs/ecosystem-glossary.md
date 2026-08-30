# MELTr Ecosystem Glossary

Canonical terminology for the MELTr stack and transitional LogForge names. Link this doc from sibling repos (Templates, Templates-UI, Enterprise) during the rebrand.

## Core concepts

| Term | Definition |
|------|------------|
| **Template** | Four-part ID: `vendor/product/data_source/event_type` (e.g. `okta/identity-cloud/authentication/login_failure`) |
| **Stream** | One weighted template entry inside a **pipeline** (`streams[].template` + `weight`) |
| **Generator** | Runtime unit that renders one template and emits events to configured outputs |
| **Pipeline** | Multi-template orchestrator: N child generators share outputs and an optional **schedule** |
| **Schedule** | Emission gate on a generator or pipeline: `continuous`, `window` (tz-aware days/time), or `burst` (count/duration then auto-stop) |
| **Output / destination** | Named sink (file, console, HTTP, TCP, syslog) referenced by generators and pipelines |
| **meltr_metadata** | HTTP wrapper field (when `include_metadata: true`) carrying generator/template routing context alongside the rendered `event` |
| **Community template** | Registry content installed under `templates/default/` from [logforge.io](https://logforge.io) |
| **Local override** | User-edited template under `templates/custom/` (takes precedence when configured) |
| **Vendor package** | `.forge` tarball installed per vendor via `meltr templates install` |
| **Entity registry** | YAML file (`entities.yaml`) with organization, users, devices, and services used at render time |
| **MELTR_HOME** | Config and data root (default `~/.meltr`). Holds `config.yaml`, entities, templates, logs, PID file |

## LogForge legacy (compat)

| Old (LogForge) | New (MELTr) | Notes |
|----------------|-------------|-------|
| `LOGFORGE_HOME` / `~/.logforge` | `MELTR_HOME` / `~/.meltr` | Read `LOGFORGE_HOME` if `MELTR_HOME` unset |
| `LOGFORGE_API_KEY` | `MELTR_API_KEY` | Key-implies-auth for management API |
| `logforge` CLI | `meltr` | `logforge` console script is a temporary alias |
| LogForge OSS repo | **MELTr** | Former single-node engine home |

## API surfaces

| Service | Base URL | Versioning |
|---------|----------|------------|
| Templates registry (transitional) | `https://logforge.io/api/v1` | `/api/v1` |
| MELTr management (single-node) | `http://127.0.0.1:8080/api` | `/api` (no v1) |
| LogForge Enterprise manager | `http://localhost/api` (via Traefik) | `/api` (no v1) |

## Enterprise-only (not in MELTr OSS)

| Term | Definition |
|------|------------|
| **Worker / worker group** | Fleet node running assigned generators (Enterprise) |
| **Job** | Short-lived worker task (preview at scale, integration tests) |
| **LLM template authoring** | AI-assisted template creation in Enterprise web UI |
| **Generation pipeline (UI label)** | Enterprise UI name for a distributed generator configuration |

MELTr OSS is the **single-node** product: FastAPI + Typer, YAML under `MELTR_HOME`, no Postgres, no worker fleet, no LLM authoring.

## Related repos

| Repo | Role |
|------|------|
| [MELTr](https://github.com/Fulcrum-Technology-Solutions/MELTr) | OSS engine (this repo) |
| [LogForge-Templates](https://github.com/Fulcrum-Technology-Solutions/LogForge-Templates) | Community template source (synced to registry) |
| [LogForge-Templates-UI](https://github.com/Fulcrum-Technology-Solutions/LogForge-Templates-UI) | Public registry at logforge.io |
| [LogForge-Enterprise](https://github.com/Fulcrum-Technology-Solutions/LogForge-Enterprise) | Distributed edition (Manager + workers) |
