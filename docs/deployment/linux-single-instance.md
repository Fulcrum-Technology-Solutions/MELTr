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
| **Python** | 3.10 or newer. |
| **Network ports** | Default management API listens on **8080** (`127.0.0.1`). Ensure this port is free, or change `api.host` / `api.port` in `config.yaml` after init. Generators and outputs use the same process; no separate “data plane” port unless you configure HTTP/TCP/syslog outputs to listen locally. Prefer loopback; see [SECURITY.md](../../SECURITY.md) before binding to `0.0.0.0` or placing a reverse proxy in front. |
| **Tools** | `pip`, `venv` (typically via `python3 -m venv`). Optional: `curl` or `httpie` for API checks. |

## Install on Linux (recommended: `/opt/meltr`)

1. Create an install root and virtual environment:

```bash
sudo mkdir -p /opt/meltr
sudo chown "$USER:$USER" /opt/meltr
cd /opt/meltr
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install meltr
```

Or install from a wheel: `pip install /path/to/meltr-*.whl`.

2. Put `meltr` on your PATH for interactive use (optional but convenient). For the **official tarball**, prefer `sudo /opt/meltr/install.sh` (façade at `/opt/meltr/bin/meltr` + profile.d + thin `/usr/local/bin` wrapper). For this **venv** layout:

```bash
sudo ln -sf /opt/meltr/.venv/bin/meltr /usr/local/bin/meltr
```

(pip entry points use an absolute shebang, so that symlink is safe. Do **not** raw-symlink the tarball’s `app/bin/meltr` — use `install.sh`.)

The [systemd install](../../src/meltr/cli/service.py) logic discovers `/opt/meltr/bin/meltr` (tarball façade), then `app/bin`, then `.venv/bin`.

**Artifact note (pip path):** This section uses a **wheel** installed into a venv under `/opt/meltr`. For the **official `.tar.gz`** (embedded Python, no `pip` on the host), use [linux-tarball.md](linux-tarball.md). In both cases the mental model is “software tree under `/opt` + `MELTR_HOME` state directory.”

## Filesystem layout

- **Install tree:** Keep `/opt/meltr` (application + `.venv`) on a **single filesystem/mount**, as you would for other `/opt` products. Avoid splitting the venv across devices.
- **State directory (`MELTR_HOME`):** Config, entities, templates, and runtime files (`run/`, etc.) live here. When the `meltr` binary resolves under `/opt/meltr`, the default is **`/opt/meltr`** (product root). Application logs default to **`/opt/meltr/logs/`** (see [`paths.py`](../../src/meltr/core/paths.py)).
- **Large or external data:** Put high-volume **file outputs** or other large paths **outside** `MELTR_HOME` by configuring explicit paths in `config.yaml` (same idea as keeping heavy queues outside a product’s install tree).

```bash
export MELTR_HOME=/opt/meltr
```

## Initialize state

Create `config.yaml`, `entities.yaml`, and directory structure under `MELTR_HOME`:

```bash
cd /opt/meltr
source .venv/bin/activate
export MELTR_HOME=/opt/meltr
meltr init --force
```

- As a **normal user** (non-root), `init` defaults to **not** creating the `meltr` system user; you do not need `--no-create-user` unless you explicitly passed `--create-user` earlier.
- To prepare **`/var/lib/meltr`** for **systemd** (owned by `meltr`), create the directory and run init as root **or** as a user that can write there; see **Run as a systemd service** below.

## Run

### Foreground (API + engine)

`meltr start` is equivalent to `meltr api start` and matches what the systemd unit runs.

```bash
export MELTR_HOME=/opt/meltr   # if not already set
source /opt/meltr/.venv/bin/activate
meltr start
```

To stop a manually started instance (foreground or background): **`meltr stop`** with the same `MELTR_HOME`—equivalent to **`meltr api stop`**.

### Systemd service (production)

1. Initialize a data directory owned by the service user (default **`meltr`**). Pick **one** layout:

**A — Bundle default (recommended):** same `MELTR_HOME` as a local run, **`/opt/meltr`** (single tree under the product directory).

```bash
sudo mkdir -p /opt/meltr
sudo meltr init --directory /opt/meltr --user meltr --group meltr --force
```

**B — State under `/var/lib`:** pass `--home /var/lib/meltr` on install.

```bash
sudo mkdir -p /var/lib/meltr
sudo meltr init --directory /var/lib/meltr --user meltr --group meltr --force
```

2. Install the unit (uses `WorkingDirectory`, `MELTR_HOME`, `ExecStart=<meltr> api start`, journal logging, `LimitNOFILE=65536`). `service install` reloads systemd.

```bash
# A: omit --home → unit sets MELTR_HOME=/opt/meltr; prefers /opt/meltr/bin/meltr
sudo /opt/meltr/bin/meltr service install --user meltr --group meltr

# B: explicit state directory
# sudo meltr service install --user meltr --group meltr --home /var/lib/meltr --binary /opt/meltr/bin/meltr

sudo systemctl enable --now meltr
```

3. Check status:

```bash
sudo systemctl status meltr
meltr service status
sudo journalctl -u meltr -n 50 --no-pager
```

Use `meltr service stop` / `meltr service start` / `meltr service restart` as needed.

## Non-root and evaluation (laptop / lab)

For quick evaluation without `/opt` or systemd:

```bash
pip install meltr   # or pipx install meltr
meltr init --force  # uses ~/.meltr by default when MELTR_HOME is unset
meltr start
```

Override the data directory:

```bash
export MELTR_HOME=/path/you/can/write
meltr init --force
```

## See also

- [DEPLOYMENT.md](../../DEPLOYMENT.md) — upgrades and data retention
- [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md) — binary path, permissions, systemd
- [README.md](../../README.md) — features, development setup, configuration reference
