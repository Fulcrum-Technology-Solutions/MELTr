# Cribl / Splunk-UF-style CLI install UX

**Date:** 2026-08-31  
**Status:** Approved  
**Repo:** MELTr  
**Goal:** Make the official Linux tarball feel like Cribl Stream / Splunk Universal Forwarder: stable `<HOME>/bin/meltr`, short `meltr` / `sudo -u meltr meltr` invocations, systemd still on an absolute path.

## Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Tarball launcher | Resolve real script path before computing `ROOT` (symlink-safe) |
| 2 | Product façade | Ship `/opt/meltr/bin/meltr` (stable operator CLI); keep `app/bin/meltr` as implementation launcher |
| 3 | PATH convenience | Tarball `install.sh` **and** `meltr service install` both ensure `/etc/profile.d/meltr.sh` **and** thin `/usr/local/bin/meltr` wrapper (idempotent) |
| 4 | systemd | `ExecStart` always uses the **absolute** product binary (prefer façade if present, else `app/bin`); never rely on PATH in the unit |

## Out of scope

- Changing default `MELTR_HOME` resolution rules (still product root for `/opt/meltr` layout)
- Relocating embedded Python or `app/lib` layout
- Windows / non-glibc / aarch64 tarball
- Auto-adding to sudoers `secure_path` (document `/usr/local/bin` + wrapper instead)
- pip/venv-only installs inventing a fake `/opt/meltr` tree (façade is a **tarball** artifact; venv docs may optionally suggest a manual wrapper)

## Problem

Today operators need:

```bash
sudo -u meltr MELTR_HOME=/opt/meltr /opt/meltr/app/bin/meltr --version
```

Deviations from Cribl/UF:

1. CLI nested under `app/bin/` instead of `<HOME>/bin/`
2. Launcher uses `dirname "$0"` without resolving symlinks → raw `/usr/local/bin` → `app/bin/meltr` breaks
3. PATH / global name is optional and undocumented as a first-class install step
4. Dual stories (tarball vs `.venv/bin`) without a single operator-facing path

## Target operator UX

After unpack + `install.sh` (or after `service install`):

```bash
meltr --version
sudo -u meltr meltr --version
sudo systemctl status meltr   # ExecStart=/opt/meltr/bin/meltr api start --foreground
```

`MELTR_HOME` usually unset for interactive use under `/opt/meltr` (existing `get_meltr_home()` behavior).

## Layout (tarball)

```
/opt/meltr/                 # product root (= default MELTR_HOME)
  bin/meltr                 # NEW — operator façade (documented CLI)
  app/bin/meltr             # implementation launcher (symlink-safe)
  python/                   # embedded CPython (unchanged)
  app/lib/.../site-packages
  install.sh                # NEW — root helper: profile.d + /usr/local/bin
  logs/, config, …          # runtime (unchanged)
```

### `bin/meltr` façade

- Small shell script (or identical relocatable launcher) that **execs** the real launcher under `../app/bin/meltr` after resolving its own directory (symlink-safe).
- Documented as **the** CLI path: `$MELTR_HOME/bin` or `/opt/meltr/bin`.
- `get_bundle_home_from_install_binary` / `paths.py` must treat both `…/bin/meltr` and `…/app/bin/meltr` as bundle layout (product root = parent of `bin` or of `app`).

### `app/bin/meltr` launcher (fix)

Replace:

```sh
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
```

with resolve-then-root (portable POSIX intent; Linux may use `readlink -f`):

1. Resolve `$0` to the real script path (follow symlinks).
2. `ROOT` = parent of `app/` (two levels up from `app/bin/meltr`).
3. Unchanged: set `PYTHONPATH`, `exec` embedded `python -m meltr`.

Acceptance: `ln -sf /opt/meltr/app/bin/meltr /tmp/meltr-link && /tmp/meltr-link --version` works.

## PATH convenience (item 3 — option B)

### Artifacts

| Path | Content |
|------|---------|
| `/etc/profile.d/meltr.sh` | `export PATH="/opt/meltr/bin:${PATH}"` (or detected install root) |
| `/usr/local/bin/meltr` | Thin wrapper: `exec /opt/meltr/bin/meltr "$@"` (absolute path to façade; **not** a raw symlink to `app/bin/meltr`) |

Both are **idempotent** (overwrite with same content OK). Creating them requires root.

### `install.sh` (in tarball root)

- Run after `tar -C /opt -xzf …` (typical: `sudo /opt/meltr/install.sh`).
- Detect install root from script location (symlink-safe).
- Write profile.d + `/usr/local/bin` wrapper pointing at `$ROOT/bin/meltr`.
- Does **not** create systemd unit (that remains `meltr service install`).
- Prints next steps: `meltr init`, `meltr service install`, re-login or `source /etc/profile.d/meltr.sh`.

### `meltr service install`

In addition to writing the unit file:

- Ensure profile.d + `/usr/local/bin` wrapper for the resolved product root (same content as `install.sh`).
- Prefer `ExecStart={façade}` when `$ROOT/bin/meltr` exists; else `$ROOT/app/bin/meltr` / `--binary`.
- Still set `Environment="MELTR_HOME=…"` and absolute `ExecStart` (item 4).
- Non-root: unchanged — refuse with existing root check; PATH helpers are root-only.

### Uninstall

- `meltr service uninstall` continues to remove **only** the unit (existing behavior).
- Spec does **not** require deleting profile.d / `/usr/local/bin/meltr` on uninstall (avoid surprising PATH removal). Document manual cleanup in TROUBLESHOOTING / linux-tarball.md.

## systemd (item 4)

```
ExecStart=/opt/meltr/bin/meltr api start --foreground
Environment="MELTR_HOME=/opt/meltr"
```

- Never `ExecStart=meltr …`.
- `--binary` flag still overrides discovery.
- Discovery order for install without `--binary`: façade `…/bin/meltr` → `…/app/bin/meltr` → existing which/venv heuristics.

## Docs

Update:

- `docs/deployment/linux-tarball.md` — façade path, `install.sh`, no raw symlink to `app/bin/meltr`
- `README-TARBALL.md` (generated in build script) — same quick path
- `docs/deployment/linux-single-instance.md` — align “put on PATH” with façade / wrapper guidance
- `TROUBLESHOOTING.md` — short CLI, sudo secure_path, manual wrapper cleanup
- `DEPLOYMENT.md` — one-line pointer if needed

Operator story:

```bash
sudo tar xzf meltr-*-linux-x86_64.tar.gz -C /opt
sudo /opt/meltr/install.sh
meltr init --force
sudo meltr service install --user meltr --group meltr
```

## Tests / verification

| Check | How |
|-------|-----|
| Symlink-safe `app/bin` launcher | Unit/integration: resolve via symlink; `--version` or import smoke |
| Façade execs real launcher | Build or script test that `bin/meltr` → working CLI |
| Bundle home from façade path | `paths.py` / existing path tests: `/opt/meltr/bin/meltr` → home `/opt/meltr` |
| Service install unit | Assert `ExecStart` absolute; contains `/bin/meltr` or `app/bin/meltr`; `MELTR_HOME` set |
| install.sh / service PATH helpers | Optional: dry-run or temp-root test writing wrapper + profile.d |

CI may keep building the tarball in release workflow; add a job step or script smoke that runs façade `--version` from a temp extract if feasible on ubuntu runners.

## Acceptance criteria

1. After unpack to `/opt/meltr`, `/opt/meltr/bin/meltr --version` works without setting `PATH` or `MELTR_HOME`.
2. Raw symlink to `app/bin/meltr` works (`--version`).
3. `sudo /opt/meltr/install.sh` creates profile.d + `/usr/local/bin/meltr`; thereafter `meltr --version` works in a new login shell (and via absolute `/usr/local/bin/meltr`).
4. `sudo meltr service install …` writes absolute `ExecStart` to façade (or `app/bin` if no façade) and ensures the same PATH helpers.
5. Docs no longer recommend `ln -sf …/app/bin/meltr /usr/local/bin/meltr` without the thin-wrapper caveat (prefer `install.sh` / façade).
6. Existing `get_meltr_home()` / systemd behavior for `/opt/meltr` remains correct.

## Implementation approach

Single feature PR (or two: launcher+façade+paths, then install.sh+service+docs). Prefer one PR if small.

Touch points:

- `scripts/build_linux_tgz.sh` — fix wrapper; emit `bin/meltr`; emit `install.sh`; refresh `README-TARBALL.md`
- `src/meltr/core/paths.py` — recognize `…/bin/meltr` façade as install binary
- `src/meltr/cli/service.py` — PATH helpers + prefer façade for `ExecStart`
- Docs listed above
- Tests under `tests/` for paths + service unit content as practical

## Non-goals / explicit non-changes

- Do not put MELTr’s embedded Python on system `PATH`.
- Do not change default API port, daemonize behavior, or service user name (`meltr`).
