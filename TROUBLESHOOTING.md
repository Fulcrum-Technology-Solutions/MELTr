# LogForge Service Troubleshooting Guide

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
# Detailed status
sudo systemctl status logforge -l --no-pager

# Check if service file exists
cat /etc/systemd/system/logforge.service
```

### 3. Verify Installation
```bash
# Check if logforge binary exists and is executable
which logforge
ls -la /opt/logforge/.venv/bin/logforge

# Test logforge command directly
/opt/logforge/.venv/bin/logforge --version
/opt/logforge/.venv/bin/logforge status
```

### 4. Check LOGFORGE_HOME and Permissions
```bash
# Check LOGFORGE_HOME environment variable
echo $LOGFORGE_HOME

# Check if logforge directory exists
ls -la /opt/logforge/logforge/ 2>/dev/null || ls -la ./logforge/ 2>/dev/null || ls -la ~/.logforge/ 2>/dev/null

# Check directory permissions
ls -la $(dirname $(/opt/logforge/.venv/bin/logforge config show 2>&1 | grep -i config | head -1 | awk '{print $NF}') 2>/dev/null || echo "/opt/logforge/logforge")

# Check if config.yaml exists
find /opt/logforge -name "config.yaml" -type f 2>/dev/null
find . -name "config.yaml" -type f 2>/dev/null
find ~ -name "config.yaml" -type f 2>/dev/null
```

### 5. Test Manual Execution
```bash
# Try running as the logforge user (if it exists)
sudo -u logforge /opt/logforge/.venv/bin/logforge api start

# Or run directly to see the error
/opt/logforge/.venv/bin/logforge api start

# Check Python path
sudo -u logforge python3 -c "import sys; print(sys.path)"
sudo -u logforge /opt/logforge/.venv/bin/python -c "import logforge; print('OK')"
```

### 6. Check User and Permissions
```bash
# Check if logforge user exists
id logforge 2>/dev/null || echo "logforge user does not exist"

# Check service file user/group
grep -E "^User=|^Group=" /etc/systemd/system/logforge.service

# Check directory ownership
ls -la /opt/logforge/
ls -la /opt/logforge/.venv/bin/logforge
```

### 7. Validate Configuration
```bash
# Validate config file
/opt/logforge/.venv/bin/logforge config validate

# Show config (if it loads)
/opt/logforge/.venv/bin/logforge config show
```

### 8. Check Dependencies
```bash
# Verify Python and virtual environment
/opt/logforge/.venv/bin/python --version
/opt/logforge/.venv/bin/pip list | grep -E "fastapi|typer|pydantic"

# Check if all required modules can be imported
sudo -u logforge /opt/logforge/.venv/bin/python -c "
import sys
sys.path.insert(0, '/opt/logforge/src')
try:
    from logforge.service import LogForgeService
    print('✓ LogForgeService import successful')
except Exception as e:
    print(f'✗ Import failed: {e}')
    import traceback
    traceback.print_exc()
"
```

### 9. Check File System and Paths
```bash
# Check if working directory exists
grep WorkingDirectory /etc/systemd/system/logforge.service

# Verify paths in service file
cat /etc/systemd/system/logforge.service | grep -E "ExecStart|WorkingDirectory|Environment"

# Check disk space
df -h /opt/logforge
```

### 10. Test with Debug Output
```bash
# Run with Python debug output
sudo -u logforge PYTHONUNBUFFERED=1 /opt/logforge/.venv/bin/python -m logforge api start

# Or with verbose Python
sudo -u logforge /opt/logforge/.venv/bin/python -v -m logforge api start 2>&1 | head -50
```

## Common Issues and Solutions

### Issue: "ModuleNotFoundError" or Import Errors
**Solution:**
- Ensure the `src/` directory is in Python path or install in development mode:
  ```bash
  cd /opt/logforge
  /opt/logforge/.venv/bin/pip install -e .
  ```

### Issue: "Permission denied" errors
**Solution:**
- Check file permissions:
  ```bash
  sudo chown -R logforge:logforge /opt/logforge/logforge/
  sudo chmod -R 755 /opt/logforge/logforge/
  ```

### Issue: "Config file not found"
**Solution:**
- Initialize LogForge:
  ```bash
  sudo -u logforge /opt/logforge/.venv/bin/logforge init --directory /opt/logforge/logforge
  ```

### Issue: "LOGFORGE_HOME not set correctly"
**Solution:**
- Check the service file environment variable:
  ```bash
  sudo systemctl edit logforge
  # Add:
  # [Service]
  # Environment="LOGFORGE_HOME=/opt/logforge/logforge"
  sudo systemctl daemon-reload
  ```

## Viewing HTTP Output Errors

HTTP output errors can be viewed in multiple ways:

### 1. Main Log File (Primary Location)

The main application log file is configured in your `config.yaml`:
```yaml
logging:
  file: ${LOGFORGE_HOME}/logforge.log
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
ls -la /opt/logforge/.venv/bin/logforge 2>/dev/null || echo "Binary not found"
echo ""
echo "4. Config Check:"
/opt/logforge/.venv/bin/logforge config validate 2>&1 || echo "Config validation failed"
echo ""
echo "5. Manual Test:"
timeout 5 /opt/logforge/.venv/bin/logforge api start 2>&1 || echo "Manual start failed"
```

