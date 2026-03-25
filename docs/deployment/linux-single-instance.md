# Linux single-instance deployment

This guide follows the same operator flow as common on-prem data-plane products: **prerequisites → install software under a fixed root → filesystem rules → initialize state → run** (foreground or systemd).

**Choose an install path:**

| Method | When to use |
|--------|-------------|
| **[Official `.tar.gz` bundle](linux-tarball.md)** | Air-gapped hosts, no `pip` on servers, or Cribl-style “unpack under `/opt`” operations. **Linux x86_64**; includes embedded Python. |
| **pip + venv** (below) | Development, PyPI installs, or when you already standardize on Python tooling. |

For **upgrades, backups, and rollback**, see [DEPLOYMENT.md](../../DEPLOYMENT.md).

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **OS** | Linux x86_64 or ARM64 with a supported Python (see README). |
| **Python** | 3.9 or newer. |
| **Network ports** | Default management API listens on **8080** (`127.0.0.1`). Ensure this port is free, or change `api.host` / `api.port` in `config.yaml` after init. Generators and outputs use the same process; no separate “data plane” port unless you configure HTTP/TCP/syslog outputs to listen locally. |
| **Tools** | `pip`, `venv` (typically via `python3 -m venv`). Optional: `curl` or `httpie` for API checks. |

## Install on Linux (recommended: `/opt/logforge`)

1. Create an install root and virtual environment:

```bash
sudo mkdir -p /opt/logforge
sudo chown "$USER:$USER" /opt/logforge
cd /opt/logforge
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install logforge
```

Or install from a wheel: `pip install /path/to/logforge-*.whl`.

2. Put `logforge` on your PATH for interactive use (optional but convenient):

```bash
sudo ln -sf /opt/logforge/.venv/bin/logforge /usr/local/bin/logforge
```

The [systemd install](../../src/logforge/cli/service.py) logic also discovers `/opt/logforge/.venv/bin/logforge` when installing the unit.

**Artifact note (pip path):** This section uses a **wheel** installed into a venv under `/opt/logforge`. For the **official `.tar.gz`** (embedded Python, no `pip` on the host), use [linux-tarball.md](linux-tarball.md). In both cases the mental model is “software tree under `/opt` + `LOGFORGE_HOME` state directory.”

## Filesystem layout

- **Install tree:** Keep `/opt/logforge` (application + `.venv`) on a **single filesystem/mount**, as you would for other `/opt` products. Avoid splitting the venv across devices.
- **State directory (`LOGFORGE_HOME`):** Config, entities, templates, local outputs, and logs live here. When the `logforge` binary resolves under `/opt/logforge`, the default data directory is **`/opt/logforge/data`** (see `get_logforge_home()` in [`paths.py`](../../src/logforge/core/paths.py)).
- **Large or external data:** Put high-volume **file outputs** or other large paths **outside** `LOGFORGE_HOME` by configuring explicit paths in `config.yaml` (same idea as keeping heavy queues outside a product’s install tree).

```bash
export LOGFORGE_HOME=/opt/logforge/data
```

## Initialize state

Create `config.yaml`, `entities.yaml`, and directory structure under `LOGFORGE_HOME`:

```bash
cd /opt/logforge
source .venv/bin/activate
export LOGFORGE_HOME=/opt/logforge/data
logforge init --force
```

- As a **normal user** (non-root), `init` defaults to **not** creating the `logmgr` system user; you do not need `--no-create-user` unless you explicitly passed `--create-user` earlier.
- To prepare **`/var/lib/logforge`** for **systemd** (owned by `logmgr`), create the directory and run init as root **or** as a user that can write there; see **Run as a systemd service** below.

## Run

### Foreground (API + engine)

`logforge start` is equivalent to `logforge api start` and matches what the systemd unit runs.

```bash
export LOGFORGE_HOME=/opt/logforge/data   # if not already set
source /opt/logforge/.venv/bin/activate
logforge start
```

To stop a manually started instance (foreground or background): **`logforge stop`** with the same `LOGFORGE_HOME`—equivalent to **`logforge api stop`**.

### Systemd service (production)

1. Ensure data directory exists and is owned by the service user (default **`logmgr`**):

```bash
sudo mkdir -p /var/lib/logforge
sudo logforge init --directory /var/lib/logforge --user logmgr --group logmgr --force
# Or: sudo chown logmgr:logmgr /var/lib/logforge && sudo -u logmgr env LOGFORGE_HOME=/var/lib/logforge /opt/logforge/.venv/bin/logforge init --directory /var/lib/logforge --force
```

2. Install the unit (uses `WorkingDirectory`, `LOGFORGE_HOME`, `ExecStart=<logforge> api start`, journal logging, `LimitNOFILE=65536`):

```bash
sudo /opt/logforge/.venv/bin/logforge service install --user logmgr --group logmgr --home /var/lib/logforge --binary /opt/logforge/.venv/bin/logforge
sudo systemctl daemon-reload
sudo systemctl enable --now logforge
```

3. Check status:

```bash
sudo systemctl status logforge
logforge service status
sudo journalctl -u logforge -n 50 --no-pager
```

Use `logforge service stop` / `logforge service start` / `logforge service restart` as needed.

## Non-root and evaluation (laptop / lab)

For quick evaluation without `/opt` or systemd:

```bash
pip install logforge   # or pipx install logforge
logforge init --force  # uses ~/.logforge by default when LOGFORGE_HOME is unset
logforge start
```

Override the data directory:

```bash
export LOGFORGE_HOME=/path/you/can/write
logforge init --force
```

## See also

- [DEPLOYMENT.md](../../DEPLOYMENT.md) — upgrades and data retention
- [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md) — binary path, permissions, systemd
- [README.md](../../README.md) — features, development setup, configuration reference
