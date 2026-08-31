# LogForge hard cut (MELTr production prep)

**Date:** 2026-08-30  
**Status:** Approved  
**Repo:** MELTr  
**Goal:** Remove all LogForge product/compat surface from MELTr before first production release (`v2.0.0`).

## Decisions (locked)

| Decision | Choice |
|----------|--------|
| Compat policy | **Hard cut** — no silent `LOGFORGE_*` / `logforge` CLI / legacy path discovery |
| Community registry default | `https://meltr.ftsc.cloud/api/v1` |
| `logforge.io` | Dropped from MELTr defaults and docs (UI migrates to new domain later) |
| Sibling repo names | Docs may name unfinished migrate targets only as needed; prefer “Enterprise edition” / “community templates repo” in user-facing copy |

## Out of scope

- Renaming LogForge-Templates / Templates-UI / Enterprise repos  
- Deploying or DNS for `meltr.ftsc.cloud` (assumed available or overridden via config/env when not)  
- Migrating old user YAML (`pipelines`, `logforge_metadata`) — already deleted in generators-only overhaul  

## Removals

### Packaging / CLI
- Remove `logforge` console-script entry from `pyproject.toml`
- No docs or help text that mention a `logforge` binary

### Environment
- Remove all `LOGFORGE_*` reads (HOME, API_KEY, TELEMETRY, LOG_FILE, LOG_LEVEL, COMMUNITY_API_URL aliases if any)
- Only `MELTR_*` (and documented non-branded vars) remain

### Code identifiers
- Delete `get_logforge_home` alias; call `get_meltr_home` everywhere
- Rename `LogForgeService` → `MeltrService` (update imports/tests)
- Path resolver: drop `LOGFORGE_HOME` substitution and leading `logforge/` path segment; keep `MELTR_HOME` / `meltr/`
- Paths discovery: drop `~/.logforge`, `/opt/logforge`, `/var/lib/logforge`, and `logforge` binary heuristics

### Docs / examples / PyPI
- Strip “Formerly LogForge”, compat blurbs, `journalctl -u logforge`, `/var/lib/logforge`, etc. from README, DEPLOYMENT, TROUBLESHOOTING, docs/, examples/, release notes, glossary, NOTICE, AGENTS.md as applicable
- Examples and defaults use `${MELTR_HOME}` and `community_api_url: https://meltr.ftsc.cloud/api/v1`
- PyPI long description (from README) must contain no LogForge product branding after publish

### Tests
- Delete or rewrite tests that only assert LogForge compat (env fallback, cmdline `logforge`, legacy dirs)
- Point telemetry/community fixtures at the new default URL (or injectable mocks)

## Registry URL

| Surface | Value |
|---------|--------|
| Config default `templates.community_api_url` | `https://meltr.ftsc.cloud/api/v1` |
| Override | Config field and/or `MELTR_COMMUNITY_API_URL` (existing CLI flags) |
| Docs wording | “community registry” — do not say LogForge |

Until Templates-UI is pointed at this domain, community install/search may fail unless the operator overrides the URL or the new host is live. That is accepted for the production cut.

## String gate

- Retarget allowlist: **empty of LogForge product strings** (or delete allowlist entries wholesale)
- Allowed only if unavoidable: none expected after cut — hostname `meltr.ftsc.cloud` is fine
- Gate should fail CI on any `logforge` / `LogForge` / `LOGFORGE` / `logforge_metadata` hit in scanned paths (except the gate script’s own pattern/docs if needed)
- Rename gate files optionally later (`check_legacy_strings.py`); not required for this cut

## Acceptance criteria

1. `rg -i 'logforge'` over `src tests examples docs README.md DEPLOYMENT.md TROUBLESHOOTING.md` (excluding `docs/superpowers/`) returns **no** product/compat hits; historical superpowers specs may retain the word until cleaned separately  
2. `python scripts/check_logforge_strings.py` exits 0 with a minimal/empty allowlist  
3. `meltr --help` works; no `logforge` entry point in the wheel  
4. Default config / `create_default_config` uses `https://meltr.ftsc.cloud/api/v1`  
5. CI green on the purge branch  
6. Ready to tag `v2.0.0` and publish to PyPI without LogForge in the project description  

## Implementation approach

Single PR on branch `chore/logforge-hard-cut`: mechanical rename/remove + doc scrub + default URL change + allowlist wipe + test updates. No migration shims.
