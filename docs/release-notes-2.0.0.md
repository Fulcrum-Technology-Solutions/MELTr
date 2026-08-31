# MELTr 2.0.0 Release Notes

First stable release of **MELTr** (formerly MELTr OSS). Install with `pip install meltr==2.0.0`.

## Highlights

- **Rebrand to MELTr** — PyPI package `meltr`, CLI `meltr`, config under `MELTR_HOME` (default `~/.meltr`). Legacy MELTr env aliases and CLI entry points are removed.
- **API key auth** — Key-implies-auth: set `MELTR_API_KEY` (or `MELTR_API_KEY`) to protect the management API; health/metrics paths configurable.
- **Template preview** — `meltr templates preview <id>` renders sample events without starting a generator.
- **Community update detection** — `meltr templates check-updates` compares installed community templates against the registry (detection only; no auto-upgrade).
- **Generators-only model** — One template per generator, each pointing at one or more outputs; run multiple generators for multiple templates.
- **Schedule gates** — Optional on generators: `continuous` (default), `window` (tz-aware days/time), and `burst` (count or duration, auto-stop).
- **CI & coverage** — GitHub Actions CI with an honest coverage gate on `src/meltr` (no whole-file omits); PyPI publish workflow via Trusted Publisher (OIDC). Phase 6 interim coverage is below the 60% target — see README for the measured gate and tracked follow-up to reach 60% without omits.
- **Docs** — Expanded README, ecosystem glossary, and destination preset guides.

## Not in OSS

Fleet/worker distribution, LLM-assisted template authoring, and advanced scenario/correlation features remain Enterprise or future work. See the [v2 design spec](superpowers/specs/2026-08-29-meltr-v2-design.md).

## Upgrade

```bash
pip install -U meltr==2.0.0
meltr init --force   # if migrating from MELTr layout
```

Community templates sync from [meltr.ftsc.cloud](https://meltr.ftsc.cloud) by default.
