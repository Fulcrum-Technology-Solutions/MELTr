# Cribl-style CLI install UX — Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox syntax.

**Goal:** Symlink-safe launcher, `/opt/meltr/bin/meltr` façade, `install.sh` + `service install` PATH helpers, absolute systemd `ExecStart`.

**Architecture:** Fix tarball wrappers in `build_linux_tgz.sh`; add shared Python helpers for profile.d + `/usr/local/bin`; teach `paths.py` / `service.py` about the façade; update docs.

**Tech Stack:** POSIX sh, Typer CLI, pytest

**Spec:** `docs/superpowers/specs/2026-08-31-cribl-style-cli-install-design.md`

## Global Constraints

- Tarball is Linux x86_64 only (`readlink -f` OK in wrappers)
- systemd `ExecStart` always absolute; prefer façade
- Uninstall does not remove PATH helpers
- Thin wrapper at `/usr/local/bin`, not raw symlink to `app/bin/meltr`

---

### Task 1: paths — façade + `app/bin` recognition + tests

- [ ] Add failing tests for `…/meltr/bin/meltr` and `…/meltr/app/bin/meltr` (incl. non-opt if we add app/bin rule)
- [ ] Update `get_data_home_from_install_binary` as needed
- [ ] Run `pytest tests/test_paths.py -q`

### Task 2: PATH helpers module + service install

- [ ] Add `src/meltr/cli/path_helpers.py` (write profile.d + wrapper; injectable paths for tests)
- [ ] Wire into `service_install`; prefer façade for ExecStart; discover `/opt/meltr/bin/meltr` first
- [ ] Tests for helper writers + unit content preference
- [ ] Run focused pytest

### Task 3: Tarball build — launcher, façade, install.sh

- [ ] Symlink-safe `app/bin/meltr` in `scripts/build_linux_tgz.sh`
- [ ] Emit `bin/meltr` façade + `install.sh`
- [ ] Refresh `README-TARBALL.md` template in build script
- [ ] Optional: small shell self-check script or document manual verify

### Task 4: Docs + spec status

- [ ] Update linux-tarball.md, linux-single-instance.md, TROUBLESHOOTING.md, DEPLOYMENT.md as needed
- [ ] Mark design spec Approved

### Task 5: Verify

- [ ] `pytest tests/test_paths.py tests/test_path_helpers.py tests/test_service_path_helpers.py -q` (names as created)
- [ ] Review gate: bugbot + silent-failure on error paths in helpers
