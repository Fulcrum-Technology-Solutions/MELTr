# MELTr 2.0.0 Release Notes

First stable release of **MELTr** (formerly LogForge OSS). Install with `pip install meltr==2.0.0`.

## Highlights

- **Rebrand to MELTr** — PyPI package `meltr`, CLI `meltr`, config under `MELTR_HOME` (default `~/.meltr`). `LOGFORGE_*` env vars remain supported for compatibility.
- **API key auth** — Key-implies-auth: set `MELTR_API_KEY` (or `LOGFORGE_API_KEY`) to protect the management API; health/metrics paths configurable.
- **Template preview** — `meltr templates preview <id>` renders sample events without starting a generator.
- **Community update detection** — `meltr templates check-updates` compares installed community templates against the registry (detection only; no auto-upgrade).
- **Multi-template pipelines** — Orchestrate ≥2 template streams into shared outputs (`streams[].weight` is reserved in config but not yet applied; all streams run at equal rate).
- **Schedule gates** — `continuous` (default), `window` (tz-aware days/time), and `burst` (count or duration, auto-stop) on generators and pipelines.
- **CI & coverage** — GitHub Actions CI with an honest coverage gate on `src/meltr` (no whole-file omits); PyPI publish workflow via Trusted Publisher (OIDC). Phase 6 interim coverage is below the 60% target — see README for the measured gate and tracked follow-up to reach 60% without omits.
- **Docs** — Expanded README, ecosystem glossary, and destination preset guides.

## Not in OSS

Fleet/worker distribution, LLM-assisted template authoring, and advanced scenario/correlation features remain Enterprise or future work. See the [v2 design spec](superpowers/specs/2026-08-29-meltr-v2-design.md).

## Upgrade

```bash
pip install -U meltr==2.0.0
meltr init --force   # if migrating from LogForge layout
```

Community templates continue to sync from [logforge.io](https://logforge.io) during the transition.
