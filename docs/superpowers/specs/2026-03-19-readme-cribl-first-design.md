# README Cribl-first and development setup (design spec)

**Goal:** Operator-facing README leads with the **official Linux `.tar.gz`** (unpack, `PATH`, `init`, `start`), not `pip install logforge`. Contributor setup is centralized in **`docs/development/setup.md`** with dependencies grounded in **`pyproject.toml`**.

**Decisions**

| Item | Choice |
|------|--------|
| Production quick start | GitHub Releases `.tar.gz` + links to [linux-tarball.md](../../deployment/linux-tarball.md) / [linux-single-instance.md](../../deployment/linux-single-instance.md). |
| pip / wheel | Mentioned as **other install options**, not the first step. |
| Development | [setup.md](../../development/setup.md): `requires-python`, runtime + dev dependency lists, `pip install -e ".[dev]"`, optional `uv`, pytest/ruff/black/mypy. |
| DEPLOYMENT intro | Neutral: tarball vs wheel vs editable source. |
| TROUBLESHOOTING | Unchanged where `pip` is a technical fix. |

**Out of scope:** Removing `pip` from upgrade/how-to sections in DEPLOYMENT that describe real wheel/source workflows.
