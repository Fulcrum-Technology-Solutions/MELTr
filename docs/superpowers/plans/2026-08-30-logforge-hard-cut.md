# LogForge Hard Cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or implement task-by-task). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all LogForge product/compat surface from MELTr and set community registry default to `https://meltr.ftsc.cloud/api/v1` before `v2.0.0`.

**Architecture:** Single mechanical purge PR — rename/remove identifiers, drop env aliases and legacy paths, scrub docs/examples, wipe string-gate allowlist, retarget defaults/tests. No migration shims.

**Tech Stack:** Python 3.10+, Typer/FastAPI package `meltr`, pytest, existing `scripts/check_logforge_strings.py`.

**Spec:** `docs/superpowers/specs/2026-08-30-logforge-hard-cut-design.md`

## Global Constraints

- Hard cut: no `LOGFORGE_*`, no `logforge` console script, no `get_logforge_home`, no `LogForgeService`
- Default community API: `https://meltr.ftsc.cloud/api/v1`
- No `logforge.io` in defaults/docs/examples
- String gate must pass with empty/minimal allowlist (no LogForge product strings)
- Do not mass-edit `docs/superpowers/` historical plans except this plan/spec

---

## File map

| Area | Primary files |
|------|----------------|
| Packaging | `pyproject.toml` |
| Paths / env | `src/meltr/core/paths.py`, `src/meltr/utils/logging.py`, `src/meltr/api/auth.py`, `src/meltr/telemetry/client.py`, `src/meltr/outputs/path_resolver.py` |
| Service | `src/meltr/service.py` → `MeltrService`; `src/meltr/cli/api.py`, `src/meltr/cli/service.py` |
| Config default URL | `src/meltr/core/config.py` |
| Call sites | All `get_logforge_home` imports under `src/` / `tests/` |
| Docs/examples | `README.md`, `DEPLOYMENT.md`, `TROUBLESHOOTING.md`, `docs/**`, `examples/**`, `AGENTS.md`, `NOTICE` |
| Gate | `scripts/logforge_string_allowlist.txt` |
| Tests | `tests/test_paths.py`, `tests/test_api_auth.py`, `tests/test_telemetry.py`, others with logforge hits |

---

### Task 1: Defaults + packaging + core renames

**Files:** `pyproject.toml`, `src/meltr/core/config.py`, `src/meltr/core/paths.py`, `src/meltr/service.py`, callers

- [ ] Remove `logforge =` console script from `pyproject.toml`
- [ ] Change `community_api_url` default to `https://meltr.ftsc.cloud/api/v1`
- [ ] Remove `get_logforge_home = get_meltr_home`; replace all call sites with `get_meltr_home`
- [ ] Rename `LogForgeService` → `MeltrService`
- [ ] Strip `LOGFORGE_*` fallbacks from auth, telemetry, logging, path_resolver, paths discovery
- [ ] Commit

### Task 2: Tests

- [ ] Rewrite/delete LogForge-compat tests (env fallback, `logforge` cmdline, legacy dirs)
- [ ] Update URL fixtures to `meltr.ftsc.cloud`
- [ ] `pytest` focused suites green
- [ ] Commit

### Task 3: Docs + examples

- [ ] Scrub README, DEPLOYMENT, TROUBLESHOOTING, docs/, examples/, release notes, glossary, NOTICE, AGENTS.md
- [ ] Commit

### Task 4: String gate + verification

- [ ] Empty allowlist (header comment only explaining hard cut)
- [ ] `python scripts/check_logforge_strings.py` → OK
- [ ] Full `pytest` (note cov-fail-under=50); fix regressions from purge
- [ ] Commit + open PR

---

## Done when

Acceptance criteria in the design spec are met; PR ready to merge to `main` before tagging `v2.0.0`.
