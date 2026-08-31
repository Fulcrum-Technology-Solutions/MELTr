# MELTr Deployment & Update Guide

**First-time Linux install (single instance, `/opt`, systemd):** See **[docs/deployment/linux-single-instance.md](docs/deployment/linux-single-instance.md)**. For the **`.tar.gz` bundle** (embedded Python, no `pip` on target), see **[docs/deployment/linux-tarball.md](docs/deployment/linux-tarball.md)**.

**Installation:** Choose the path that matches your environment—the **official Linux x86_64 `.tar.gz`** or **wheel** from [GitHub Releases](https://github.com/Fulcrum-Technology-Solutions/MELTr/releases) (see [linux-tarball.md](docs/deployment/linux-tarball.md)), or an **editable install** from source for development. Install wheels with `pip install ./meltr-*.whl` (PyPI package name is `meltr`). Config and data live under **MELTR_HOME**. For `meltr service install` without `--home`, the default is derived from the **resolved binary** (bundle under `/opt/meltr` → **`MELTR_HOME=/opt/meltr`**; otherwise same rules as `get_logforge_home()`). The service user is **meltr**. Uninstalling the systemd service (`meltr service uninstall`) removes only the unit file; it does not delete MELTR_HOME or application data.

## Updating the official Linux `.tar.gz` (GitHub Releases)

Use this when MELTr was installed from **`meltr-{version}-linux-x86_64.tar.gz`** (embedded Python under e.g. `/opt/meltr`). Details: [docs/deployment/linux-tarball.md](docs/deployment/linux-tarball.md).

1. **Stop** the service: `sudo systemctl stop meltr`
2. **Back up** `MELTR_HOME` (e.g. `/opt/meltr` or `/var/lib/meltr`), for example:  
   `sudo tar czf ~/meltr-home-backup.tgz -C /opt meltr`  
   (adjust `-C` and paths to match your layout; preserve `config.yaml`, `entities.yaml`, `templates/`, etc.).
3. **Download** the new `meltr-{version}-linux-x86_64.tar.gz` and verify checksums from [Releases](https://github.com/Fulcrum-Technology-Solutions/MELTr/releases).
4. **Replace the install tree** (`python/`, `app/`) without deleting your data directory:
   - If **`MELTR_HOME`** is **outside** the unpacked bundle, remove the old `python` and `app` directories (or the whole previous bundle folder) and unpack the new tarball into the same install root.
   - If **`MELTR_HOME`** is **`/opt/meltr`** (state alongside `app/` and `python/`), move state aside before replacing the install tree, for example:  
     `sudo mv /opt/meltr/config.yaml /tmp/ && sudo mv /opt/meltr/entities.yaml /tmp/ && …`  
     or archive the whole directory except the install subdirs you replace; then restore after unpacking.
5. Ensure **`PATH`** includes `/opt/meltr/app/bin` and that **systemd** still uses the bundled binary if you installed with  
   `meltr service install --binary /opt/meltr/app/bin/meltr ...`.
6. **Start** the service: `sudo systemctl start meltr`

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
cd /opt/meltr

# Stop the service
sudo systemctl stop meltr

# Backup current installation (optional but recommended)
sudo cp -r src src.backup.$(date +%Y%m%d_%H%M%S)

# Pull latest changes
git pull origin main  # or your branch name

# Reinstall the package
source .venv/bin/activate
pip install -e . --upgrade

# Restart the service
sudo systemctl start meltr

# Verify it's running
sudo systemctl status meltr
meltr --version
```

### Method 2: Direct File Copy (No Git)

**On your development machine:**
```bash
# Create a tarball of the source
cd /path/to/MELTr
tar czf meltr-update.tar.gz src/ pyproject.toml README.md LICENSE

# Transfer to test machine (scp, rsync, USB, etc.)
scp meltr-update.tar.gz user@test-machine:/tmp/
```

**On the test machine:**
```bash
# Stop the service
sudo systemctl stop meltr

# Backup current installation
cd /opt/meltr
sudo cp -r src src.backup.$(date +%Y%m%d_%H%M%S)

# Extract new files
cd /opt/meltr
sudo tar xzf /tmp/meltr-update.tar.gz

# Reinstall the package
source .venv/bin/activate
pip install -e . --upgrade

# Restart the service
sudo systemctl start meltr

# Verify
sudo systemctl status meltr
meltr --version
```

### Method 3: Reinstall from Scratch (Clean Install)

**On the test machine:**
```bash
# Stop and uninstall service
sudo systemctl stop meltr
sudo systemctl disable meltr
sudo meltr service uninstall

# Backup your data (config, entities, templates)
sudo cp -r /var/lib/meltr /var/lib/meltr.backup.$(date +%Y%m%d_%H%M%S)

# For wheel install: download the new wheel from GitHub Releases; data stays in /var/lib/meltr
pip install ./meltr-*.whl --upgrade

# Reinstall service (only if you removed it)
sudo meltr service install --user meltr --group meltr --home /var/lib/meltr

# For source install: remove old tree, clone/copy, pip install -e ., then service install --home /var/lib/meltr
# Restore from backup to /var/lib/meltr if you moved data

# Start service
sudo systemctl start meltr
sudo systemctl enable meltr
```

## What Gets Preserved During Updates

**Preserved (in MELTR_HOME):**
- ✅ `config.yaml` - Your configuration
- ✅ `entities.yaml` - Your entity registry
- ✅ `templates/custom/` - Your custom templates
- ✅ `templates/default/` - Community templates (unless you reinstall them)
- ✅ `outputs/` - Output files
- ✅ `logs/meltr.log` - Application logs (bundle default: under `<install_root>/logs`, e.g. `/opt/meltr/logs/`; override with `LOGFORGE_LOG_FILE`)

**Replaced:**
- 🔄 Python source code (`src/`)
- 🔄 Virtual environment packages (if you reinstall)
- 🔄 Systemd service file (if you reinstall service)

## Quick Update Script

Create this script on your test machine for easy updates:

```bash
#!/bin/bash
# /opt/meltr/update.sh

set -e

echo "=== MELTr Update Script ==="
echo ""

# Stop service
echo "Stopping service..."
sudo systemctl stop meltr

# Backup
BACKUP_DIR="src.backup.$(date +%Y%m%d_%H%M%S)"
echo "Creating backup: $BACKUP_DIR"
cd /opt/meltr
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
sudo systemctl start meltr

# Verify
sleep 2
if sudo systemctl is-active --quiet meltr; then
    echo "✓ Service started successfully"
    meltr --version
else
    echo "✗ Service failed to start. Check logs:"
    echo "  sudo journalctl -u meltr -n 50"
    exit 1
fi
```

Make it executable:
```bash
chmod +x /opt/meltr/update.sh
```

Usage:
```bash
sudo /opt/meltr/update.sh
```

## Update Checklist

Before updating:
- [ ] Backup your `config.yaml`
- [ ] Backup your `entities.yaml`
- [ ] Backup custom templates in `templates/custom/`
- [ ] Note any running generators (they'll restart automatically)

After updating:
- [ ] Verify service is running: `sudo systemctl status meltr`
- [ ] Check version: `meltr --version`
- [ ] Verify generators: `meltr generators list`
- [ ] Check logs: `sudo journalctl -u meltr -n 50`
- [ ] Test API: `curl http://127.0.0.1:8080/api/health`

## Rollback Process

If an update causes issues:

```bash
# Stop service
sudo systemctl stop meltr

# Restore backup
cd /opt/meltr
sudo rm -rf src
sudo mv src.backup.YYYYMMDD_HHMMSS src

# Reinstall from backup
source .venv/bin/activate
pip install -e . --upgrade

# Restart
sudo systemctl start meltr
```

## Configuration Migration

If the config schema changes between versions:

1. **Backup your config:**
   ```bash
   cp /opt/meltr/config.yaml /opt/meltr/config.yaml.backup
   ```

2. **Validate config after update:**
   ```bash
   meltr config validate
   ```

3. **If validation fails, check what changed:**
   ```bash
   meltr config show > new_config.yaml
   diff config.yaml.backup new_config.yaml
   ```

4. **Merge changes manually or regenerate:**
   ```bash
   # Option 1: Let MELTr create new default and merge manually
   mv config.yaml config.yaml.old
   meltr init --force  # Creates new default
   # Manually merge your customizations
   
   # Option 2: Use config diff/merge tools (if implemented)
   ```

## Best Practices

1. **Always backup before updating** - Your data in `MELTR_HOME` is safe, but backup anyway
2. **Test updates on a non-production machine first**
3. **Check release notes** - If there are breaking changes, plan accordingly
4. **Use version control** - Keep your config and entities in git if possible
5. **Monitor after update** - Watch logs and metrics for a few minutes after restart

## Automated Updates (Future)

For production, consider:
- CI/CD workflow that builds and deploys
- Package manager (RPM/DEB) for easier updates
- Container-based deployment (Docker) for isolated updates
- Configuration management tools (Ansible, Puppet, etc.)









