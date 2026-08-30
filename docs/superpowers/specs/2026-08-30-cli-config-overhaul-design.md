# CLI config overhaul + generators-only product model

**Date:** 2026-08-30  
**Status:** Approved (brainstorm)  
**Repo:** MELTr  
**Approach:** Vertical slices (model → menu → docs/grep gate)

## Goal

Make the local OSS product match a simple mental model, fix the config editor, and remove pipeline complexity before production.

## Product model

| Concept | Role |
|---------|------|
| **Entity registry** | Single `entities.yaml` for the local environment |
| **Output** | Destination (file, console, HTTP, TCP, syslog) — word **outputs** everywhere |
| **Generator** | One template → one or more outputs; velocity/density from template metadata |
| **Schedule** | Optional secondary control; default **continuous** |
| **internal-logs** | Reserved generator; not a Jinja template; app log forwarding |

**Not in product:** pipelines / streams / shared multi-template orchestrator.

**Philosophy:** Enable multiple generators for multiple templates. Simplest straightforward path.

**Pre-production:** No legacy config migration, no special-case errors for removed keys (`pipelines`, old `internal_logs:` block, `logforge_metadata`). Delete the old code and ship the new shape only. Stale YAML keys are ignored by the loader or fail as ordinary unknown/invalid config — do not add dedicated “formerly pipelines” messaging or migrate-on-load paths.

### Reserved generator `internal-logs`

- Always present after load / in default config
- Default: `enabled: false`, `outputs: []`
- Cannot be removed (CLI/API reject); enable/disable + outputs only
- No template picker; no schedule UI
- Engine keeps `InternalLogGenerator` behind that name
- Configured only as a reserved entry under `generators:` — no separate `internal_logs:` config object

### Removals / renames

- Delete pipelines end-to-end (config model, `Pipeline` engine, CLI, API, tests, docs) — no residual references in product copy
- `logforge_metadata` → `meltr_metadata` in code and docs only (no load-time rename of old YAML)
- Rebrand user-facing LogForge leftovers in config editor (title, reload hints, `${MELTR_HOME}`)

### Compat env (allowlisted)

Keep **`LOGFORGE_HOME`**, **`LOGFORGE_API_KEY`**, and related `LOGFORGE_*` aliases for one release. Document in allowlist for the string-match gate. Prefer `MELTR_*` in new copy.

## Config menu (`meltr config edit`)

**Main menu:** Outputs · Generators · API · Engine · Logging · Preview · Save · Discard

### Outputs

- Existing add/edit/remove by type
- HTTP metadata field / prompts: `meltr_metadata`
- Labels: “outputs” (not destinations)

### Generators — happy path

1. Pick template (vendor → product → template)
2. Pick one or more outputs
3. Enable (default on for new user generators)
4. Persist via Save on main menu

### Generators — secondary

- “Set schedule…” → `continuous` / `window` / `burst`
- Not part of Add Generator flow

### `internal-logs` in list

- Always shown
- Edit: enable + outputs only
- Remove: blocked with clear message

### Fixes

- `--section` must offer save (or track dirty and prompt)
- Editor title: MELTr Configuration Editor
- Reload guidance: `meltr config reload`
- Path defaults: `${MELTR_HOME}/...`
- Remove output: warn if generators reference it; clear or block with explicit choice

### Out of scope for this menu

- Entities editor (`meltr entities`)
- Community template install (`meltr templates`)

## Architecture

### Slice 1 — Product model

- Remove `PipelineConfig` / `PipelineStreamConfig` / `pipelines` from `Config`
- Remove `src/meltr/core/pipeline.py` and engine/CLI/API wiring
- Remove `InternalLogsConfig` / `internal_logs` field; use reserved generator only
- Rename metadata key in code to `meltr_metadata`
- Update `create_default_config()` to include disabled `internal-logs`

### Slice 2 — Config menu

- Fix save/`--section`/rebrand/path defaults
- Continuous-first generator UX; optional schedule action
- Enforce non-removable `internal-logs`
- Light module split only if file remains unmanageable (`config_editor_*.py`)

### Slice 3 — Docs + string gate

- Glossary/README/release notes: generators-only story; schedule secondary
- Repo-wide search: `logforge`, `LogForge`, `LOGFORGE`, `logforge_metadata`, `pipelines`
- Allowlist file or CI check for intentional leftovers only (compat env, “formerly LogForge” in historical notes if any)

## Errors

| Condition | Behavior |
|-----------|----------|
| Delete `internal-logs` | Reject |
| Missing reserved generator on load | Inject disabled `internal-logs` into in-memory config (not a migrate-from-old-key path) |

## Testing

- Slice 1: no Pipeline types/modules; default config has internal-logs; metadata key is meltr_metadata; reserved name rules
- Slice 2: add-generator helpers; schedule secondary; `--section` save; cannot remove internal-logs
- Slice 3: docs accuracy; grep/allowlist gate green (no pipeline product references)

## Non-goals

- Any pipeline migration, compatibility shims, or user-facing “pipelines removed” copy
- Load-time rewrite of `logforge_metadata` / `internal_logs:`
- Enterprise UI / fleet
- Rewriting entities editor
- Dropping `LOGFORGE_*` env aliases in this work (allowlist only)

## Acceptance

1. No pipelines in code, tests, or docs (grep clean aside from allowlist if any historical note)
2. Default config has disabled `internal-logs` generator; cannot remove via CLI
3. Config menu: continuous-first generators; optional schedule; outputs wording; MELTr branding
4. `--section` can persist changes
5. `meltr_metadata` is the only metadata include flag name in code
6. String-match pass for logforge/LogForge/LOGFORGE with documented allowlist only
