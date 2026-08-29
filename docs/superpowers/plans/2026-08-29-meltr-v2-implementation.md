# MELTr v2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship MELTr **v2.0.0** — CI, key-implies auth, template preview, community update detection, multi-template pipelines, schedule modes, docs/coverage ≥60%, and PyPI (`2.0.0a1` then `2.0.0`).

**Architecture:** Extend the existing single-process FastAPI + Typer + YAML engine. Auth via FastAPI dependency. Pipelines orchestrate child `Generator` instances. Schedule is a emit-gate separate from frequency variations. Stacked PRs per phase into `main`.

**Tech Stack:** Python ≥3.10, FastAPI, Typer, Pydantic, pytest, ruff, black, GitHub Actions (CI + OIDC PyPI).

**Spec:** `docs/superpowers/specs/2026-08-29-meltr-v2-design.md`  
**Roadmap checkboxes:** `docs/superpowers/plans/2026-08-29-meltr-v2-completion.md`

## Global Constraints

- Package/CLI name: `meltr`; compat `logforge` entry + `LOGFORGE_*` env fallbacks
- Version target: stable `2.0.0`; early claim `2.0.0a1`
- Auth: key-implies-auth; `GET /api/health` public; `/api/metrics` protected when auth on
- Community registry default: `https://logforge.io/api/v1`
- No fleet, LLM, scenarios, or Templates/UI/Enterprise migration in this plan
- Delivery: one PR per phase (`feat/v2-phase-N-*`)
- Coverage: lower fail-under to honest floor in Phase 0; **≥60%** by Phase 6
- Work only in MELTr repo; sync `main` before each phase branch

## File map (create / modify)

| Path | Responsibility |
|------|----------------|
| `.github/workflows/ci.yml` | Lint + test matrix |
| `.github/workflows/publish-pypi.yml` | OIDC publish on tag |
| `.github/workflows/release.yml` | `meltr-*` tarball names |
| `pyproject.toml` | cov-fail-under; optional publish metadata |
| `src/meltr/__init__.py` | `__version__` bumps on release tags |
| `src/meltr/api/auth.py` | Bearer dependency + key resolution |
| `src/meltr/api/server.py` | Wire auth; metrics gate; description cleanup |
| `src/meltr/api/endpoints/*.py` | Depends(require_api_key) where needed |
| `src/meltr/api/endpoints/templates.py` | Preview + version fields |
| `src/meltr/api/endpoints/community.py` | Updates endpoint (new) |
| `src/meltr/api/endpoints/pipelines.py` | Pipeline API (new) |
| `src/meltr/core/config.py` | `ScheduleConfig`, `PipelineConfig`, `pipelines` list |
| `src/meltr/core/schedule.py` | continuous / window / burst gate (new) |
| `src/meltr/core/pipeline.py` | Orchestrator (new) |
| `src/meltr/core/engine.py` | Load/start/stop pipelines |
| `src/meltr/core/generator.py` | Honor schedule gate in loop |
| `src/meltr/cli/pipelines.py` | CLI (new) |
| `src/meltr/cli/templates.py` | `preview`, `check-updates` commands |
| `src/meltr/cli/main.py` | Register pipelines typer |
| `docs/ecosystem-glossary.md` | Terms |
| `README.md` | v2.0 user docs |
| `tests/test_api_auth.py` | Auth matrix |
| `tests/test_template_preview.py` | Preview |
| `tests/test_community_updates.py` | Updates |
| `tests/test_schedule.py` | Schedule unit |
| `tests/test_pipelines.py` | Pipeline integration |

---

## Phase 0 — CI & coverage floor

### Task 0.1: CI workflow + honest coverage floor

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]` `addopts` cov-fail-under **25**)
- Modify: `.github/workflows/release.yml` (replace remaining `logforge` artifact strings with `meltr` if any)

**Interfaces:**
- Produces: green CI on PR; local `pytest` fails only under 25% coverage

- [ ] **Step 1: Measure current coverage**

```bash
cd "/Users/johnowen/GitHub Repositories/work/MELTr"
source .venv/bin/activate || (python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]")
pytest --cov-fail-under=0 -q 2>&1 | tail -5
```

Expected: all tests pass; TOTAL ~30%.

- [ ] **Step 2: Set fail-under to 25 in pyproject.toml**

In `pyproject.toml` under `addopts`, change:

```toml
"--cov-fail-under=25",
```

(from `80`).

- [ ] **Step 3: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Ruff
        run: ruff check .
      - name: Black
        run: black --check .
      - name: Pytest
        run: pytest -q
```

If `ruff`/`black` fail on pre-existing issues, either fix only touched files' blockers or scope checks to `src/meltr tests` in this task and note remaining debt in the PR — do **not** mass-reformat the repo unless CI cannot pass otherwise. Prefer:

```yaml
      - run: ruff check src tests
      - run: black --check src tests
```

If still red, open a follow-up chore; Phase 0 must at least run pytest green.

- [ ] **Step 4: Verify locally**

```bash
pytest -q
```

Expected: PASS with coverage ≥25%.

- [ ] **Step 5: Commit on `feat/v2-phase-0-ci`**

```bash
git checkout main && git pull origin main
git checkout -b feat/v2-phase-0-ci
git add .github/workflows/ci.yml pyproject.toml .github/workflows/release.yml
git commit -m "ci: add test workflow and lower coverage floor to 25%"
```

---

### Task 0.2: PyPI OIDC publish workflow scaffold

**Files:**
- Create: `.github/workflows/publish-pypi.yml`
- Modify: `README.md` (short “Publishing” note: link PyPI Trusted Publisher to this repo/workflow)

**Interfaces:**
- Produces: workflow that publishes on tags `v*` using `pypa/gh-action-pypi-publish`
- Consumes: PyPI project `meltr` Trusted Publisher config (human sets on pypi.org)

- [ ] **Step 1: Add workflow**

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:

permissions:
  contents: read
  id-token: write

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Build
        run: |
          python -m pip install --upgrade pip build
          python -m build
      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 2: Document Trusted Publisher setup in README** (3–5 bullets: create empty `meltr` project on PyPI; add publisher GitHub org/repo `Fulcrum-Technology-Solutions/MELTr`; workflow `publish-pypi.yml`; environment `pypi`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish-pypi.yml README.md
git commit -m "ci: add OIDC PyPI publish workflow"
```

- [ ] **Step 4: Open PR for Phase 0; merge when green**

```bash
git push -u origin HEAD
gh pr create --title "ci: Phase 0 — CI + PyPI publish scaffold" --body "## Summary
- CI matrix 3.10–3.12
- Coverage floor 25%
- OIDC publish workflow for meltr
"
```

- [ ] **Step 5 (human):** After merge + Trusted Publisher linked, optionally tag `v2.0.0a1` (bump `__version__` in that release commit/tag flow). Do not block Phase 1.

---

## Phase 1 — API auth

### Task 1.1: Auth module + unit tests

**Files:**
- Create: `src/meltr/api/auth.py`
- Create: `tests/test_api_auth.py`
- Modify: `src/meltr/core/config.py` (docstring on `AuthConfig` clarifying key-implies-auth)

**Interfaces:**
- Produces:
  - `def resolve_api_key(config: Config) -> Optional[str]`
  - `def auth_required(config: Config) -> bool` — True if enabled flag or non-empty resolved key
  - `async def require_api_key(request: Request, …) -> None` — FastAPI dependency; raises HTTPException 401
- Consumes: `Config.api.auth`, env `MELTR_API_KEY` / `LOGFORGE_API_KEY`

- [ ] **Step 1: Write failing tests** in `tests/test_api_auth.py`

```python
import os
from unittest.mock import patch

from meltr.core.config import AuthConfig, APIConfig, create_default_config
from meltr.api.auth import auth_required, resolve_api_key


def test_auth_required_false_when_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key=None)
    assert auth_required(cfg) is False


def test_auth_required_true_when_env_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "secret")
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key=None)
    assert auth_required(cfg) is True
    assert resolve_api_key(cfg) == "secret"
```

- [ ] **Step 2: Run tests — expect FAIL (import error)**

```bash
pytest tests/test_api_auth.py -v --cov-fail-under=0
```

- [ ] **Step 3: Implement `src/meltr/api/auth.py`**

```python
"""API key authentication for the management API."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import HTTPException, Request, status

from meltr.core.config import Config


def resolve_api_key(config: Config) -> Optional[str]:
    env = (os.getenv("MELTR_API_KEY") or os.getenv("LOGFORGE_API_KEY") or "").strip()
    if env:
        return env
    key = (config.api.auth.key or "").strip() if config.api.auth.key else ""
    return key or None


def auth_required(config: Config) -> bool:
    if config.api.auth.enabled:
        return True
    return resolve_api_key(config) is not None


async def require_api_key(request: Request) -> None:
    server = request.app.state.server
    config: Config = server.config
    if not auth_required(config):
        return
    expected = resolve_api_key(config)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API auth enabled but no API key configured",
        )
    auth = request.headers.get("Authorization", "")
    token = ""
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

Also: in `APIServer.start` / init path, if `config.api.auth.enabled` and `resolve_api_key` is None → log error and refuse to start API (raise or exit). Wire that in Task 1.2 if start lives in `server.py` / `service.py`.

- [ ] **Step 4: Tests pass**

```bash
pytest tests/test_api_auth.py -v --cov-fail-under=0
```

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/v2-phase-1-auth
git add src/meltr/api/auth.py tests/test_api_auth.py src/meltr/core/config.py
git commit -m "feat: add API key auth helpers (key-implies-auth)"
```

---

### Task 1.2: Wire auth into FastAPI routes + integration tests

**Files:**
- Modify: `src/meltr/api/server.py` (metrics endpoint uses `require_api_key`)
- Modify: `src/meltr/api/endpoints/entities.py`, `generators.py`, `templates.py`, `health.py` (`/status` protected; `/health` not)
- Modify: `tests/test_api_auth.py` (TestClient cases)

**Interfaces:**
- Consumes: `require_api_key` from Task 1.1
- Produces: protected management API

- [ ] **Step 1: Add TestClient tests** (extend `tests/test_api_auth.py`)

Use FastAPI `TestClient` against `APIServer(config).app` with `app.state.server` set; monkeypatch env key; assert `/api/health` 200 without header; `/api/entities` 401 without; 200 with Bearer.

- [ ] **Step 2: Run — expect FAIL (401 not enforced)**

- [ ] **Step 3: Wire dependency**

On routers that must be protected, add:

```python
from meltr.api.auth import require_api_key

router = APIRouter(..., dependencies=[Depends(require_api_key)])
```

For `health.py`: keep `/health` without the dependency; put `dependencies=[Depends(require_api_key)]` on `/status` and other non-public routes individually if they share the same router — split routers if needed so `/health` stays public.

In `server.py` metrics route, call `await require_api_key(request)` at the start of the handler (or wrap with a dependency).

- [ ] **Step 4: Tests pass; commit**

```bash
git commit -am "feat: enforce Bearer auth on management API"
```

- [ ] **Step 5: README auth section + PR**

Document key-implies-auth; open/merge Phase 1 PR.

---

## Phase 2 — Template preview

### Task 2.1: Preview API + CLI

**Files:**
- Modify: `src/meltr/api/endpoints/templates.py`
- Modify: `src/meltr/cli/templates.py`
- Create: `tests/test_template_preview.py`
- Create fixture under `tests/fixtures/templates/...` if none suitable exists

**Interfaces:**
- Produces: `POST /api/templates/{template_id}/preview` body `PreviewRequest(count: int = 1)` → `{template_id, count, events: list[str]}`
- Produces: `meltr templates preview <id> [--count N]`

- [ ] **Step 1: Failing test** — call preview helper / TestClient; expect 404 or missing route.

- [ ] **Step 2: Implement endpoint**

```python
from pydantic import BaseModel, Field

class PreviewRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=20)

@router.post("/{template_id:path}/preview", dependencies=[Depends(require_api_key)])
async def preview_template(
    template_id: str,
    body: PreviewRequest,
    request: Request,
    cache: Annotated[TemplateCache, Depends(get_template_cache)],
) -> dict:
    info = cache.get_template(template_id)
    if not info:
        raise HTTPException(404, detail=f"Template not found: {template_id}")
    registry = request.app.state.registry  # ensure engine sets this
    from meltr.templates.renderer import TemplateRenderer
    renderer = TemplateRenderer(registry)
    events = []
    for _ in range(body.count):
        events.append(renderer.render_path(info.path))  # use actual renderer API
    return {"template_id": template_id, "count": body.count, "events": events}
```

Verify real method names on `TemplateRenderer` / loader before coding — adapt to existing `render` signature in `src/meltr/templates/renderer.py`.

- [ ] **Step 3: CLI command** calling API client `POST .../preview`.

- [ ] **Step 4: Tests pass; commit; PR `feat/v2-phase-2-preview`**

---

## Phase 3 — Community update detection

### Task 3.1: Version fields + updates endpoint

**Files:**
- Modify: `src/meltr/api/endpoints/templates.py` (fill `version` / `remote_version`)
- Create: `src/meltr/api/endpoints/community.py`
- Modify: `src/meltr/api/server.py` (include community router)
- Modify: `src/meltr/cli/templates.py` (`check-updates` command if not already equivalent)
- Create: `tests/test_community_updates.py`

**Interfaces:**
- Produces: `GET /api/community/updates` → `{ "updates": [ { "product_id", "local_version", "remote_version", ... } ] }`
- Consumes: `meltr.community.client` + `compare_versions`

- [ ] **Step 1: Failing test** with mocked community client returning newer remote version.

- [ ] **Step 2: Implement** lookup of local package versions from installed template metadata; compare to remote collection versions; list only stale.

- [ ] **Step 3: Wire list/get template responses to same helpers (no more hard-coded `None` for version when metadata has it).

- [ ] **Step 4: CLI `meltr templates check-updates` prints stale list; exit 0 if none, 0 with list if some (or exit 1 if any stale — pick **exit 0 always on success**, print count; document).

- [ ] **Step 5: Commit; PR `feat/v2-phase-3-updates`**

---

## Phase 4 — Pipelines

### Task 4.1: Config models

**Files:**
- Modify: `src/meltr/core/config.py`

**Interfaces:**
- Produces:

```python
class ScheduleConfig(BaseModel):
    mode: str = Field(default="continuous")  # continuous | window | burst
    days: Optional[List[str]] = None
    time: Optional[str] = None  # "09:00-17:00"
    timezone: Optional[str] = None
    count: Optional[int] = None  # burst
    duration: Optional[str] = None  # burst, e.g. "5m"

class PipelineStreamConfig(BaseModel):
    template: str
    weight: float = 1.0

class PipelineConfig(BaseModel):
    name: str
    enabled: bool = True
    timezone: Optional[str] = None
    outputs: List[str]
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    streams: List[PipelineStreamConfig]

# on Config:
pipelines: List[PipelineConfig] = Field(default_factory=list)
# on GeneratorConfig:
schedule: Optional[ScheduleConfig] = None
```

- [ ] **Step 1: Unit test** round-trip YAML load with a sample pipeline.
- [ ] **Step 2: Implement models + validation** (`mode` enum-like check).
- [ ] **Step 3: Commit**

---

### Task 4.2: Schedule gate module

**Files:**
- Create: `src/meltr/core/schedule.py`
- Create: `tests/test_schedule.py`

**Interfaces:**
- Produces:

```python
@dataclass
class ScheduleDecision:
    emit: bool
    reason: str  # "ok" | "outside_window" | "burst_complete"

def evaluate_schedule(
    schedule: ScheduleConfig,
    *,
    now: datetime,
    events_emitted: int,
    started_at: datetime,
) -> ScheduleDecision: ...
```

- [ ] **Step 1: Tests** for continuous always emit; window inside/outside; burst by count.
- [ ] **Step 2: Implement** with `zoneinfo.ZoneInfo`.
- [ ] **Step 3: Commit**

---

### Task 4.3: Pipeline orchestrator + engine + API/CLI

**Files:**
- Create: `src/meltr/core/pipeline.py`
- Modify: `src/meltr/core/engine.py`
- Modify: `src/meltr/core/generator.py` (call `evaluate_schedule` each tick; skip emit if not `emit`; stop on burst_complete)
- Create: `src/meltr/api/endpoints/pipelines.py`
- Create: `src/meltr/cli/pipelines.py`
- Modify: `src/meltr/cli/main.py`, `src/meltr/api/server.py`
- Create: `tests/test_pipelines.py`

**Interfaces:**
- `Pipeline` holds name, config, list of child generator names, shared schedule
- Engine methods: `start_pipeline`, `stop_pipeline`, `list_pipelines`
- API: `GET/POST ...` list/start/stop mirroring generators endpoints style

- [ ] **Step 1: Integration test** — two streams, file outputs, assert both files gain lines (use tmp_path + short burst schedule).
- [ ] **Step 2: Implement orchestrator** creating Generators with templates from streams and shared outputs; register under engine.
- [ ] **Step 3: Wire API/CLI**
- [ ] **Step 4: Commit; PR `feat/v2-phase-4-pipelines`**

---

## Phase 5 — Schedule polish

### Task 5.1: Window + burst coverage on generators and pipelines

**Files:**
- Modify: `tests/test_schedule.py`, `tests/test_pipelines.py`
- Modify: docs snippets in README

**Interfaces:** Consumes Task 4.2–4.3

- [ ] **Step 1: Add tests** — generator with `schedule.mode=window` emits 0 outside window (freeze time); burst auto-stops pipeline status STOPPED.
- [ ] **Step 2: Fix gaps found**
- [ ] **Step 3: Commit; PR `feat/v2-phase-5-schedule`**

---

## Phase 6 — Docs, coverage, release

### Task 6.1: Glossary + README + destination presets

**Files:**
- Create: `docs/ecosystem-glossary.md`
- Modify: `README.md`
- Optional: `src/meltr/cli/outputs.py` or extend config CLI with `outputs test` — config validate + optional `--send` probe

- [ ] **Step 1: Write glossary** (pipeline, stream, schedule, generator, MELTR_HOME, LogForge legacy).
- [ ] **Step 2: Expand README** per dogfood checklist.
- [ ] **Step 3: Commit**

---

### Task 6.2: Raise coverage to ≥60%

**Files:**
- Modify: `pyproject.toml` → `--cov-fail-under=60`
- Add tests for uncovered auth/schedule/pipeline/preview paths as needed

- [ ] **Step 1: `pytest --cov-fail-under=0` and note %**
- [ ] **Step 2: Add targeted tests until ≥60%**
- [ ] **Step 3: Set fail-under 60; CI green**
- [ ] **Step 4: Commit; PR `feat/v2-phase-6-docs-coverage`**

---

### Task 6.3: Release v2.0.0 + PyPI

**Files:**
- Modify: `src/meltr/__init__.py` → `__version__ = "2.0.0"`

- [ ] **Step 1: Ensure dogfood checklist items 1–8, 10 pass locally**
- [ ] **Step 2: Merge Phase 6 PR**
- [ ] **Step 3: Tag and push**

```bash
git checkout main && git pull origin main
# version commit if not already 2.0.0
git tag -a v2.0.0 -m "MELTr v2.0.0"
git push origin v2.0.0
```

- [ ] **Step 4: Confirm GitHub Release + PyPI `meltr==2.0.0`**
- [ ] **Step 5: Verify**

```bash
python3.11 -m venv /tmp/meltr-verify && /tmp/meltr-verify/bin/pip install meltr==2.0.0
/tmp/meltr-verify/bin/meltr --version
```

Expected: `MELTr 2.0.0`

---

## Spec coverage checklist

| Spec section | Tasks |
|--------------|-------|
| §1 Delivery & CI | 0.1, 0.2 |
| §2 Auth | 1.1, 1.2 |
| §3 Preview + updates | 2.1, 3.1 |
| §4 Pipelines + schedule | 4.1–4.3, 5.1 |
| §5 Docs / coverage / release | 6.1–6.3 |
| Early `2.0.0a1` | 0.2 Step 5 (human) |
| Dogfood acceptance | 6.3 |

## Self-review notes

- No TBD placeholders in task steps; renderer method name must be verified against `renderer.py` at implement time (call out in Task 2.1).
- `cov-fail-under` currently 80 in pyproject — Phase 0 must change it first or local/CI stays red.
- Health vs status split may require router dependency refactor — Task 1.2 owns it.
