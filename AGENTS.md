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

## Key commands

| Task | Command |
|------|---------|
| Lint | `ruff check .` |
| Format check | `black --check .` |
| Type check | `mypy src` |
| Tests | `pytest` |
| Start service | `meltr start` |

## Non-obvious caveats

- `pytest` may exit non-zero due to `--cov-fail-under` until coverage climbs (see v2.0 plan).
- Community registry default: `https://meltr.ftsc.cloud/api/v1`.
- LLM template authoring is **not** in this OSS product (Enterprise-only).
- Only create git commits when explicitly asked.
