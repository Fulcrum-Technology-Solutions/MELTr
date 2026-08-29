# MELTr v2.0 Design Spec

**Date:** 2026-08-29  
**Status:** Approved (brainstorming)  
**Home:** `/Users/johnowen/GitHub Repositories/work/MELTr`  
**Plan reference:** `docs/superpowers/plans/2026-08-29-meltr-v2-completion.md`

## Goal

Ship **MELTr v2.0.0** as the complete single-node OSS synthetic generation product: auth, preview, community update detection, multi-template pipelines, schedule, CI/coverage ≥60%, docs, and **PyPI** publish (`meltr`).

## Locked decisions

| Topic | Choice |
|-------|--------|
| Scope | Full v2.0 dogfood checklist through PyPI |
| Version | Stable `2.0.0`; early name claim `2.0.0a1` |
| Auth | Key-implies-auth |
| PyPI | GitHub Actions OIDC Trusted Publisher |
| Delivery | Stacked PRs by phase (0→6) |
| Approach | Plan-faithful incremental — extend existing engine/generators; no pipeline-only rewrite |
| Registry | Keep `https://logforge.io/api/v1` until Templates-UI rebrand |
| Out of scope | Fleet, LLM authoring, scenarios/correlation, Templates/UI/Enterprise migration |

## Architecture (unchanged shape)

```
CLI (Typer) ──► Management API (FastAPI) ──► Engine
                                              ├── generators (existing)
                                              ├── pipelines (new orchestrator → child Generators)
                                              ├── templates / entities / outputs
                                              └── schedule gate (new)
```

State remains YAML under `MELTR_HOME` (compat `LOGFORGE_HOME`). Single process; no Postgres; no worker fleet.

---

## §1 Delivery & CI

1. One branch/PR per phase: `feat/v2-phase-0-ci` … `feat/v2-phase-6-release`, merge to `main`.
2. **Phase 0**
   - Add `.github/workflows/ci.yml`: Python 3.10–3.12; `pip install -e ".[dev]"`; `ruff check`; `black --check`; `pytest`.
   - Coverage fail-under starts near current floor (~25–30%); raise toward **60%** by Phase 6.
   - Adapt `release.yml` artifact names to `meltr-*`.
   - Add `publish-pypi.yml` (OIDC Trusted Publisher; tag + `workflow_dispatch`); document PyPI project linking in README.
3. After Phase 0 + Trusted Publisher linked: tag **`v2.0.0a1`** to claim the name (human approves first publish). Does not block Phases 1–5.
4. Phase 6 tags **`v2.0.0`** for stable GitHub Release + tarball + PyPI.

---

## §2 API auth

**When auth is on:** a non-empty API key exists from config (`api.auth.key`) or env (`MELTR_API_KEY` / `LOGFORGE_API_KEY`), **or** `api.auth.enabled: true` (then a key is required — refuse start if missing).

**Implementation**

- `src/meltr/api/auth.py` — FastAPI dependency; Bearer token vs configured key; constant-time compare.
- Apply to all routes except **`GET /api/health`** (public).
- **`GET /api/metrics`** protected when auth is on.
- Existing CLI `APIClient` already sends `Authorization: Bearer …`.

**Tests:** open when no key; 401 without Bearer when key set; CLI with key succeeds; health always public.

---

## §3 Template preview + community updates

### Preview

- `POST /api/templates/{template_id}/preview` with body `{ "count": 1..20 }` (default 1).
- Render via `TemplateLoader` + `TemplateRenderer` + entity registry; **do not** start generators or write outputs.
- Response: `{ "template_id", "count", "events": [string, ...] }`.
- CLI: `meltr templates preview <id> [--count N] [--output json|text]`.
- Errors: 404 missing template; 400 bad count. Auth applies when on.

### Updates

- Populate `version` / `remote_version` on template list/detail API (replace `None` TODOs) via local metadata vs community API.
- `GET /api/community/updates` — stale packages: `{ product_id, local_version, remote_version, … }`.
- CLI: `meltr templates check-updates` (reuse comparison helpers already used in CLI).
- **Detection only** — no auto-upgrade in v2.0.
- Community base URL remains configurable; default `logforge.io`.

---

## §4 Pipelines + schedule

### Pipelines

Config (YAML-primary, same as generators):

```yaml
pipelines:
  - name: identity-lab
    enabled: true
    timezone: America/New_York
    outputs: [http-cribl, file-out]
    schedule:
      mode: continuous
    streams:
      - template: vendor/product/datasource/event
        weight: 1.0
```

- `Pipeline` orchestrates **N child `Generator` instances** (one per stream), sharing output handlers and schedule gate.
- Standalone `generators:` remain supported.
- Pipeline name must not collide with a generator name.
- CLI/API: list / get / start / stop / status under `meltr pipelines …` and `/api/pipelines`.

### Schedule

New gate in `src/meltr/core/schedule.py` (separate from frequency `variation` rate multipliers):

| Mode | Behavior |
|------|----------|
| `continuous` | Emit whenever started (default) |
| `window` | Emit only inside tz-aware `days` + `time`; pause outside without stopping the process |
| `burst` | Emit until `count` events **or** `duration`, then auto-stop |

- Primary on pipeline; optional on standalone generator.
- Frequency/variation still controls **rate** while schedule allows emission.

---

## §5 Docs, destinations, coverage, release

- `docs/ecosystem-glossary.md` — MELTr terms + LogForge legacy names.
- README: PyPI install, auth, preview, check-updates, pipelines, schedule; LLM/fleet **not in OSS**.
- Destination presets: document Cribl/Splunk HEC + `include_metadata`; optional `meltr outputs test <name>` (prefer config validate + optional live probe).
- Coverage fail-under **60%** on `src/meltr` by Phase 6 end.
- Tag `v2.0.0`; GitHub Release + Linux tarball; OIDC publish `meltr==2.0.0`.
- Dogfood checklist in the completion plan must pass before stable tag.

---

## Error handling principles

- Auth failures: 401 with stable public message (no key leakage).
- Preview/template missing: 404; invalid count: 400.
- Schedule/window closed: generators stay RUNNING but emit zero (or DEGRADED only if outputs fail — prefer quiet pause).
- Burst completion: transition to STOPPED with clear status reason.
- Community API failures on check-updates: non-zero CLI exit + actionable error; do not corrupt local installs.

## Testing strategy

| Phase | Focus |
|-------|--------|
| 0 | CI green; coverage floor honest |
| 1 | Auth matrix (off/on/health/metrics/CLI) |
| 2 | Preview fixture + bounds |
| 3 | Updates with mocked community client |
| 4 | ≥2 streams → ≥2 outputs |
| 5 | Window open/closed; burst stop |
| 6 | Coverage ≥60%; release smoke (`pip install meltr` on clean venv) |

## Acceptance (dogfood)

1. Development only on MELTr; LogForge README redirects  
2. `pip install meltr` (or `-e .`) → `meltr` CLI  
3. Auth when key set; `MELTR_API_KEY` works  
4. `meltr templates preview <id>`  
5. `meltr templates check-updates`  
6. Pipeline ≥2 templates → ≥2 outputs  
7. Schedule window + burst tested and documented  
8. CI green; coverage ≥60%  
9. On PyPI as `meltr`  
10. LLM / fleet documented as not-in-OSS  

## Implementation next step

After user review of this spec: write a detailed implementation plan via `writing-plans`, then execute stacked PRs starting at Phase 0.
