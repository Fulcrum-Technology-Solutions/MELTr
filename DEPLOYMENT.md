# LogForge Deployment & Update Guide

**First-time Linux install (single instance, `/opt`, systemd):** See **[docs/deployment/linux-single-instance.md](docs/deployment/linux-single-instance.md)**. For the **`.tar.gz` bundle** (embedded Python, no `pip` on target), see **[docs/deployment/linux-tarball.md](docs/deployment/linux-tarball.md)**.

**Installation:** Choose the path that matches your environment—the **official Linux x86_64 `.tar.gz`** (see [linux-tarball.md](docs/deployment/linux-tarball.md)), a **wheel** (`pip install logforge` or `pip install logforge-*.whl` from a release), or an **editable install** from source for development. Config and data live under **LOGFORGE_HOME**. For `logforge service install` without `--home`, the default is derived from the **resolved binary** (bundle under `/opt/logforge` → `/opt/logforge/data`; otherwise same rules as `get_logforge_home()`). The service user is **logmgr**. Uninstalling the systemd service (`logforge service uninstall`) removes only the unit file; it does not delete LOGFORGE_HOME or application data.

## Updating the official Linux `.tar.gz` (GitHub Releases)

Use this when LogForge was installed from **`logforge-{version}-linux-x86_64.tar.gz`** (embedded Python under e.g. `/opt/logforge`). Details: [docs/deployment/linux-tarball.md](docs/deployment/linux-tarball.md).

1. **Stop** the service: `sudo systemctl stop logforge`
2. **Back up** `LOGFORGE_HOME` (e.g. `/opt/logforge/data` or `/var/lib/logforge`), for example:  
   `sudo tar czf ~/logforge-home-backup.tgz -C /var/lib logforge`  
   (adjust `-C` and the final path component to match your data directory).
3. **Download** the new `logforge-{version}-linux-x86_64.tar.gz` and verify checksums from [Releases](https://github.com/Fulcrum-Technology-Solutions/LogForge/releases).
4. **Replace the install tree** (`python/`, `app/`) without deleting your data directory:
   - If **`LOGFORGE_HOME`** is **outside** the unpacked bundle, remove the old `python` and `app` directories (or the whole previous bundle folder) and unpack the new tarball into the same install root.
   - If **`LOGFORGE_HOME`** is **`/opt/logforge/data`**, move it aside before replacing the tree:  
     `sudo mv /opt/logforge/data /tmp/logforge-data.PRESERVE`  
     remove the old bundle under `/opt/logforge`, unpack the new tarball, then  
     `sudo mv /tmp/logforge-data.PRESERVE /opt/logforge/data`.
5. Ensure **`PATH`** includes `/opt/logforge/app/bin` and that **systemd** still uses the bundled binary if you installed with  
   `logforge service install --binary /opt/logforge/app/bin/logforge ...`.
6. **Start** the service: `sudo systemctl start logforge`

## Update Process for Test Machines

### Scenario: You've made code changes and need to update a test machine

### Method 1: Git-based Update (Recommended for Development)

**On your development machine:**
```bash
# Commit and push your changes
git add .
git commit -m "Your changes"
git push
```

**On the test machine:**
```bash
# Navigate to installation directory
cd /opt/logforge

# Stop the service
sudo systemctl stop logforge

# Backup current installation (optional but recommended)
sudo cp -r src src.backup.$(date +%Y%m%d_%H%M%S)

# Pull latest changes
git pull origin main  # or your branch name

# Reinstall the package
source .venv/bin/activate
pip install -e . --upgrade

# Restart the service
sudo systemctl start logforge

# Verify it's running
sudo systemctl status logforge
logforge --version
```

### Method 2: Direct File Copy (No Git)

**On your development machine:**
```bash
# Create a tarball of the source
cd /path/to/LogForge
tar czf logforge-update.tar.gz src/ pyproject.toml README.md LICENSE

# Transfer to test machine (scp, rsync, USB, etc.)
scp logforge-update.tar.gz user@test-machine:/tmp/
```

**On the test machine:**
```bash
# Stop the service
sudo systemctl stop logforge

# Backup current installation
cd /opt/logforge
sudo cp -r src src.backup.$(date +%Y%m%d_%H%M%S)

# Extract new files
cd /opt/logforge
sudo tar xzf /tmp/logforge-update.tar.gz

# Reinstall the package
source .venv/bin/activate
pip install -e . --upgrade

# Restart the service
sudo systemctl start logforge

# Verify
sudo systemctl status logforge
logforge --version
```

### Method 3: Reinstall from Scratch (Clean Install)

**On the test machine:**
```bash
# Stop and uninstall service
sudo systemctl stop logforge
sudo systemctl disable logforge
sudo logforge service uninstall

# Backup your data (config, entities, templates)
sudo cp -r /var/lib/logforge /var/lib/logforge.backup.$(date +%Y%m%d_%H%M%S)

# For wheel install: upgrade the package; data stays in /var/lib/logforge
pip install logforge --upgrade

# Reinstall service (only if you removed it)
sudo logforge service install --user logmgr --group logmgr --home /var/lib/logforge

# For source install: remove old tree, clone/copy, pip install -e ., then service install --home /var/lib/logforge
# Restore from backup to /var/lib/logforge if you moved data

# Start service
sudo systemctl start logforge
sudo systemctl enable logforge
```

## What Gets Preserved During Updates

**Preserved (in LOGFORGE_HOME):**
- ✅ `config.yaml` - Your configuration
- ✅ `entities.yaml` - Your entity registry
- ✅ `templates/custom/` - Your custom templates
- ✅ `templates/default/` - Community templates (unless you reinstall them)
- ✅ `outputs/` - Output files
- ✅ `logs/logforge.log` - Log files (under LOGFORGE_HOME)

**Replaced:**
- 🔄 Python source code (`src/`)
- 🔄 Virtual environment packages (if you reinstall)
- 🔄 Systemd service file (if you reinstall service)

## Quick Update Script

Create this script on your test machine for easy updates:

```bash
#!/bin/bash
# /opt/logforge/update.sh

set -e

echo "=== LogForge Update Script ==="
echo ""

# Stop service
echo "Stopping service..."
sudo systemctl stop logforge

# Backup
BACKUP_DIR="src.backup.$(date +%Y%m%d_%H%M%S)"
echo "Creating backup: $BACKUP_DIR"
cd /opt/logforge
sudo cp -r src "$BACKUP_DIR"

# Update code
echo "Updating code..."
if [ -d "src/.git" ]; then
    cd src
    git pull
    cd ..
else
    echo "Not a git repository. Please update manually."
    exit 1
fi

# Reinstall
echo "Reinstalling package..."
source .venv/bin/activate
pip install -e . --upgrade

# Restart
echo "Restarting service..."
sudo systemctl start logforge

# Verify
sleep 2
if sudo systemctl is-active --quiet logforge; then
    echo "✓ Service started successfully"
    logforge --version
else
    echo "✗ Service failed to start. Check logs:"
    echo "  sudo journalctl -u logforge -n 50"
    exit 1
fi
```

Make it executable:
```bash
chmod +x /opt/logforge/update.sh
```

Usage:
```bash
sudo /opt/logforge/update.sh
```

## Update Checklist

Before updating:
- [ ] Backup your `config.yaml`
- [ ] Backup your `entities.yaml`
- [ ] Backup custom templates in `templates/custom/`
- [ ] Note any running generators (they'll restart automatically)

After updating:
- [ ] Verify service is running: `sudo systemctl status logforge`
- [ ] Check version: `logforge --version`
- [ ] Verify generators: `logforge generators list`
- [ ] Check logs: `sudo journalctl -u logforge -n 50`
- [ ] Test API: `curl http://127.0.0.1:8080/api/health`

## Rollback Process

If an update causes issues:

```bash
# Stop service
sudo systemctl stop logforge

# Restore backup
cd /opt/logforge
sudo rm -rf src
sudo mv src.backup.YYYYMMDD_HHMMSS src

# Reinstall from backup
source .venv/bin/activate
pip install -e . --upgrade

# Restart
sudo systemctl start logforge
```

## Configuration Migration

If the config schema changes between versions:

1. **Backup your config:**
   ```bash
   cp /opt/logforge/logforge/config.yaml /opt/logforge/logforge/config.yaml.backup
   ```

2. **Validate config after update:**
   ```bash
   logforge config validate
   ```

3. **If validation fails, check what changed:**
   ```bash
   logforge config show > new_config.yaml
   diff config.yaml.backup new_config.yaml
   ```

4. **Merge changes manually or regenerate:**
   ```bash
   # Option 1: Let LogForge create new default and merge manually
   mv config.yaml config.yaml.old
   logforge init --force  # Creates new default
   # Manually merge your customizations
   
   # Option 2: Use config diff/merge tools (if implemented)
   ```

## Best Practices

1. **Always backup before updating** - Your data in `LOGFORGE_HOME` is safe, but backup anyway
2. **Test updates on a non-production machine first**
3. **Check release notes** - If there are breaking changes, plan accordingly
4. **Use version control** - Keep your config and entities in git if possible
5. **Monitor after update** - Watch logs and metrics for a few minutes after restart

## Automated Updates (Future)

For production, consider:
- CI/CD pipeline that builds and deploys
- Package manager (RPM/DEB) for easier updates
- Container-based deployment (Docker) for isolated updates
- Configuration management tools (Ansible, Puppet, etc.)









