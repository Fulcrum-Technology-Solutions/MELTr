# MELTr Service Troubleshooting Guide

**Linux single-instance install and layout:** [docs/deployment/linux-single-instance.md](docs/deployment/linux-single-instance.md).

## Installation paths

- **Wheel install:** The `meltr` binary is typically in the active virtualenv’s `bin/` or in `/usr/local/bin` / `/usr/bin`. Config and data live under **MELTR_HOME** (default: `~/.meltr` for interactive users without a bundle layout).
- **Official `/opt/meltr` bundle:** Operator CLI is **`/opt/meltr/bin/meltr`**. Run `sudo /opt/meltr/install.sh` (or `meltr service install`) for `/etc/profile.d/meltr.sh` and a thin `/usr/local/bin/meltr` wrapper. Default **`MELTR_HOME` is `/opt/meltr`**; `service install` without `--home` sets that in the unit. **`/var/lib/meltr`** is only used when you pass **`--home /var/lib/meltr`** (or when no bundle layout applies and the process falls back as root).
- **Service user:** The default service user is **meltr**. The unit sets `User=meltr`, `Group=meltr`, and `Environment="MELTR_HOME=…"` to match **`--home`** or the bundle default. `ExecStart` is always an absolute path (never bare `meltr`).
- **Log files:** For the bundled layout under `/opt/meltr`, application logs default to **`/opt/meltr/logs/meltr.log`** (with rotation), independent of `MELTR_HOME`. Other installs fall back to `MELTR_HOME/logs/meltr.log`. Operators can set **`MELTR_LOG_FILE`** in the environment (e.g. systemd unit or `systemctl edit`) to override. The systemd unit also sends stdout/stderr to the journal.

### `meltr: command not found` after tarball unpack

```bash
sudo /opt/meltr/install.sh
source /etc/profile.d/meltr.sh
# or: /usr/local/bin/meltr --version
# or: /opt/meltr/bin/meltr --version
```

If `sudo meltr` fails but `/usr/local/bin/meltr` works, sudo’s `secure_path` may omit `/usr/local/bin` — call the absolute wrapper or adjust sudoers.

### Cleaning PATH helpers after uninstall

`meltr service uninstall` removes only the unit. To remove helpers:

```bash
sudo rm -f /etc/profile.d/meltr.sh /usr/local/bin/meltr
```

### Wrong mount or split filesystem

If **`MELTR_HOME`** or **`/opt/meltr`** spans multiple mounts (e.g. bind mounts inside the venv or data dir), you can see confusing permission or I/O errors. Keep the **application venv** under one mount (e.g. all of `/opt/meltr`) and put **large file outputs** on separate paths via `config.yaml` instead of splitting the default tree across devices.

## Quick Diagnosis Commands

### 1. Check Systemd Journal Logs (Most Important)
```bash
# View recent logs
sudo journalctl -u meltr -n 50 --no-pager

# Follow logs in real-time
sudo journalctl -u meltr -f

# View logs with timestamps
sudo journalctl -u meltr --since "5 minutes ago" --no-pager

# View full error details
sudo journalctl -u meltr -n 100 --no-pager | grep -i error
```

### 2. Check Service Status
```bash
# Status (no root required)
meltr service status
# or
systemctl status meltr --no-pager

# Check if service file exists
cat /etc/systemd/system/meltr.service
```

### 3. Verify Installation
```bash
# Binary location (venv or /usr/local/bin when installed from wheel)
which meltr
meltr --version
meltr service status
```

### 4. Check MELTR_HOME and Permissions
```bash
echo $MELTR_HOME

# Common locations
ls -la /var/lib/meltr/ 2>/dev/null || ls -la ~/.meltr/ 2>/dev/null || ls -la ./.meltr/ 2>/dev/null

# Config and log file
ls -la /var/lib/meltr/config.yaml 2>/dev/null
ls -la /var/lib/meltr/logs/meltr.log 2>/dev/null
```

### 5. Test Manual Execution
```bash
# As service user (meltr)
sudo -u meltr meltr api start

# Or run directly to see errors
meltr api start
```

### 6. Check User and Permissions
```bash
id meltr 2>/dev/null || echo "meltr user does not exist"
grep -E "^User=|^Group=" /etc/systemd/system/meltr.service
ls -la /var/lib/meltr/
```

### 7. Validate Configuration
```bash
meltr config validate
meltr config show
```

### 8. Check Dependencies
```bash
python3 --version
pip list | grep -E "fastapi|typer|pydantic"
python3 -c "import meltr; print('OK')"
```

### 9. Check File System and Paths
```bash
grep WorkingDirectory /etc/systemd/system/meltr.service
grep -E "ExecStart|WorkingDirectory|Environment" /etc/systemd/system/meltr.service
df -h /var/lib/meltr
```

### 10. Test with Debug Output
```bash
sudo -u meltr PYTHONUNBUFFERED=1 meltr api start
python3 -v -m meltr api start 2>&1 | head -50
```

## Common Issues and Solutions

### Issue: "ModuleNotFoundError" or Import Errors
**Solution:**
- Reinstall the wheel or install from source in development mode: `pip install -e .` from the project root.

### Issue: "Permission denied" errors
**Solution:**
- Ensure MELTR_HOME (e.g. `/var/lib/meltr`) is owned by the service user:
  ```bash
  sudo chown -R meltr:meltr /var/lib/meltr
  ```

### Issue: "Config file not found"
**Solution:**
- Run init. As a normal user: `meltr init --directory /var/lib/meltr --force` only works if you can write that path; otherwise use `sudo` or init as `meltr` after `chown`.
  ```bash
  sudo meltr init --directory /var/lib/meltr --user meltr --group meltr --force
  # If meltr exists and the tree is writable as meltr:
  sudo -u meltr env MELTR_HOME=/var/lib/meltr meltr init --directory /var/lib/meltr --force
  ```

### Issue: "MELTR_HOME not set correctly"
**Solution:**
- Ensure the systemd unit sets MELTR_HOME. Reinstall the service with explicit home:
  ```bash
  sudo meltr service install --home /var/lib/meltr --user meltr
  ```
  Or edit the unit and add `Environment="MELTR_HOME=/var/lib/meltr"`, then `sudo systemctl daemon-reload`.

## Viewing HTTP Output Errors

HTTP output errors can be viewed in multiple ways:

### 1. Main Log File (Primary Location)

The main application log file is under MELTR_HOME by default:
```yaml
logging:
  file: ${MELTR_HOME}/logs/meltr.log
  level: INFO  # Use DEBUG for more detailed logs
```

**View HTTP-specific errors:**
```bash
# View HTTP output errors in log file
tail -f ${MELTR_HOME}/meltr.log | grep -i "http output"

# View all HTTP output related messages
grep -i "meltr.outputs.http" ${MELTR_HOME}/meltr.log

# View only errors and warnings from HTTP handler
grep -E "ERROR|WARNING.*http output" ${MELTR_HOME}/meltr.log

# View connection failures
grep -i "connection failed\|connection error\|timeout" ${MELTR_HOME}/meltr.log

# View authentication failures
grep -i "authentication failed\|401\|403" ${MELTR_HOME}/meltr.log

# View retry attempts
grep -i "retry attempt" ${MELTR_HOME}/meltr.log

# View recent HTTP errors (last 50 lines)
tail -n 50 ${MELTR_HOME}/meltr.log | grep -i "http output"
```

### 2. Systemd Journal (If Running as Service)

```bash
# View HTTP output errors in journal
sudo journalctl -u meltr | grep -i "http output"

# Follow HTTP errors in real-time
sudo journalctl -u meltr -f | grep -i "http output"

# View only HTTP errors and warnings
sudo journalctl -u meltr -n 100 --no-pager | grep -E "ERROR|WARNING.*http output"

# View connection failures
sudo journalctl -u meltr | grep -iE "connection failed|connection error|timeout"

# View HTTP initialization messages
sudo journalctl -u meltr | grep -i "http output.*initialized"
```

### 3. Generator Status Command (Quick Overview)

```bash
# View generator status with output handler details
meltr generators status <generator-name>

# Example output shows:
# - Output handler health status (healthy/degraded/failed)
# - Events sent/failed counts
# - Buffered events
# - Last error message
# - Average response time
# - Last success/failure times
```

**Example output:**
```
Generator: paloalto-wildfire-threats
  State: RUNNING
  Outputs: http-api-bearer
  
  Output Status:
    http-api-bearer (http): DEGRADED
      Events Sent: 1,245
      Events Failed: 15
      Batches: 15 sent, 3 failed
      Buffered Events: 45
      Avg Response Time: 245.5ms
      Last Error: Connection timeout after 30s
      Last Success: 2025-11-28T21:29:45Z
      Last Failure: 2025-11-28T21:30:20Z
```

### 4. Console Output (If Running in Foreground)

If you run MELTr directly (not as a service):
```bash
# Run in foreground to see all logs
meltr api start

# Or with environment variable to see HTTP debug info
MELTR_LOG_LEVEL=DEBUG meltr api start
```

### 5. Log Levels for HTTP Debugging

**INFO level (default)** shows:
- HTTP handler initialization
- Successful batch sends (with latency)
- HTTP errors (4xx, 5xx) with status codes
- Connection failures
- Timeout errors
- Authentication failures
- Retry attempts
- Recovery messages

**DEBUG level** adds:
- Connection attempt details
- Request headers (sanitized)
- Batch buffer status
- Periodic statistics

**To enable DEBUG level:**
```yaml
# In config.yaml
logging:
  level: DEBUG  # Change from INFO to DEBUG
```

Or set environment variable:
```bash
export MELTR_LOG_LEVEL=DEBUG
meltr api start
```

### 6. Real-Time Monitoring

```bash
# Monitor HTTP output errors in real-time from log file
tail -f ${MELTR_HOME}/meltr.log | grep --line-buffered -i "http output"

# Monitor with color highlighting (if you have ccze installed)
tail -f ${MELTR_HOME}/meltr.log | grep --line-buffered -i "http output" | ccze -A

# Monitor via journalctl
sudo journalctl -u meltr -f | grep --line-buffered -i "http output"
```

### 7. Common HTTP Error Messages

**Connection Errors:**
```
ERROR - HTTP output 'http-api-bearer': Connection failed: ConnectionError - Failed to establish connection
```

**Timeout Errors:**
```
ERROR - HTTP output 'http-api-bearer': Request timeout after 30s
```

**HTTP Errors (4xx/5xx):**
```
WARNING - HTTP output 'http-api-bearer': HTTP 401 client error: Unauthorized
WARNING - HTTP output 'http-api-bearer': HTTP 503 server error: Service Unavailable
```

**Authentication Failures:**
```
ERROR - HTTP output 'http-api-bearer': Authentication failed: HTTP 401 Unauthorized
```

**Retry Messages:**
```
WARNING - HTTP output 'http-api-bearer': Retry attempt 1/∞ in 5.0s - ConnectionError: ...
```

**Recovery Messages:**
```
INFO - HTTP output 'http-api-bearer': Recovered after 3 retry attempts, flushed 150 buffered events
```

**Buffer Warnings:**
```
WARNING - HTTP output 'http-api-bearer': Buffer is 8500/10000 (85.0% full)
```

### 8. Quick Diagnostic Commands

```bash
# Check if HTTP handler is working
meltr generators status <generator-name> | grep -A 10 "Output Status"

# Check for recent HTTP errors
tail -n 100 ${MELTR_HOME}/meltr.log | grep -E "ERROR.*http output|WARNING.*http output"

# Count HTTP errors in last hour
grep "$(date -d '1 hour ago' +%Y-%m-%d)" ${MELTR_HOME}/meltr.log | grep -c "ERROR.*http output"

# View HTTP statistics summary
meltr generators status <generator-name> | grep -A 15 "Output Status"
```

## Quick Fix Script

Run this to check common issues:
```bash
#!/bin/bash
echo "=== MELTr Service Diagnostic ==="
echo ""
echo "1. Service Status:"
sudo systemctl status meltr --no-pager -l | head -20
echo ""
echo "2. Recent Logs:"
sudo journalctl -u meltr -n 20 --no-pager
echo ""
echo "3. Binary Check:"
which meltr && meltr --version || echo "Binary not found"
echo ""
echo "4. Config Check:"
meltr config validate 2>&1 || echo "Config validation failed"
echo ""
echo "5. Manual Test:"
timeout 5 meltr api start 2>&1 || echo "Manual start failed"
```

