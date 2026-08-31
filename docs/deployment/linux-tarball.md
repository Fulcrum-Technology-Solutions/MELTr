# Linux `.tar.gz` bundle (official release)

The GitHub **Release** for each tag includes **`meltr-{version}-linux-x86_64.tar.gz`**: a self-contained tree with an embedded CPython build (from [python-build-standalone](https://github.com/astral-sh/python-build-standalone)), MELTr installed under `app/lib/python3.11/site-packages`, and a portable `app/bin/meltr` launcher. No `pip` or system Python is required on the target host. Extracting the archive creates a top-level **`meltr/`** directory (not a version-suffixed path).

For **pip/venv install** from PyPI or a wheel, see [linux-single-instance.md](linux-single-instance.md).

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **OS** | **Linux x86_64**, **glibc**-based (typical RHEL / Debian / Ubuntu family). **musl** (e.g. Alpine Linux) is **not** supported for this bundle. Portability is primarily **glibc version** and **CPU architecture**; kernel 4.x / 5.x / 6.x is a common test matrix, not a hard gate. |
| **CPU** | x86_64 only for this artifact (aarch64 may be added later). |
| **Disk** | Unpacked size is larger than a wheel-only install (embedded Python + dependencies). |
| **Filesystem** | Keep the unpacked product tree on **one mount** (same idea as [Cribl single-instance](https://docs.cribl.io/stream/deploy-single-instance/)); put large file outputs outside `MELTR_HOME` via `config.yaml` if needed. |

## Install

1. Download **`meltr-{version}-linux-x86_64.tar.gz`** and verify the checksum from `checksums.txt` on the release.

2. Unpack under `/opt` (or another fixed path):

```bash
sudo tar xzf meltr-{version}-linux-x86_64.tar.gz -C /opt
```

3. Put the CLI on `PATH`:

```bash
export PATH=/opt/meltr/app/bin:$PATH
# Optional: sudo ln -sf /opt/meltr/app/bin/meltr /usr/local/bin/meltr
```

4. Initialize and run (same as other install methods):

```bash
export MELTR_HOME=/opt/meltr
meltr init --force
meltr start
```

`get_meltr_home()` treats binaries under `/opt/meltr` as an install layout and defaults `MELTR_HOME` to **`/opt/meltr`** when unset—see [`paths.py`](../../src/meltr/core/paths.py).

## Background operation (default)

On POSIX, `meltr start` **daemonizes by default** (Splunk/Cribl-style): it prints the child PID and returns your shell. Application logs default to **`<install_root>/logs`** (e.g. `/opt/meltr/logs/`). Use **`meltr start --foreground`** (`-f`) to keep the process attached for troubleshooting.

**systemd** units use `api start --foreground` so the service manager tracks the main process correctly.

**Stopping a manual start:** use **`meltr stop`** (same `MELTR_HOME` as when you ran `start`); it reads `run/meltr.pid`, sends **SIGTERM**, then **SIGKILL** after `--timeout` if needed. For production, prefer **`systemctl stop meltr`** / `meltr service stop`.

## systemd

The unit should invoke the **bundled** CLI:

```bash
sudo meltr service install \
  --user meltr --group meltr \
  --binary /opt/meltr/app/bin/meltr
```

Omit `--home` to use **`MELTR_HOME=/opt/meltr`**. Use `--home /var/lib/meltr` (or similar) only if policy requires state outside `/opt`.

## Open source artifacts in the bundle

- **`LICENSE`** — MELTr (Apache-2.0).
- **`NOTICE`** — Project attribution (Apache-style; when present in the bundle).
- **`PYTHON_PSF_LICENSE.txt`** — CPython / PSF (embedded runtime under `python/`).
- **`THIRD_PARTY_NOTICES.txt`** — Python dependency licenses (generated at build time).
- **`README-TARBALL.md`** — Short copy inside the archive.

## See also

- [DEPLOYMENT.md](../../DEPLOYMENT.md) — upgrades
- [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)
- [building-linux-tarball.md](../development/building-linux-tarball.md) — how the bundle is produced
