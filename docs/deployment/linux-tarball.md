# Linux `.tar.gz` bundle (official release)

The GitHub **Release** for each tag includes **`logforge-{version}-linux-x86_64.tar.gz`**: a self-contained tree with an embedded CPython build (from [python-build-standalone](https://github.com/astral-sh/python-build-standalone)), LogForge installed under `app/lib/python3.11/site-packages`, and a portable `app/bin/logforge` launcher. No `pip` or system Python is required on the target host. Extracting the archive creates a top-level **`logforge/`** directory (not a version-suffixed path).

For **pip/venv install** from PyPI or a wheel, see [linux-single-instance.md](linux-single-instance.md).

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **OS** | **Linux x86_64**, **glibc**-based (typical RHEL / Debian / Ubuntu family). **musl** (e.g. Alpine Linux) is **not** supported for this bundle. Portability is primarily **glibc version** and **CPU architecture**; kernel 4.x / 5.x / 6.x is a common test matrix, not a hard gate. |
| **CPU** | x86_64 only for this artifact (aarch64 may be added later). |
| **Disk** | Unpacked size is larger than a wheel-only install (embedded Python + dependencies). |
| **Filesystem** | Keep the unpacked product tree on **one mount** (same idea as [Cribl single-instance](https://docs.cribl.io/stream/deploy-single-instance/)); put large file outputs outside `LOGFORGE_HOME` via `config.yaml` if needed. |

## Install

1. Download **`logforge-{version}-linux-x86_64.tar.gz`** and verify the checksum from `checksums.txt` on the release.

2. Unpack under `/opt` (or another fixed path):

```bash
sudo tar xzf logforge-{version}-linux-x86_64.tar.gz -C /opt
```

3. Put the CLI on `PATH`:

```bash
export PATH=/opt/logforge/app/bin:$PATH
# Optional: sudo ln -sf /opt/logforge/app/bin/logforge /usr/local/bin/logforge
```

4. Initialize and run (same as other install methods):

```bash
export LOGFORGE_HOME=/opt/logforge/data
logforge init --force
logforge start
```

`get_logforge_home()` treats binaries under `/opt/logforge` as an install layout and defaults `LOGFORGE_HOME` to `/opt/logforge/data` when unset—see [`paths.py`](../../src/logforge/core/paths.py).

## systemd

The unit should invoke the **bundled** CLI:

```bash
sudo logforge service install \
  --user logmgr --group logmgr \
  --home /var/lib/logforge \
  --binary /opt/logforge/app/bin/logforge
```

Or install data under `/opt/logforge/data` and run as a non-`logmgr` user if your policy allows.

## Open source artifacts in the bundle

- **`LICENSE`** — LogForge (Apache-2.0).
- **`NOTICE`** — Project attribution (Apache-style; when present in the bundle).
- **`PYTHON_PSF_LICENSE.txt`** — CPython / PSF (embedded runtime under `python/`).
- **`THIRD_PARTY_NOTICES.txt`** — Python dependency licenses (generated at build time).
- **`README-TARBALL.md`** — Short copy inside the archive.

## See also

- [DEPLOYMENT.md](../../DEPLOYMENT.md) — upgrades
- [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)
- [building-linux-tarball.md](../development/building-linux-tarball.md) — how the bundle is produced
