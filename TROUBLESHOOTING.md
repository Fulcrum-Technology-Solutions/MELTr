# LogForge Service Troubleshooting Guide

**Linux single-instance install and layout:** [docs/deployment/linux-single-instance.md](docs/deployment/linux-single-instance.md).

## Installation paths

- **Wheel install:** The `logforge` binary is typically in the active virtualenv’s `bin/` or in `/usr/local/bin` / `/usr/bin`. Config and data live under **LOGFORGE_HOME** (default: `~/.logforge` for interactive users, or **`/var/lib/logforge`** when running as the service user).
- **Service user:** The default service user is **logmgr** (not `logforge`). The systemd unit sets `User=logmgr`, `Group=logmgr`, and `Environment="LOGFORGE_HOME=/var/lib/logforge"` when installed with `--home /var/lib/logforge`.
- **Log files:** For the bundled layout under `/opt/logforge`, application logs default to **`/opt/logforge/logs/logforge.log`** (with rotation), independent of `LOGFORGE_HOME`. Other installs fall back to `LOGFORGE_HOME/logs/logforge.log`. Operators can set **`LOGFORGE_LOG_FILE`** in the environment (e.g. systemd unit or `systemctl edit`) to override. The systemd unit also sends stdout/stderr to the journal.

### Wrong mount or split filesystem

If **`LOGFORGE_HOME`** or **`/opt/logforge`** spans multiple mounts (e.g. bind mounts inside the venv or data dir), you can see confusing permission or I/O errors. Keep the **application venv** under one mount (e.g. all of `/opt/logforge`) and put **large file outputs** on separate paths via `config.yaml` instead of splitting the default tree across devices.

## Quick Diagnosis Commands

### 1. Check Systemd Journal Logs (Most Important)
```bash
# View recent logs
sudo journalctl -u logforge -n 50 --no-pager

# Follow logs in real-time
sudo journalctl -u logforge -f

# View logs with timestamps
sudo journalctl -u logforge --since "5 minutes ago" --no-pager

# View full error details
sudo journalctl -u logforge -n 100 --no-pager | grep -i error
```

### 2. Check Service Status
```bash
# Status (no root required)
logforge service status
# or
systemctl status logforge --no-pager

# Check if service file exists
cat /etc/systemd/system/logforge.service
```

### 3. Verify Installation
```bash
# Binary location (venv or /usr/local/bin when installed from wheel)
which logforge
logforge --version
logforge service status
```

### 4. Check LOGFORGE_HOME and Permissions
```bash
echo $LOGFORGE_HOME

# Common locations
ls -la /var/lib/logforge/ 2>/dev/null || ls -la ~/.logforge/ 2>/dev/null || ls -la ./.logforge/ 2>/dev/null

# Config and log file
ls -la /var/lib/logforge/config.yaml 2>/dev/null
ls -la /var/lib/logforge/logs/logforge.log 2>/dev/null
```

### 5. Test Manual Execution
```bash
# As service user (logmgr)
sudo -u logmgr logforge api start

# Or run directly to see errors
logforge api start
```

### 6. Check User and Permissions
```bash
id logmgr 2>/dev/null || echo "logmgr user does not exist"
grep -E "^User=|^Group=" /etc/systemd/system/logforge.service
ls -la /var/lib/logforge/
```

### 7. Validate Configuration
```bash
logforge config validate
logforge config show
```

### 8. Check Dependencies
```bash
python3 --version
pip list | grep -E "fastapi|typer|pydantic"
python3 -c "import logforge; print('OK')"
```

### 9. Check File System and Paths
```bash
grep WorkingDirectory /etc/systemd/system/logforge.service
grep -E "ExecStart|WorkingDirectory|Environment" /etc/systemd/system/logforge.service
df -h /var/lib/logforge
```

### 10. Test with Debug Output
```bash
sudo -u logmgr PYTHONUNBUFFERED=1 logforge api start
python3 -v -m logforge api start 2>&1 | head -50
```

## Common Issues and Solutions

### Issue: "ModuleNotFoundError" or Import Errors
**Solution:**
- Reinstall the wheel or install from source in development mode: `pip install -e .` from the project root.

### Issue: "Permission denied" errors
**Solution:**
- Ensure LOGFORGE_HOME (e.g. `/var/lib/logforge`) is owned by the service user:
  ```bash
  sudo chown -R logmgr:logmgr /var/lib/logforge
  ```

### Issue: "Config file not found"
**Solution:**
- Run init. As a normal user: `logforge init --directory /var/lib/logforge --force` only works if you can write that path; otherwise use `sudo` or init as `logmgr` after `chown`.
  ```bash
  sudo logforge init --directory /var/lib/logforge --user logmgr --group logmgr --force
  # If logmgr exists and the tree is writable as logmgr:
  sudo -u logmgr env LOGFORGE_HOME=/var/lib/logforge logforge init --directory /var/lib/logforge --force
  ```

### Issue: "LOGFORGE_HOME not set correctly"
**Solution:**
- Ensure the systemd unit sets LOGFORGE_HOME. Reinstall the service with explicit home:
  ```bash
  sudo logforge service install --home /var/lib/logforge --user logmgr
  ```
  Or edit the unit and add `Environment="LOGFORGE_HOME=/var/lib/logforge"`, then `sudo systemctl daemon-reload`.

## Viewing HTTP Output Errors

HTTP output errors can be viewed in multiple ways:

### 1. Main Log File (Primary Location)

The main application log file is under LOGFORGE_HOME by default:
```yaml
logging:
  file: ${LOGFORGE_HOME}/logs/logforge.log
  level: INFO  # Use DEBUG for more detailed logs
```

**View HTTP-specific errors:**
```bash
# View HTTP output errors in log file
tail -f ${LOGFORGE_HOME}/logforge.log | grep -i "http output"

# View all HTTP output related messages
grep -i "logforge.outputs.http" ${LOGFORGE_HOME}/logforge.log

# View only errors and warnings from HTTP handler
grep -E "ERROR|WARNING.*http output" ${LOGFORGE_HOME}/logforge.log

# View connection failures
grep -i "connection failed\|connection error\|timeout" ${LOGFORGE_HOME}/logforge.log

# View authentication failures
grep -i "authentication failed\|401\|403" ${LOGFORGE_HOME}/logforge.log

# View retry attempts
grep -i "retry attempt" ${LOGFORGE_HOME}/logforge.log

# View recent HTTP errors (last 50 lines)
tail -n 50 ${LOGFORGE_HOME}/logforge.log | grep -i "http output"
```

### 2. Systemd Journal (If Running as Service)

```bash
# View HTTP output errors in journal
sudo journalctl -u logforge | grep -i "http output"

# Follow HTTP errors in real-time
sudo journalctl -u logforge -f | grep -i "http output"

# View only HTTP errors and warnings
sudo journalctl -u logforge -n 100 --no-pager | grep -E "ERROR|WARNING.*http output"

# View connection failures
sudo journalctl -u logforge | grep -iE "connection failed|connection error|timeout"

# View HTTP initialization messages
sudo journalctl -u logforge | grep -i "http output.*initialized"
```

### 3. Generator Status Command (Quick Overview)

```bash
# View generator status with output handler details
logforge generators status <generator-name>

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

If you run LogForge directly (not as a service):
```bash
# Run in foreground to see all logs
logforge api start

# Or with environment variable to see HTTP debug info
LOGFORGE_LOG_LEVEL=DEBUG logforge api start
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
export LOGFORGE_LOG_LEVEL=DEBUG
logforge api start
```

### 6. Real-Time Monitoring

```bash
# Monitor HTTP output errors in real-time from log file
tail -f ${LOGFORGE_HOME}/logforge.log | grep --line-buffered -i "http output"

# Monitor with color highlighting (if you have ccze installed)
tail -f ${LOGFORGE_HOME}/logforge.log | grep --line-buffered -i "http output" | ccze -A

# Monitor via journalctl
sudo journalctl -u logforge -f | grep --line-buffered -i "http output"
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
logforge generators status <generator-name> | grep -A 10 "Output Status"

# Check for recent HTTP errors
tail -n 100 ${LOGFORGE_HOME}/logforge.log | grep -E "ERROR.*http output|WARNING.*http output"

# Count HTTP errors in last hour
grep "$(date -d '1 hour ago' +%Y-%m-%d)" ${LOGFORGE_HOME}/logforge.log | grep -c "ERROR.*http output"

# View HTTP statistics summary
logforge generators status <generator-name> | grep -A 15 "Output Status"
```

## Quick Fix Script

Run this to check common issues:
```bash
#!/bin/bash
echo "=== LogForge Service Diagnostic ==="
echo ""
echo "1. Service Status:"
sudo systemctl status logforge --no-pager -l | head -20
echo ""
echo "2. Recent Logs:"
sudo journalctl -u logforge -n 20 --no-pager
echo ""
echo "3. Binary Check:"
which logforge && logforge --version || echo "Binary not found"
echo ""
echo "4. Config Check:"
logforge config validate 2>&1 || echo "Config validation failed"
echo ""
echo "5. Manual Test:"
timeout 5 logforge api start 2>&1 || echo "Manual start failed"
```

