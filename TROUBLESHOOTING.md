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

