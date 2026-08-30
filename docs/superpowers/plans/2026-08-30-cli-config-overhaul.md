# CLI Config Overhaul + Generators-Only Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove pipelines, make `generators` the only job type (one template → outputs), treat `internal-logs` as a reserved non-removable generator, rename `logforge_metadata` → `meltr_metadata`, and overhaul `meltr config edit` for a continuous-first UX.

**Architecture:** Three vertical slices. Slice 1 changes the config/engine product model. Slice 2 rewrites the interactive config editor around that model. Slice 3 cleans docs and adds a repo string-match allowlist gate. No legacy migrate-on-load paths for removed keys.

**Tech Stack:** Python 3.10+, Pydantic, Typer/Rich CLI, FastAPI, pytest

**Spec:** `docs/superpowers/specs/2026-08-30-cli-config-overhaul-design.md`

## Global Constraints

- Word **outputs** everywhere (not destinations)
- Keep name **generators**; one generator = one template → one or more outputs
- Schedule is secondary; default continuous (omit schedule or `mode: continuous`)
- Reserved generator name exactly `internal-logs` (constant `INTERNAL_LOGS_GENERATOR_NAME`)
- `internal-logs` cannot be removed; only enable/disable + outputs
- No pipelines in code, tests, or product docs
- Metadata JSON key: `meltr_metadata` only
- Pre-prod: no migrate-on-load for `pipelines`, `internal_logs:`, or `logforge_metadata`
- Keep `LOGFORGE_*` / `MELTR_*` env aliases; allowlist them in the string gate
- Prefer `MELTR_*` and `${MELTR_HOME}` in new user-facing copy

---

## File map

| Area | Primary files |
|------|----------------|
| Config model | `src/meltr/core/config.py` |
| Engine | `src/meltr/core/engine.py`, `src/meltr/service.py` |
| Delete | `src/meltr/core/pipeline.py`, `src/meltr/cli/pipelines.py`, `src/meltr/api/endpoints/pipelines.py`, `tests/test_pipelines.py` |
| HTTP metadata | `src/meltr/outputs/http.py`, `docs/deployment/destination-presets.md` |
| Internal logs | `src/meltr/core/internal_log_generator.py` |
| Config menu | `src/meltr/cli/config_editor.py`, `src/meltr/cli/config.py` |
| API mount | `src/meltr/api/server.py`, `src/meltr/cli/main.py` |
| Docs | `README.md`, `docs/ecosystem-glossary.md`, `docs/release-notes-2.0.0.md` |
| String gate | `scripts/check_logforge_strings.py`, `.github/workflows/ci.yml`, `scripts/logforge_string_allowlist.txt` |

---

### Task 1: Config model — drop pipelines & `internal_logs`; inject reserved generator

**Files:**
- Modify: `src/meltr/core/config.py`
- Modify: `src/meltr/core/internal_log_generator.py` (export name constant if not already public)
- Test: `tests/test_config_generators_model.py` (create)

**Interfaces:**
- Consumes: `INTERNAL_LOGS_GENERATOR_NAME = "internal-logs"` from `meltr.core.internal_log_generator`
- Produces:
  - `ensure_internal_logs_generator(config: Config) -> Config` — guarantees reserved entry exists
  - `create_default_config()` includes disabled `internal-logs`
  - No `pipelines`, `PipelineConfig`, `PipelineStreamConfig`, `InternalLogsConfig`, or `internal_logs` on `Config`
  - Reserved generator uses sentinel template `__internal__` (never loaded as Jinja)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config_generators_model.py
from pathlib import Path

from meltr.core.config import Config, GeneratorConfig, create_default_config, ensure_internal_logs_generator
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME


def test_default_config_has_disabled_internal_logs_generator(tmp_path: Path):
    cfg = create_default_config(tmp_path)
    assert not hasattr(cfg, "pipelines") or "pipelines" not in Config.model_fields
    assert "internal_logs" not in Config.model_fields
    names = [g.name for g in cfg.generators]
    assert names.count(INTERNAL_LOGS_GENERATOR_NAME) == 1
    il = next(g for g in cfg.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME)
    assert il.enabled is False
    assert il.outputs == []
    assert il.template == "__internal__"


def test_ensure_injects_internal_logs_when_missing(tmp_path: Path):
    cfg = create_default_config(tmp_path)
    cfg.generators = [g for g in cfg.generators if g.name != INTERNAL_LOGS_GENERATOR_NAME]
    cfg = ensure_internal_logs_generator(cfg)
    assert any(g.name == INTERNAL_LOGS_GENERATOR_NAME for g in cfg.generators)


def test_ensure_does_not_duplicate_internal_logs(tmp_path: Path):
    cfg = create_default_config(tmp_path)
    cfg = ensure_internal_logs_generator(cfg)
    cfg = ensure_internal_logs_generator(cfg)
    assert sum(1 for g in cfg.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME) == 1
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd "/Users/johnowen/GitHub Repositories/work/MELTr"
source .venv/bin/activate  # or project venv
pytest tests/test_config_generators_model.py -v --no-cov
```

Expected: FAIL (`ensure_internal_logs_generator` missing and/or `pipelines` still present)

- [ ] **Step 3: Implement model changes**

In `src/meltr/core/config.py`:
1. Delete `PipelineStreamConfig`, `PipelineConfig`, `InternalLogsConfig`
2. Remove `pipelines` and `internal_logs` from `Config`
3. Add:

```python
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME

INTERNAL_LOGS_TEMPLATE_SENTINEL = "__internal__"


def ensure_internal_logs_generator(config: Config) -> Config:
    """Ensure the reserved internal-logs generator exists (disabled by default)."""
    if any(g.name == INTERNAL_LOGS_GENERATOR_NAME for g in config.generators):
        return config
    config.generators.insert(
        0,
        GeneratorConfig(
            name=INTERNAL_LOGS_GENERATOR_NAME,
            template=INTERNAL_LOGS_TEMPLATE_SENTINEL,
            enabled=False,
            outputs=[],
        ),
    )
    return config
```

4. Call `ensure_internal_logs_generator` at end of `load_config` (after `Config(**data)`) and inside `create_default_config` (generators list starts with reserved entry or via ensure)
5. Update `create_default_config` to drop `pipelines=` / `internal_logs=`

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_config_generators_model.py -v --no-cov
```

- [ ] **Step 5: Commit**

```bash
git add src/meltr/core/config.py tests/test_config_generators_model.py
git commit -m "feat(config): generators-only model with reserved internal-logs"
```

---

### Task 2: Engine + service — remove Pipeline; wire internal-logs from generators

**Files:**
- Modify: `src/meltr/core/engine.py`
- Modify: `src/meltr/service.py`
- Delete: `src/meltr/core/pipeline.py`
- Test: `tests/test_engine_internal_logs_generator.py` (create) + fix any broken imports in existing tests

**Interfaces:**
- Consumes: `ensure_internal_logs_generator`, `INTERNAL_LOGS_GENERATOR_NAME`, `GeneratorConfig`
- Produces: Engine with no `_pipelines` / `load_pipelines_from_config` / `list_pipelines` / start|stop pipeline APIs; `load_generators_from_config` skips creating a Jinja `Generator` for `internal-logs` and uses `InternalLogGenerator` when that entry is enabled

- [ ] **Step 1: Write failing test**

```python
# tests/test_engine_internal_logs_generator.py
from meltr.core.config import GeneratorConfig, create_default_config
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME


def test_enabled_internal_logs_uses_internal_generator(tmp_path, monkeypatch):
    # Minimal: build config with internal-logs enabled + one file output,
    # construct Engine (or call the load path), assert get_generator(INTERNAL_LOGS_GENERATOR_NAME)
    # is InternalLogGenerator and no Pipeline import remains.
    from meltr.core.internal_log_generator import InternalLogGenerator
    # Implementation detail: follow existing engine test patterns in tests/test_engine_*.py
    assert InternalLogGenerator is not None
```

Flesh this out against the existing engine fixture style in `tests/test_engine_output_def_live_reload.py` (copy the smallest setup that constructs an Engine).

- [ ] **Step 2: Run — expect FAIL** (pipelines still referenced or internal_logs block still required)

- [ ] **Step 3: Implement**

1. Delete `src/meltr/core/pipeline.py`
2. In `engine.py`: remove all Pipeline imports, `_pipelines`, pipeline methods; in generator load loop:

```python
if gen_config.name == INTERNAL_LOGS_GENERATOR_NAME:
    if not gen_config.enabled:
        continue
    # build output handlers from gen_config.outputs; start InternalLogGenerator
    continue
# else normal TemplateLoader Generator path — skip if template == "__internal__"
```

3. Sync-on-reload: derive internal log generator from the reserved `GeneratorConfig` entry (not `config.internal_logs`)
4. In `service.py`: remove pipeline start loop; use generators-only startup

- [ ] **Step 4: Fix compile/import fallout**

```bash
pytest tests/test_engine_internal_logs_generator.py tests/test_internal_log_generator.py -v --no-cov
python -c "from meltr.core.engine import Engine; from meltr.core import pipeline"  # second import must fail
```

- [ ] **Step 5: Commit**

```bash
git add src/meltr/core/engine.py src/meltr/service.py src/meltr/core/pipeline.py tests/
git commit -m "feat(engine): drop pipelines; internal-logs from generators list"
```

---

### Task 3: Remove CLI/API pipeline surface; fix callers

**Files:**
- Delete: `src/meltr/cli/pipelines.py`, `src/meltr/api/endpoints/pipelines.py`, `tests/test_pipelines.py`
- Modify: `src/meltr/cli/main.py`, `src/meltr/api/server.py`
- Modify: any remaining imports (`tests/test_api_auth.py`, `tests/test_phase6_*.py`, examples)
- Modify: `examples/config.production-http.yaml` (remove `pipelines:` sections)

**Interfaces:**
- Produces: no `meltr pipelines` command; no `/api/.../pipelines` router

- [ ] **Step 1: Grep and list hits**

```bash
rg -n "pipelines|Pipeline" src tests examples README.md docs --glob '!docs/superpowers/**'
```

- [ ] **Step 2: Delete modules and unmount**

In `main.py` remove `pipelines` typer. In `server.py` remove pipelines router include.

- [ ] **Step 3: Fix tests/examples that referenced pipelines** — rewrite as multi-generator fixtures or delete obsolete cases

- [ ] **Step 4: Run**

```bash
pytest tests/ -q --no-cov -k "not phase6"  # then full suite as needed
pytest tests/test_pipelines.py -v --no-cov  # expect collection error / file gone — OK
```

- [ ] **Step 5: Commit**

```bash
git commit -am "chore: remove pipelines CLI/API and tests"
```

---

### Task 4: Rename `logforge_metadata` → `meltr_metadata`

**Files:**
- Modify: `src/meltr/outputs/http.py` (`_wrap_event_with_metadata`)
- Modify: `src/meltr/cli/config_editor.py` (prompts mentioning `logforge_metadata`)
- Modify: `docs/deployment/destination-presets.md`
- Modify: tests asserting metadata key (`tests/test_config.py`, `tests/test_phase6_final.py`, etc.)

**Interfaces:**
- Produces: wrapped HTTP payload `{"event": ..., "meltr_metadata": {...}}`

- [ ] **Step 1: Failing test**

```python
def test_wrap_event_uses_meltr_metadata_key():
    # Construct HTTPOutputHandler with include_metadata True (follow existing http tests)
    # assert "meltr_metadata" in wrapped and "logforge_metadata" not in wrapped
    ...
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Replace key + docs/prompts**

```python
return {"event": event, "meltr_metadata": metadata}
```

- [ ] **Step 4: `rg logforge_metadata` → zero hits in `src/` and `tests/`

- [ ] **Step 5: Commit**

```bash
git commit -am "refactor: rename logforge_metadata to meltr_metadata"
```

---

### Task 5: Config editor — rebrand, `--section` save, path defaults

**Files:**
- Modify: `src/meltr/cli/config_editor.py` (`config_editor`, `_show_main_menu`, `_save_config`, `_create_file_output` defaults)
- Test: `tests/test_config_editor_section_save.py` (create) — mock Confirm/Prompt where needed

**Interfaces:**
- Produces: after `--section` edit, prompt `Save changes?` and call `_save_config` on yes

- [ ] **Step 1: Failing test for section save behavior**

```python
from unittest.mock import patch
from meltr.cli import config_editor as ce

def test_section_edit_offers_save(tmp_path, monkeypatch):
    # patch load_config, _edit_outputs_section (return config), Confirm.ask True, _save_config
    with patch.object(ce, "load_config", return_value=...), \
         patch.object(ce, "_edit_outputs_section", side_effect=lambda c: c), \
         patch.object(ce, "_save_config", return_value=True) as save, \
         patch("meltr.cli.config_editor.Confirm") as confirm:
        confirm.ask.return_value = True
        ce.config_editor(section="outputs", edit_existing=True)
        save.assert_called_once()
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

After section branch in `config_editor`, if `section` was set:

```python
if Confirm.ask("\nSave changes?", default=True):
    _save_config(config)
return
```

Replace title `LogForge Configuration Editor` → `MELTr Configuration Editor`.  
Replace `logforge config reload` → `meltr config reload`.  
Default file path `${LOGFORGE_HOME}/...` → `${MELTR_HOME}/...`.  
Remove unused `get_logforge_home()` call at L255 if still dead.

- [ ] **Step 4: PASS + Commit**

```bash
git commit -am "fix(cli): MELTr branding and save after config --section"
```

---

### Task 6: Config editor — generators UX (continuous-first, schedule secondary, internal-logs rules)

**Files:**
- Modify: `src/meltr/cli/config_editor.py` (`_edit_generators_section`, add/edit/remove flows)
- Optionally split: `src/meltr/cli/config_editor_generators.py` if the section grows past ~400 new lines
- Test: `tests/test_config_editor_generators.py` (create)

**Interfaces:**
- Consumes: `INTERNAL_LOGS_GENERATOR_NAME`
- Produces:
  - Add generator: template → outputs → enabled (no schedule prompts)
  - Menu action “Set schedule…” for non-reserved generators
  - Remove: refuse if name == `internal-logs`
  - Edit reserved: enable + outputs only

- [ ] **Step 1: Tests**

```python
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME
from meltr.core.config import create_default_config, GeneratorConfig

def test_cannot_remove_internal_logs(tmp_path):
    cfg = create_default_config(tmp_path)
    # call internal helper once extracted, e.g. _remove_generator(cfg, INTERNAL_LOGS_GENERATOR_NAME)
    # expect generators still contain internal-logs
    ...

def test_add_generator_omits_schedule_by_default(...):
    # after mocked prompts, resulting GeneratorConfig.schedule is None
    ...
```

- [ ] **Step 2: Implement menu options**

Generators submenu sketch:
1. Add generator  
2. Edit generator  
3. Remove generator  
4. Set schedule…  
5. Back  

On remove/edit: if target is `internal-logs`, block remove; edit path only toggles `enabled` + `outputs`.

- [ ] **Step 3: Wire schedule editor** to existing `ScheduleConfig` fields (`mode`, window/burst fields in `src/meltr/core/config.py`) — prompt only from action 4

- [ ] **Step 4: Run targeted tests + Commit**

```bash
pytest tests/test_config_editor_generators.py tests/test_config_editor_section_save.py -v --no-cov
git commit -am "feat(cli): continuous-first generators; protect internal-logs"
```

---

### Task 7: Docs + glossary alignment

**Files:**
- Modify: `docs/ecosystem-glossary.md` — remove Stream/Pipeline product rows (or mark N/A); generators-only
- Modify: `README.md` — remove pipelines as primary; describe multiple generators
- Modify: `docs/release-notes-2.0.0.md` — drop pipeline highlight; note generators-only
- Modify: `docs/deployment/destination-presets.md` — `meltr_metadata`
- Modify: `DEPLOYMENT.md` — `meltr` commands (not `logforge`) where touched

- [ ] **Step 1: Edit docs to match spec mental model**
- [ ] **Step 2: `rg -n "pipeline|Pipeline|logforge_metadata" README.md docs DEPLOYMENT.md`** — only historical “formerly LogForge” / allowlisted notes remain
- [ ] **Step 3: Commit**

```bash
git commit -am "docs: generators-only model; meltr_metadata"
```

---

### Task 8: LogForge / pipelines string-match gate

**Files:**
- Create: `scripts/logforge_string_allowlist.txt`
- Create: `scripts/check_logforge_strings.py`
- Modify: `.github/workflows/ci.yml` — add step on test job or lint job

**Allowlist (initial):**
```
# patterns or path:line rules — one per line
LOGFORGE_HOME
LOGFORGE_API_KEY
LOGFORGE_API_URL
LOGFORGE_TELEMETRY
LOGFORGE_LOG_LEVEL
get_logforge_home
# docs historical
formerly LogForge
```

Script behavior:
- Ripgrep `logforge|LogForge|LOGFORGE|logforge_metadata|\bpipelines\b|\bPipeline\b` over `src tests examples docs README.md DEPLOYMENT.md scripts` excluding `docs/superpowers/` and allowlisted matches
- Exit 1 on unexpected hits

- [ ] **Step 1: Write script + allowlist; run locally until green**

```bash
python scripts/check_logforge_strings.py
```

- [ ] **Step 2: Add CI step**

```yaml
- name: Legacy string gate
  run: python scripts/check_logforge_strings.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/check_logforge_strings.py scripts/logforge_string_allowlist.txt .github/workflows/ci.yml
git commit -m "ci: gate leftover logforge/pipeline product strings"
```

---

### Task 9: Full verification

- [ ] **Step 1: Run full pytest**

```bash
pytest -q
```

- [ ] **Step 2: Manual smoke (or document for human)**

```bash
meltr init --force
meltr config edit   # title MELTr; generators list shows internal-logs
meltr config edit --section outputs  # prompts save
```

- [ ] **Step 3: String gate green**

```bash
python scripts/check_logforge_strings.py
```

- [ ] **Step 4: Final commit if fixes needed; open PR for the slice stack or whole overhaul**

---

## Spec coverage check

| Spec item | Task |
|-----------|------|
| Delete pipelines end-to-end | 2, 3 |
| No legacy migrate/error for pipelines | Global + 1–3 |
| Reserved `internal-logs`, non-removable | 1, 2, 6 |
| Default disabled internal-logs | 1 |
| `meltr_metadata` | 4 |
| Config menu continuous-first + schedule secondary | 6 |
| `--section` save + MELTr branding + MELTR_HOME | 5 |
| Outputs wording | 5–7 |
| Docs | 7 |
| String-match allowlist gate | 8 |
| Keep LOGFORGE_* env aliases | 8 allowlist |

## Placeholder scan

No TBD/TODO steps; commands and code sketches are concrete. Engine test in Task 2 must be completed against existing fixture patterns during execution (do not leave assert-only stub).
