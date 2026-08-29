# MELTr v2.0 Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish **MELTr** as the OSS single-node synthetic generation product (migrated from LogForge), then ship **v2.0**: auth, preview, community updates, multi-template pipelines, schedule, CI/coverage, and **PyPI publish**.

**Home repo:** [`Fulcrum-Technology-Solutions/MELTr`](https://github.com/Fulcrum-Technology-Solutions/MELTr) → local `/Users/johnowen/GitHub Repositories/work/MELTr`

**Architecture:** Single-process, YAML under `MELTR_HOME` (compat: `LOGFORGE_HOME`), FastAPI + Typer. No Postgres, no worker fleet, no LLM authoring.

**Tech stack:** Python ≥3.10, FastAPI, Typer, Jinja2, Pydantic, pytest, ruff/black/mypy. Package name **`meltr`** (PyPI name currently free — verified 404 on pypi.org).

---

## Locked decisions

| Decision | Choice |
|----------|--------|
| Product / repo | **MELTr** — replaces LogForge OSS first; other LogForge repos (Templates, Templates-UI, Enterprise) migrate later |
| Scope model | **B** — complete single-node product |
| Exception to B | **Multi-template pipelines** in MELTr (single-node only, no fleet) |
| Release | **v2.0.0** on MELTr (first public MELTr release may be 2.0.0 to signal continuity, or 1.0.0+2.0 features — see Phase −1) |
| Priorities | Migrate → CI → Auth → Preview → Updates → Pipelines → Schedule → PyPI/docs |
| Boundary | MELTr = single-node OSS; **LLM authoring = Enterprise-only** (later MELTr Enterprise / rebranded) |
| PyPI | **`meltr`** on PyPI — back in scope (LogForge blocked because `logforge` name taken) |
| Rename depth | Full: package `meltr`, CLI `meltr`, env `MELTR_HOME` / `MELTR_API_KEY`, with **compat aliases** for `logforge` / `LOGFORGE_*` during transition |
| Ecosystem | Keep consuming **logforge.io** / LogForge-Templates for now; rebrand registry later |

---

## Ecosystem migration strategy (later)

```text
Now:     MELTr (OSS engine)  ←── work here
Later:   Templates repo → MELTr-Templates (or keep LogForge-Templates + dual branding)
Later:   Templates-UI / logforge.io → MELTr registry
Later:   LogForge-Enterprise → MELTr Enterprise
```

Until then: MELTr community client still points at `https://logforge.io/api/v1` (configurable). Document as transitional.

---

## Out of scope (v2.0)

- Distributed workers / leader–worker fleet  
- Scenario / campaign / cross-event correlation  
- LLM template creation  
- Transforms / ingest / replay  
- Migrating Templates / Templates-UI / Enterprise repos (separate programs)  
- Deleting the LogForge GitHub repo immediately (archive + README redirect after MELTr is live)

---

## Naming map

| Concept | Old (LogForge) | New (MELTr) | Compat |
|---------|----------------|-------------|--------|
| GitHub repo | LogForge | MELTr | README redirect on LogForge |
| Python package | `logforge` | `meltr` | optional `logforge` shim package deprecated |
| CLI | `logforge` | `meltr` | `logforge` console_script → same entry for 1 minor |
| Home | `LOGFORGE_HOME` / `~/.logforge` | `MELTR_HOME` / `~/.meltr` | Read `LOGFORGE_HOME` if `MELTR_HOME` unset; migrate on `meltr init` |
| API key env | `LOGFORGE_API_KEY` | `MELTR_API_KEY` | Fall back to `LOGFORGE_API_KEY` |
| Config telemetry / User-Agent | LogForge-OSS | MELTr | — |
| PyPI | N/A (blocked) | `meltr` | — |

---

## Architecture notes (product features)

### Pipeline (new primitive)

```yaml
pipelines:
  - name: identity-lab
    enabled: true
    timezone: America/New_York
    outputs: [http-cribl, file-out]
    schedule:
      mode: continuous   # continuous | window | burst
    streams:
      - template: okta/identity-cloud/authentication/login_failure
        weight: 1.0
      - template: microsoft/azure-active-directory/signin/signin
        weight: 1.0
```

Runtime: orchestrate N child `Generator` instances sharing outputs + schedule. Keep standalone `generators:` for backward compatibility. CLI/API: `meltr pipelines …`, `/api/pipelines`.

### Auth / Preview / Updates / Schedule

Same as prior LogForge plan: enforce API auth; template preview; community check-updates; schedule gate (continuous | window | burst). Paths use `src/meltr/…`.

---

## Phase −1 — Migrate LogForge → MELTr (do first)

**Repo today:** MELTr is empty (`README.md` only). LogForge holds full history at sibling path.

### Task −1.1: History-preserving import

- [x] From a clean worktree, add LogForge as source and push history into MELTr `main` (or `develop` then merge), e.g.:
  - Option A: `git clone --mirror` LogForge → push to MELTr (rewrites empty history — coordinate with anyone who already committed to MELTr README)
  - Option B: copy tree + single import commit (loses history — avoid unless required)
- [x] Prefer **Option A** after resetting MELTr `main` or force-pushing with org approval (empty repo; only README to lose)
- [x] Verify: `git log` on MELTr shows LogForge history; `pip install -e .` works after rename PR

### Task −1.2: Rebrand package & CLI

- [x] Rename `src/logforge/` → `src/meltr/`
- [x] Update all imports, `pyproject.toml` name → `meltr`, script entry `meltr = "meltr.cli.main:main"`
- [x] Add deprecated `logforge` script entry pointing at same main (compat)
- [x] `MELTR_HOME` primary; `LOGFORGE_HOME` fallback in `paths.py`
- [x] `MELTR_API_KEY` primary; `LOGFORGE_API_KEY` fallback
- [x] Default data dir `~/.meltr` (init migrates or documents copy from `~/.logforge`)
- [x] User-Agent / telemetry client strings → MELTr
- [x] Update README, AGENTS.md, deployment docs for MELTr branding
- [x] Leave community URL default as logforge.io for now

### Task −1.3: Retire LogForge as active OSS home

- [x] On LogForge repo: README banner → “Moved to MELTr” + link  
- [x] Do not continue feature work in LogForge  
- [x] Enterprise: later change sibling dep to MELTr (`pip install -e ../../MELTr` or `meltr` from PyPI)

### Task −1.4: PyPI readiness (plumbing only)

- [x] Confirm `meltr` still free on PyPI before first publish  
- [ ] Add trusted-publisher / API token workflow scaffold (publish on tag) — dry-run until v2.0  
- [x] License remains Apache-2.0 unless decided otherwise  

**Done when:** MELTr is the only active OSS checkout; `meltr --help` works; tests pass under new package name; LogForge README redirects.

---

## Phase 0 — CI & coverage (weeks 1–2)

**Priority #9.**

### Task 0.1: CI on MELTr

- [ ] `.github/workflows/ci.yml`: Python 3.10–3.12, `pip install -e ".[dev]"`, ruff, black --check, pytest  
- [ ] Keep/adapt `security-checks.yml`, `release.yml` for MELTr artifact names (`meltr-*-linux-*.tar.gz`)

### Task 0.2: Coverage strategy

- [ ] Short term: fail-under ≈ current floor (~25%) or separate optional job  
- [ ] v2.0 target: **≥60%** on `src/meltr`  
- [ ] Each feature phase adds tests for its modules  

**Done when:** Every push to MELTr runs lint + tests without false coverage red.

---

## Phase 1 — API auth enforcement

- [ ] Tests: auth on → 401 without key; CLI with `MELTR_API_KEY` succeeds  
- [ ] Health public; metrics protected when auth on (recommended)  
- [ ] `src/meltr/api/auth.py`; wire routers  
- [ ] README: enable auth  

**Done when:** Auth config is real.

---

## Phase 2 — Template preview

- [ ] `POST /api/templates/{id}/preview` `{ "count": 1..20 }`  
- [ ] `meltr templates preview <id> [--count N]`  
- [ ] Fixture templates + tests  

**Done when:** Preview without starting generators.

---

## Phase 3 — Community update detection

- [ ] Fill `version` / `remote_version` on template API  
- [ ] `GET /api/community/updates` + `meltr templates check-updates`  
- [ ] Still talks to logforge.io until registry rebrand  

**Done when:** Stale packages visible to operators.

---

## Phase 4 — Multi-template pipelines

- [ ] `PipelineConfig` / streams in config  
- [ ] Orchestrator over child generators  
- [ ] `/api/pipelines` + `meltr pipelines …`  

**Done when:** ≥2 templates → shared destinations on one node.

---

## Phase 5 — Schedule

- [ ] `continuous` | `window` | `burst`  
- [ ] Primary on pipeline; optional on generator  
- [ ] Tests for window + burst  

**Done when:** Business-hours and burst-then-stop work without manual stop.

---

## Phase 6 — Docs, PyPI, release

### Task 6.1: Docs

- [ ] `docs/ecosystem-glossary.md` (MELTr terms; note LogForge legacy names)  
- [ ] README: install from PyPI + GitHub; pipelines; schedule; auth; preview; updates  
- [ ] Enterprise/LLM called out as future / separate  

### Task 6.2: Destination presets (light)

- [ ] Document Cribl/Splunk HEC + `include_metadata`  
- [ ] Optional: `meltr outputs test <name>`  

### Task 6.3: Coverage ≥60%

- [ ] Raise CI fail-under to 60  

### Task 6.4: Release v2.0.0 + PyPI

- [ ] Version `2.0.0` (continuity with LogForge 1.1.x) **or** `1.0.0` if you prefer clean MELTr semver — **default: 2.0.0**  
- [ ] GitHub Release + Linux tarball  
- [ ] **`twine` / OIDC publish `meltr` to PyPI**  
- [ ] Verify: `pip install meltr` on clean venv  

**Done when:** `pip install meltr` works; dogfood checklist below passes.

---

## Sequencing

```text
Week:  0      1    2    3    4    5    6    7    8    9   10
Migrate ████
CI            ████
Auth          ████████
Preview            ████████
Updates                 ████████
Pipeline                     ████████████████
Schedule                          ████████████
PyPI/docs/release                       ████████
```

---

## Acceptance criteria (MELTr v2.0 dogfood)

1. Active development only on **MELTr**; LogForge README redirects  
2. `pip install meltr` (or `-e .`) provides `meltr` CLI  
3. Auth enforced when enabled; `MELTR_API_KEY` works (compat `LOGFORGE_API_KEY`)  
4. `meltr templates preview <id>` works  
5. `meltr templates check-updates` works against current registry  
6. Pipeline ≥2 templates → ≥2 outputs  
7. Schedule window + burst documented and tested  
8. CI green; coverage ≥60%  
9. Published on **PyPI** as `meltr`  
10. LLM / fleet documented as not-in-OSS  

---

## Risks

| Risk | Mitigation |
|------|------------|
| Force-push to MELTr loses README-only history | Empty repo; document; proceed |
| Rename breaks Enterprise checkout | Compat path docs; update Enterprise when ready |
| PyPI name squatted before publish | Claim ASAP with 0.0.1 or 2.0.0a1 placeholder after migrate |
| Registry still “LogForge” branding | Config URL; dual branding in docs until UI migrate |
| Pipeline rewrite balloons | Orchestrate existing Generators |

---

## Ready to go — immediate next actions

1. **Approve Phase −1 approach:** mirror LogForge history into MELTr + full `meltr` rebrand + PyPI name claim.  
2. **Agent executes Phase −1** in `/Users/johnowen/GitHub Repositories/work/MELTr` (needs git push permission / `all`).  
3. Then Phase 0 CI + Phase 1 auth on MELTr only.  

**Do not** implement v2.0 features in the LogForge tree.

---

## Explicit non-goals reminder

Scenarios/correlation, fleet, LLM, Kafka/S3 as blockers, and migrating Templates/UI/Enterprise — **not** MELTr v2.0. Track as follow-on “replace LogForge stack” program.
