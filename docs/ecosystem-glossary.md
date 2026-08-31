# MELTr Ecosystem Glossary

Canonical terminology for the MELTr stack.

## Core concepts

| Term | Definition |
|------|------------|
| **Template** | Four-part ID: `vendor/product/data_source/event_type` (e.g. `okta/identity-cloud/authentication/login_failure`) |
| **Generator** | Runtime unit that renders **one template** and emits events to one or more configured **outputs**; velocity/density from template metadata |
| **Schedule** | Optional secondary emission gate on a generator: `continuous` (default), `window` (tz-aware days/time), or `burst` (count/duration then auto-stop) |
| **Output** | Named sink (file, console, HTTP, TCP, syslog) referenced by generators |
| **internal-logs** | Reserved generator for application log forwarding (not a Jinja template); always present after load, cannot be removed; enable + outputs only |
| **meltr_metadata** | HTTP wrapper field (when `include_metadata: true`) carrying generator/template routing context alongside the rendered `event` |
| **Community template** | Registry content installed under `templates/default/` from [meltr.ftsc.cloud](https://meltr.ftsc.cloud) |
| **Local override** | User-edited template under `templates/custom/` (takes precedence when configured) |
| **Vendor package** | `.forge` tarball installed per vendor via `meltr templates install` |
| **Entity registry** | YAML file (`entities.yaml`) with organization, users, devices, and services used at render time |
| **MELTR_HOME** | Config and data root (default `~/.meltr`). Holds `config.yaml`, entities, templates, logs, PID file |

## API surfaces

| Service | Base URL | Versioning |
|---------|----------|------------|
| Community templates registry | `https://meltr.ftsc.cloud/api/v1` | `/api/v1` |
| MELTr management (single-node) | `http://127.0.0.1:8080/api` | `/api` (no v1) |
| Enterprise manager | `http://localhost/api` (via Traefik) | `/api` (no v1) |

## Enterprise-only (not in MELTr OSS)

| Term | Definition |
|------|------------|
| **Worker / worker group** | Fleet node running assigned generators (Enterprise) |
| **Job** | Short-lived worker task (preview at scale, integration tests) |
| **LLM template authoring** | AI-assisted template creation in Enterprise web UI |
| **Distributed generator (Enterprise UI)** | Enterprise UI label for a fleet-assigned generator configuration |

MELTr OSS is the **single-node** product: FastAPI + Typer, YAML under `MELTR_HOME`, no Postgres, no worker fleet, no LLM authoring.

## Related repos

| Repo | Role |
|------|------|
| [MELTr](https://github.com/Fulcrum-Technology-Solutions/MELTr) | OSS engine (this repo) |
| Community templates source | Synced into the registry (sibling GitHub repo; name TBD during ecosystem migrate) |
| Community registry UI | Serves `meltr.ftsc.cloud` (sibling GitHub repo; name TBD during ecosystem migrate) |
| Enterprise edition | Distributed Manager + workers (sibling GitHub repo; name TBD during ecosystem migrate) |
