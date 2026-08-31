# AGENTS.md

## Spec & parity

| Field | Value |
|-------|-------|
| **SPEC_SOURCE** | Live FastAPI/OpenAPI (`/docs`), entity import schema, and CLI + YAML behavior under `MELTR_HOME`. Greenfield features: the approved plan doc is the spec. |
| **PARITY_MODE** | When pointed at a reference (OpenAPI, design doc, legacy MELTr path), that reference defines "done." Audit DONE / PARTIAL / MISSING; do not invent behavior. Name deliberate deviations in the PR. |
| **PLANNING_MODE** | No external reference → decompose with explicit acceptance criteria; those criteria define done. |

Global review gate: `~/.cursor/rules/review-gate.mdc` (≥2 specialists by risk).

## Project overview

**MELTr** is a single-package Python application (FastAPI + Typer) for synthetic log generation. State lives under `MELTR_HOME` (defaults to `~/.meltr`).

Canonical roadmap: `docs/superpowers/plans/2026-08-29-meltr-v2-completion.md`

## Local Cursor skills

Under `.cursor/skills/` (use when relevant):

| Skill | Use for |
|-------|---------|
| `creating-pr` | Feature/fix PRs into `main` |
| `writing-commit-messages` | Conventional commits |
| `reviewing-code` | Diff reviews (Python/FastAPI) |
| `auditing-security` | Security pass / OWASP-style audit |
| `security-baseline` | FTSC CI/secret-scan/Dependabot baseline |
| `grill-with-docs` | Stress-test plans against domain language |
| `suggesting-cursor-rules` / `suggesting-cursor-hooks` | Encode repeated corrections / checks |
| `writing-guidelines` | Prose/docs voice review |

## Development setup

```
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

Cloud Agent bootstrap (idempotent): `bash .cursor/install.sh` then `bash .cursor/start.sh` (API on `127.0.0.1:8080`). See `.cursor/environment.json`.

## Local vs Cloud Agent vs CI

| Layer | Use for | Not for |
|-------|---------|---------|
| **Local** (worktrees + IDE) | Fast iteration, multi-repo, interactive `meltr config edit`, debugging | Assuming a clean install layout |
| **Cloud Agent** | Clean-room install/runtime smoke after packaging, paths, init, or pre-release | Replacing CI; every small push |
| **CI** | Merge gate: lint, pytest, string gate, secrets | Deep manual flows / live registry |

**Shared smoke (same commands everywhere):**

```bash
./scripts/smoke.sh
```

Uses a disposable `MELTR_HOME` under `/tmp` by default. Reuse a home with `MELTR_HOME=… ./scripts/smoke.sh`. Keep temp home + API with `SMOKE_KEEP=1`. Skip the live registry pull with `SMOKE_SKIP_COMMUNITY=1`. When `https://meltr.ftsc.cloud/api/v1/health` (or `MELTR_COMMUNITY_API_URL`) is reachable, smoke also browses, searches, installs `apache`, and compares against the catalog.

| Change type | Local | Cloud Agent | CI |
|-------------|-------|-------------|-----|
| Small fix | focused pytest | skip | PR checks |
| Config / CLI / engine | pytest + optional smoke | optional | PR checks |
| Packaging / paths / init | optional smoke | **preferred** | PR checks |
| Pre-tag release | smoke | **smoke on `main`** | green on `main` |
| Community registry | override `MELTR_COMMUNITY_API_URL` if needed | only if host reachable | N/A |

Do not invent different smoke steps per environment. Prefer this script.

## Key commands

| Task | Command |
|------|---------|
| Lint | `ruff check .` |
| Format check | `black --check .` |
| Type check | `mypy src` |
| Tests | `pytest` |
| Runtime smoke | `./scripts/smoke.sh` |
| Start service | `meltr start` |
| Legacy string gate | `python scripts/check_logforge_strings.py` |

## Non-obvious caveats

- `pytest` may exit non-zero due to `--cov-fail-under` until coverage climbs (see v2.0 plan).
- Community registry default: `https://meltr.ftsc.cloud/api/v1` (override with `MELTR_COMMUNITY_API_URL`).
- LLM template authoring is **not** in this OSS product (Enterprise-only).
- Cloud Agent `start.sh` is best-effort (exits 0 even if health is slow); `scripts/smoke.sh` **fails** if health never comes up.
- Only create git commits when explicitly asked.
