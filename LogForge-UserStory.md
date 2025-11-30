s# 🎯 LogForge Community Edition - User Story & CLI Specification

**Version:** 1.0  
**Target User:** Intermediate technical professionals (security engineers, DevOps, QA)  
**Primary Use Case:** Continuous generation of realistic synthetic observability data  
**Platform:** API-first FastAPI service with Linux-native CLI

---

## 👤 User Persona

**Name:** Sam Rodriguez  
**Role:** Security Engineer  
**Organization:** Memorial Hospital (Healthcare, 500 employees)  
**Technical Profile:**
- Intermediate proficiency (understands data types, file formats, basic CLI)
- Cannot write complex code but can read/modify configuration files
- Comfortable with Linux command line and systemd services
- Familiar with SIEM platforms (Splunk, Elastic)

**Problem Statement:**
Sam needs to generate realistic synthetic logs from multiple vendors (Palo Alto, Windows, Cisco) to test their new SIEM deployment. Production data cannot be used due to HIPAA compliance. They need continuous, realistic event generation that mimics business hours patterns, with easy routing to multiple output handlers.

**Success Criteria:**
- Generate 10,000+ realistic events within first hour
- Successfully route events to both local files and Splunk HEC
- Customize entity registry with hospital-specific data
- Deploy to air-gapped test environment
- Run continuously with minimal supervision

---

## 🗺️ User Journey Map

### **Phase 1: Installation & Initialization (5 minutes)**

**Goal:** Get LogForge installed and initialized

```bash
# Download release binary
wget https://github.com/logforge/logforge-ce/releases/download/v1.0.0/logforge-linux-amd64
chmod +x logforge-linux-amd64
sudo mv logforge-linux-amd64 /usr/local/bin/logforge

# Verify installation
logforge --version
# Output: LogForge v1.0.0 (Community Edition)

# Initialize configuration
logforge init
```

**Expected Output:**
```
Initializing LogForge...
✓ Created config directory: ~/.logforge/
✓ Created config.yaml (core configuration)
✓ Created entities.yaml (sample with 10 users, 15 devices, 10 services)
✓ Created templates/default/ (community cache)
✓ Created templates/custom/ (user overrides)
✓ Initialized template cache
✓ FastAPI management API configured for 127.0.0.1:8080

Next steps:
  1. Install templates: logforge templates install <collection>
  2. Configure outputs: logforge outputs add
  3. Configure generators: logforge generators add <template>
  4. Start management API (optional): logforge api start --host 127.0.0.1 --port 8080
  5. Start service: logforge start (foreground) or sudo logforge service install

To run as a system service:
  sudo logforge service install
```

**Optional: Install as systemd service**
```bash
sudo logforge service install
```

**Expected Output:**
```
Installing LogForge systemd service...
✓ Created service file: /etc/systemd/system/logforge.service
✓ Created service user: logforge
✓ Created log directory: /var/log/logforge/
✓ Set permissions on /var/log/logforge/ (owner: logforge)
✓ Reloaded systemd daemon

Service installed successfully!

Manage with systemd:
  sudo systemctl start logforge
  sudo systemctl stop logforge
  sudo systemctl status logforge
  sudo systemctl enable logforge  (start on boot)

Or use LogForge commands:
  sudo logforge service start
  sudo logforge service stop
  sudo logforge service restart
  sudo logforge service status
```

**User State:** Sam now has LogForge installed with sample configurations ready to customize.

---

### **Phase 2: Template Discovery & Installation (8 minutes)**

**Goal:** Browse and install template collections

```bash
# Browse available templates (requires internet)
logforge templates list
```

**Expected Output:**
```
Available Template Collections (from repository):

📦 paloalto-wildfire (v1.0.0)
   Palo Alto Networks WildFire Threat Detection
   Templates: 2
   └─ threats/wildfire_threat_detected
   └─ analysis/file_analysis_complete

📦 microsoft-windows (v2.1.0)
   Microsoft Windows Event Logs
   Templates: 8
   └─ security/login_success
   └─ security/login_failure
   └─ security/account_lockout
   └─ security/privilege_escalation
   └─ system/service_start
   └─ system/service_stop
   └─ system/application_crash
   └─ system/driver_load

📦 cisco-asa (v1.5.0)
   Cisco ASA Firewall Logs
   Templates: 12
   └─ [collapsed - use 'templates info' for details]

Use 'logforge templates info <collection>' for details
Use 'logforge templates install <collection>' to install
```

**Get details on specific template:**
```bash
logforge templates info paloalto-wildfire/threats/wildfire_threat_detected
```

**Expected Output:**
```
🛡️  WildFire Threat Detection

Vendor:        Palo Alto Networks
Product:       WildFire
Data Source:   threats
Format:        CSV
Version:       1.0.0

Description:
  WildFire threat detection events with file analysis results including
  malware classification, severity ratings, and threat intelligence data.

Generation Settings:
  Base Frequency:  12 events/hour
  Time Patterns:   business_hours, night_hours, weekend
  Multipliers:
    - Business hours (Mon-Fri 9am-5pm): 3.0x  (36 events/hour)
    - Night hours (Mon-Fri 5pm-9am):    0.4x  (4.8 events/hour)
    - Weekend (Sat-Sun):                0.6x  (7.2 events/hour)

Required Entities:
  - users (random selection for event attribution)
  - devices (source IP addresses, hostnames)

Output Format: CSV with 47 fields
  - timestamp, device info, threat type, severity, file hash, threat description
  - Compatible with Palo Alto syslog ingestion

Documentation: https://docs.paloaltonetworks.com/wildfire
```

**Install template collections:**
```bash
# Install from repository (requires internet)
logforge templates install paloalto-wildfire
```

**Expected Output:**
```
Installing paloalto-wildfire from repository...
✓ Fetching package from repository
✓ Downloaded paloalto-wildfire-v1.0.0.forge (2.4 MB)
✓ Verified package signature
✓ Extracted 2 templates
✓ Validated template schemas
✓ Updated local template registry

Installed Templates:
  └─ paloalto-wildfire/threats/wildfire_threat_detected
  └─ paloalto-wildfire/analysis/file_analysis_complete

Ready to use! Create a generator with:
  logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
```

```bash
# Install more collections
logforge templates install microsoft-windows
logforge templates install cisco-asa
```

**Verify installed templates:**
```bash
logforge templates list --installed
```

**Expected Output:**
```
Installed Template Collections:

📦 paloalto-wildfire (v1.0.0) - 2 templates
📦 microsoft-windows (v2.1.0) - 8 templates
📦 cisco-asa (v1.5.0) - 12 templates

Total: 3 collections, 22 templates
```

**User State:** Sam has browsed available templates and installed three vendor collections (Palo Alto, Windows, Cisco).

---

### **Phase 3: Configure Outputs (12 minutes)**

**Goal:** Define output handlers (local files + Splunk HEC)

**Default output definition in `~/.logforge/config.yaml`:**

```yaml
outputs:
  retry:
    max_attempts: -1
    retry_interval: 5s
    backoff_multiplier: 2.0
    max_backoff: 5m
  buffer_size: 10000
  definitions:
    - name: local-files
      type: file
      enabled: true
      path: /var/log/logforge/output/
      rotation:
        type: size
        max_size: 100MB
        max_files: 10
      format: raw
      filename_pattern: "${vendor}-${product}-${data_source}.log"
```

**List current outputs:**
```bash
logforge outputs list
```

**Expected Output:**
```
Configured Outputs:

Name         | Type  | Status   | Events Sent | Errors | Description
local-files  | file  | ready    | 0           | 0      | Local file output
```

**Add Splunk HEC output interactively:**
```bash
logforge outputs add
```

**Interactive Prompts:**
```
Add New Output
───────────────────

Output Name: splunk-hec
Output Type: [file, http, syslog, kafka, stdout] http

HTTP Configuration:
  URL: https://splunk.memorial.local:8088/services/collector/event
  Method: [GET, POST, PUT] POST
  
  Headers (key=value, empty line to finish):
    Header 1: Authorization=Splunk ${SPLUNK_HEC_TOKEN}
    Header 2: Content-Type=application/json
    Header 3: [Enter]
  
  Batch size (events per request) [100]: 
  Batch timeout (e.g., 5s, 1m) [5s]: 
  
  Retry Configuration:
    Max retry attempts [3]: 
    Backoff strategy: [fixed, exponential] exponential
  
  Enable now? [Y/n] y
  Test connection? [Y/n] y

Testing connection to splunk-hec...
✓ DNS resolution: splunk.memorial.local → 10.50.1.100
✓ TCP connection: successful
✓ TLS handshake: successful (certificate valid)
✓ Authentication: token accepted
✓ Test event sent and acknowledged

✓ Output 'splunk-hec' created and enabled

Summary:
  Name:   splunk-hec
  Type:   http
  URL:    https://splunk.memorial.local:8088/services/collector/event
  Status: connected
```

**Alternative: Update `config.yaml` directly**

```yaml
outputs:
  retry:
    max_attempts: -1
    retry_interval: 5s
    backoff_multiplier: 2.0
    max_backoff: 5m
  buffer_size: 10000
  definitions:
    - name: local-files
      type: file
      enabled: true
      path: /var/log/logforge/output/
      rotation:
        type: size
        max_size: 100MB
        max_files: 10
      format: raw
      filename_pattern: "${vendor}-${product}-${data_source}.log"
  
    - name: splunk-hec
      type: http
      enabled: true
      url: https://splunk.memorial.local:8088/services/collector/event
      method: POST
      headers:
        Authorization: "Splunk ${SPLUNK_HEC_TOKEN}"
        Content-Type: "application/json"
      batch_size: 100
      batch_timeout: 5s
      retry:
        max_attempts: 3
        backoff: exponential
```

**Verify outputs:**
```bash
logforge outputs list
```

**Expected Output:**
```
Configured Outputs:

Name         | Type  | Status      | Events Sent | Errors | Description
local-files  | file  | ready       | 0           | 0      | Local file output
splunk-hec   | http  | connected   | 0           | 0      | Splunk HEC ingestion
```

**Test outputs:**
```bash
logforge outputs test splunk-hec
```

**Expected Output:**
```
Testing output: splunk-hec
✓ DNS resolution: splunk.memorial.local → 10.50.1.100
✓ TCP connection: successful
✓ TLS handshake: successful
✓ Authentication: valid token
✓ Test event sent: acknowledged by Splunk (200 OK)

Output is healthy and ready to receive events
```

**User State:** Sam has configured two outputs: local files and Splunk HEC, both tested and ready.

---

### **Phase 4: Configure Generators (15 minutes)**

**Goal:** Create generators from templates and map to outputs

**Add first generator (Palo Alto WildFire threats):**
```bash
logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
```

**Interactive Prompts:**
```
Add New Generator from Template
─────────────────────────────

Template: paloalto-wildfire/threats/wildfire_threat_detected
  🛡️  WildFire Threat Detection
  Format: CSV | Base Frequency: 12 events/hour

Generator Configuration:
  Generator ID (default: paloalto-wildfire-threats): [Enter]

Select Outputs (space to toggle, enter to confirm):
  [x] local-files
  [x] splunk-hec

Generation Settings:
  Base frequency (events/hour) [12]: [Enter]
  
  Enable time-based patterns? [Y/n] y
    Business hours multiplier (Mon-Fri 9am-5pm) [3.0]: [Enter]
    Night hours multiplier (Mon-Fri 5pm-9am) [0.4]: [Enter]
    Weekend multiplier (Sat-Sun) [0.6]: [Enter]

Summary:
  Generator ID:      paloalto-wildfire-threats
  Template:       paloalto-wildfire/threats/wildfire_threat_detected
  Outputs:   local-files, splunk-hec
  Expected Rate:  
    - Business hours: 36 events/hour (3.0x multiplier)
    - Night hours:    4.8 events/hour (0.4x multiplier)
    - Weekend:        7.2 events/hour (0.6x multiplier)
  Entity Registry: ~/.logforge/entities.yaml

Enable generator now? [Y/n] y

✓ Generator 'paloalto-wildfire-threats' created
✓ Output 'local-files' mapped
✓ Output 'splunk-hec' mapped
✓ Generator enabled and ready

Generator will begin generating when service starts.
```

**Add Windows login generators:**
```bash
logforge generators add microsoft-windows/security/login_success
```

**Interactive Prompts:**
```
Generator ID: windows-login-success
Outputs: [x] local-files, [x] splunk-hec
Base frequency [50]: [Enter]
Time patterns? [Y/n] y
  Business hours [4.0]: [Enter]
  Night hours [0.2]: [Enter]
  Weekend [0.3]: [Enter]
Enable now? [Y/n] y

✓ Generator 'windows-login-success' created and enabled
```

```bash
logforge generators add microsoft-windows/security/login_failure
```

**Interactive Prompts:**
```
Generator ID: windows-login-failures
Outputs: [x] local-files, [x] splunk-hec
Base frequency [5]: [Enter]
Time patterns? [Y/n] y
  Business hours [2.0]: [Enter]
  Night hours [0.5]: [Enter]
  Weekend [0.4]: [Enter]
Enable now? [Y/n] y

✓ Generator 'windows-login-failures' created and enabled
```

**Alternative: Bulk YAML Configuration**

Sam could create `generators-memorial.yaml`:

```yaml
generators:
  - id: paloalto-wildfire-threats
    template: paloalto-wildfire/threats/wildfire_threat_detected
    enabled: true
    outputs:
      - local-files
      - splunk-hec
    generation:
      base_frequency: 12
      time_patterns:
        - business_hours
        - night_hours
        - weekend
      multipliers:
        business_hours: 3.0
        night_hours: 0.4
        weekend: 0.6
  
  - id: windows-login-success
    template: microsoft-windows/security/login_success
    enabled: true
    outputs:
      - local-files
      - splunk-hec
    generation:
      base_frequency: 50
      time_patterns:
        - business_hours
        - night_hours
        - weekend
      multipliers:
        business_hours: 4.0
        night_hours: 0.2
        weekend: 0.3
  
  - id: windows-login-failures
    template: microsoft-windows/security/login_failure
    enabled: true
    outputs:
      - local-files
      - splunk-hec
    generation:
      base_frequency: 5
      time_patterns:
        - business_hours
        - night_hours
        - weekend
      multipliers:
        business_hours: 2.0
        night_hours: 0.5
        weekend: 0.4
```

**Apply bulk configuration:**
```bash
# Validate first
logforge generators validate -f generators-memorial.yaml
```

**Expected Output:**
```
Validating generator configuration: generators-memorial.yaml

✓ YAML syntax valid
✓ All templates exist and are installed
✓ All output references valid (local-files, splunk-hec)
✓ Entity registry compatible with all templates
✓ No ID conflicts with existing generators
✓ Generation settings within valid ranges

Configuration is valid and ready to apply

Summary:
  Generators to create: 3
  Templates used:    3
  Outputs:      2 (local-files, splunk-hec)
  Total expected rate (business hours): ~268 events/hour
```

```bash
# Apply configuration
logforge generators apply -f generators-memorial.yaml
```

**Expected Output:**
```
Applying generator configuration...

✓ Created generator: paloalto-wildfire-threats
  └─ Mapped to: local-files, splunk-hec
✓ Created generator: windows-login-success
  └─ Mapped to: local-files, splunk-hec
✓ Created generator: windows-login-failures
  └─ Mapped to: local-files, splunk-hec

Generators created: 3
Active generators:  3
Outputs:    2 connected
Expected rate:   ~67 events/hour (varies with time patterns)

Generators will begin generating when service starts
```

**View configured generators:**
```bash
logforge generators list
```

**Expected Output:**
```
Configured Generators:

ID                        | Template                              | Status  | Outputs        | Enabled
paloalto-wildfire-threats | paloalto-wildfire/threats/threat_det  | ready   | local-files, spl... | yes
windows-login-success     | microsoft-windows/security/login_suc  | ready   | local-files, spl... | yes
windows-login-failures    | microsoft-windows/security/login_fai  | ready   | local-files, spl... | yes

Total: 3 generators configured
Expected rate: ~67 events/hour base (varies with time patterns)
```

**User State:** Sam has configured three generators mapped to both local files and Splunk HEC, ready to generate.

---

### **Phase 5: Start Generation (3 minutes)**

**Goal:** Start LogForge service and verify generation

**Start the service:**

```bash
# Option 1: Start as systemd service (production)
sudo systemctl start logforge
sudo systemctl status logforge
```

**Expected Output:**
```
● logforge.service - LogForge Synthetic Event Generator
     Loaded: loaded (/etc/systemd/system/logforge.service; disabled; vendor preset: enabled)
     Active: active (running) since Tue 2025-01-15 14:23:45 EST; 5s ago
   Main PID: 12345 (logforge)
      Tasks: 8 (limit: 4915)
     Memory: 42.3M
        CPU: 234ms
     CGroup: /system.slice/logforge.service
             └─12345 /usr/local/bin/logforge start --service

Jan 15 14:23:45 memorial-test logforge[12345]: LogForge v1.0.0 starting...
Jan 15 14:23:45 memorial-test logforge[12345]: ✓ Loaded configuration
Jan 15 14:23:45 memorial-test logforge[12345]: ✓ Loaded entity registry (10 users, 15 devices, 10 services)
Jan 15 14:23:45 memorial-test logforge[12345]: ✓ Initialized 3 generators
Jan 15 14:23:45 memorial-test logforge[12345]: ✓ Connected 2 outputs
Jan 15 14:23:45 memorial-test logforge[12345]: LogForge ready - generating events
```

```bash
# Option 2: Run in foreground (development/testing)
logforge start
```

**Expected Output:**
```
Starting LogForge v1.0.0...

✓ Loaded configuration from ~/.logforge/config.yaml
✓ Loaded entity registry: ~/.logforge/entities.yaml
  └─ 10 users, 15 devices, 10 services
✓ Initialized 3 generators:
  └─ paloalto-wildfire-threats (enabled)
  └─ windows-login-success (enabled)
  └─ windows-login-failures (enabled)
✓ Connected 2 outputs:
  └─ local-files (file) - /var/log/logforge/output/
  └─ splunk-hec (http) - https://splunk.memorial.local:8088

LogForge is running
Management API: http://127.0.0.1:8080/api/status
Expected rate: ~67 events/hour base (varies with time patterns)

Press Ctrl+C to stop
[14:23:46] Generated event → paloalto-wildfire-threats → local-files, splunk-hec
[14:23:47] Generated event → windows-login-success → local-files, splunk-hec
[14:23:48] Generated event → windows-login-success → local-files, splunk-hec
...
```

**Check service status:**
```bash
logforge status
```

**Expected Output:**
```
LogForge Status
════════════════════════════════════════════════════════════════

Service:       RUNNING (uptime: 00:02:34)
Version:       1.0.0
Config:        ~/.logforge/config.yaml
Entity Reg:    10 users, 15 devices, 10 services

Generators:       3 active, 0 disabled
Outputs:  2 connected, 0 errors

Generation Rate (current):
  Total:       1.2 events/sec
  Last minute: 72 events
  Since start: 185 events

Active Generators:
┌───────────────────────────┬─────────┬──────────┬─────────┬──────────────┐
│ ID                        │ Status  │ Rate     │ Events  │ Outputs │
├───────────────────────────┼─────────┼──────────┼─────────┼──────────────┤
│ paloalto-wildfire-threats │ running │ 0.01/s   │ 3       │ 2            │
│ windows-login-success     │ running │ 1.11/s   │ 171     │ 2            │
│ windows-login-failures    │ running │ 0.07/s   │ 11      │ 2            │
└───────────────────────────┴─────────┴──────────┴─────────┴──────────────┘

Outputs:
┌─────────────┬──────┬───────────┬─────────┬────────┐
│ ID          │ Type │ Status    │ Events  │ Errors │
├─────────────┼──────┼───────────┼─────────┼────────┤
│ local-files │ file │ connected │ 185     │ 0      │
│ splunk-hec  │ http │ connected │ 185     │ 0      │
└─────────────┴──────┴───────────┴─────────┴────────┘

Time Pattern: business_hours (multiplier: 4.0x for windows-login-success)
Next status update: 00:00:56
```

**Monitor output file:**
```bash
tail -f /var/log/logforge/output/paloalto-wildfire-threats.log
```

**Sample Output:**
```
1,2025/01/15 14:23:45,0010101010,THREAT,ransomware,0,2025/01/15 14:23:45,192.168.1.101,45.142.212.35,0.0.0.0,0.0.0.0,fw-policy-1,jsmith,,web-browsing,vsys1,trusted,untrusted,ethernet1/2,ethernet1/1,alert,0,10523,1,52341,443,0,0,0x400000,tcp,deny,invoice_a8f3c9d2.pdf,WildFire-Report,malware,high,client-to-server,142573,0x2000,United States,Russia,0,application/pdf,0,d4e8f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0,...
1,2025/01/15 14:24:12,0010101010,THREAT,command-and-control,0,2025/01/15 14:24:12,192.168.1.103,217.182.143.67,0.0.0.0,0.0.0.0,fw-policy-1,bjohnson,,web-browsing,vsys1,trusted,untrusted,ethernet1/2,ethernet1/1,critical,0,11847,1,49182,443,0,0,0x400000,tcp,deny,system_b7d4e8f1.dll,WildFire-Report,malware,critical,client-to-server,198472,0x2000,United States,Bulgaria,0,application/octet-stream,0,c9e5a2b3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1,...
```

**💡 "Aha!" Moment:** Sam sees realistic logs flowing with:
- Usernames from their entity registry (`jsmith`, `bjohnson`)
- Device IP addresses from their network ranges
- Realistic threat types, severities, file hashes
- Contextually appropriate timestamps and patterns

**User State:** LogForge is running and generating realistic events to both local files and Splunk HEC.

---

### **Phase 6: Monitoring & Operations (Ongoing)**

**Goal:** Monitor generation, view metrics, troubleshoot issues

**Real-time status monitoring:**
```bash
logforge status --watch
```

**Updates every 5 seconds with live metrics**

**Check FastAPI management endpoint directly:**
```bash
curl -s http://127.0.0.1:8080/api/status | jq .
```

**Sample Response:**
```json
{
  "uptime": 154,
  "version": "1.0.0",
  "generators": [
    {
      "name": "windows-login-success",
      "state": "RUNNING",
      "events_generated": 128,
      "errors": 0
    }
  ],
  "system": {
    "cpu_percent": 12.4,
    "memory_mb": 48.1,
    "threads": 9
  }
}
```

**View detailed generator metrics:**
```bash
logforge generators metrics paloalto-wildfire-threats
```

**Expected Output:**
```
Generator Metrics: paloalto-wildfire-threats
════════════════════════════════════════════════════════════════

Template:      paloalto-wildfire/threats/wildfire_threat_detected
Status:        running
Uptime:        02:15:34
Last Event:    2 seconds ago

Events Generated:
  Total:       543 events
  Last hour:   432 events (0.12/sec avg)
  Last 24h:    N/A (service started today)

Current Rate:  0.01 events/sec
Time Modifier: 3.0x (business hours active)
Effective Rate: 36 events/hour

Frequency Pattern:
  Base:          12 events/hour
  Business hrs:  36 events/hour (3.0x)
  Night hrs:     4.8 events/hour (0.4x)
  Weekend:       7.2 events/hour (0.6x)

Outputs:
  local-files:   543 events sent, 0 failed, 0 retries
  splunk-hec:    543 events sent, 0 failed, 2 retries (transient network)

Entity Usage:
  Users:         10 total, 8 accessed (80% coverage)
  Devices:       15 total, 12 accessed (80% coverage)
  Services:      Not used by this template

Output Files:
  /var/log/logforge/output/paloalto-wildfire-threats.log (487 KB, 543 lines)
```

**View service logs:**
```bash
logforge logs --follow
```

**Expected Output:**
```
[14:23:45] INFO  Service started (v1.0.0)
[14:23:45] INFO  Loaded entity registry: 10 users, 15 devices, 10 services
[14:23:45] INFO  Initialized generator: paloalto-wildfire-threats
[14:23:45] INFO  Initialized generator: windows-login-success
[14:23:45] INFO  Initialized generator: windows-login-failures
[14:23:45] INFO  Connected output: local-files (file)
[14:23:45] INFO  Connected output: splunk-hec (http)
[14:23:46] DEBUG Generated event from paloalto-wildfire-threats
[14:23:46] DEBUG Sent to local-files: success
[14:23:46] DEBUG Sent to splunk-hec: success (200 OK)
[14:23:47] DEBUG Generated event from windows-login-success
...
[14:25:12] WARN  Output splunk-hec: transient error (network timeout), retrying...
[14:25:13] INFO  Output splunk-hec: retry successful
```

**Filter logs by generator:**
```bash
logforge logs --generator windows-login-success --level info
```

**Health check:**
```bash
logforge health
```

**Expected Output:**
```
LogForge Health Check
════════════════════════════════════════════════════════════════

✓ Service:          running (uptime: 02:15:34)
✓ Configuration:    valid
✓ Entity Registry:  loaded (10 users, 15 devices, 10 services)
✓ Templates:        3 installed, 3 in use
✓ Generators:          3 active, 0 errors, 0 warnings
✓ Outputs:     2 connected, 0 errors
✓ Disk Space:       247 GB available in /var/log/logforge/
✓ Memory:           42.3 MB / 2 GB used (2.1%)
✓ File Handles:     23 / 1024 used

Overall Status: HEALTHY

Recent Issues: None
Suggestions:   None
```

**View aggregated metrics:**
```bash
logforge metrics
```

**Expected Output:**
```
LogForge Metrics (Last 60 minutes)
════════════════════════════════════════════════════════════════

Events Generated:   2,847 total
Average Rate:       0.79 events/sec
Peak Rate:          3.2 events/sec (14:45:00 - business hours spike)
Min Rate:           0.05 events/sec (14:12:00)

By Generator:
┌───────────────────────────┬─────────┬──────────┬────────┐
│ Generator                    │ Events  │ Percent  │ Rate   │
├───────────────────────────┼─────────┼──────────┼────────┤
│ windows-login-success     │ 2,247   │ 78.9%    │ 0.62/s │
│ windows-login-failures    │ 312     │ 11.0%    │ 0.09/s │
│ paloalto-wildfire-threats │ 288     │ 10.1%    │ 0.08/s │
└───────────────────────────┴─────────┴──────────┴────────┘

By Output:
┌─────────────┬─────────┬────────┬─────────┬────────┐
│ Output │ Events  │ Errors │ Retries │ Uptime │
├─────────────┼─────────┼────────┼─────────┼────────┤
│ local-files │ 2,847   │ 0      │ 0       │ 100%   │
│ splunk-hec  │ 2,847   │ 0      │ 3       │ 100%   │
└─────────────┴─────────┴────────┴─────────┴────────┘

Disk Usage:
  Output directory: 2.4 MB (2,847 events across 3 files)
  Rotation status:  healthy (well below 100 MB limit)
```

**User State:** Sam can monitor generation in real-time, view detailed metrics, and verify events are flowing correctly.

---

### **Phase 7: Customization - Entity Registry (30 minutes)**

**Goal:** Replace sample data with Memorial Hospital-specific entities

**Copy sample for customization:**
```bash
cp ~/.logforge/entities.yaml ~/.logforge/entities-memorial.yaml
```

**Edit with hospital-specific data:**
```bash
vim ~/.logforge/entities-memorial.yaml
```

**Sam updates:**
- Organization name: "Memorial Hospital"
- Domain: "memorialhospital.org"
- NetBIOS domain: "MEMORIAL"
- Adds realistic user names (medical staff)
- Adds realistic device names (medical workstations, servers)
- Adds hospital-specific custom fields (HIPAA compliance flags, medical departments)

**Sample customized entities.yaml:**
```yaml
organization:
  name: "Memorial Hospital"
  domain: "memorialhospital.org"
  netbios_domain: "MEMORIAL"
  timezone: "America/New_York"
  industry: "Healthcare"
  location:
    city: "New York"
    state: "New York"
    country: "USA"
  settings:
    password_expiry_days: 90
    require_mfa: true
    custom_hipaa_compliant: true

users:
  - username: "dr_smith"
    full_name: "Dr. Sarah Smith"
    email: "ssmith@memorialhospital.org"
    user_id: "U1001"
    department: "Cardiology"
    title: "Attending Physician"
    custom_license_number: "MD-123456"
    custom_phi_access_level: "full"
  
  - username: "nurse_johnson"
    full_name: "Robert Johnson"
    email: "rjohnson@memorialhospital.org"
    user_id: "U1002"
    department: "Emergency"
    title: "RN"
    custom_license_number: "RN-789012"
    custom_phi_access_level: "standard"

devices:
  - hostname: "RADIOLOGY-WS001"
    fqdn: "RADIOLOGY-WS001.memorialhospital.org"
    ip_address: "10.50.1.100"
    mac_address: "00:1A:2B:3C:4D:5E"
    device_id: "D1001"
    os_type: "Windows 10"
    device_type: "medical_workstation"
    department: "Radiology"
    custom_hipaa_compliant: true
    custom_phi_storage: true
    custom_pacs_integrated: true
  
  # ... more hospital-specific devices
```

**Validate custom entity registry:**
```bash
logforge config validate --entities ~/.logforge/entities-memorial.yaml
```

**Expected Output (Success):**
```
Validating entity registry: ~/.logforge/entities-memorial.yaml

✓ YAML syntax valid
✓ Schema validation passed
✓ Organization section: valid
  └─ Name: Memorial Hospital
  └─ Domain: memorialhospital.org (valid DNS format)
  └─ NetBIOS: MEMORIAL (valid format)
✓ Network ranges: 3 ranges defined
✓ Users: 15 defined
  └─ All usernames unique
  └─ All user_ids unique
  └─ All emails valid format
  └─ 12 custom fields detected
✓ Devices: 25 defined
  └─ All hostnames unique
  └─ All device_ids unique
  └─ All IP addresses valid
  └─ All MAC addresses valid
  └─ 8 custom fields detected
✓ Services: 12 defined
  └─ All service_ids unique

Entity Registry is valid!

Summary:
  Organization:  Memorial Hospital (memorialhospital.org)
  Users:         15
  Devices:       25
  Services:      12
  Custom Fields: 20 (across all entity types)
```

**Expected Output (Error - shows helpful validation):**
```
Validating entity registry: ~/.logforge/entities-memorial.yaml

✗ Validation failed

Errors found:

  Line 47: Invalid IP address format
    Device: RADIOLOGY-WS001
    Field:  ip_address
    Value:  "10.50.1"
    Error:  IP address must be complete (e.g., "10.50.1.100")

  Line 82: Duplicate username
    Username: "dr_smith"
    First defined: line 23
    Duplicate: line 82
    Fix: Each username must be unique

  Line 115: Invalid email format
    User:   nurse_johnson
    Email:  "rjohnson@memorialhospital"
    Error:  Missing domain extension (should be .org)

Run with --verbose for additional details
```

**Sam fixes the errors and validates again:**
```bash
vim ~/.logforge/entities-memorial.yaml
# Fix IP address, remove duplicate username, fix email format

logforge config validate --entities ~/.logforge/entities-memorial.yaml
# ✓ Entity Registry is valid!
```

**Update main config to use custom entities:**
```bash
vim ~/.logforge/config.yaml
```

**Change:**
```yaml
# Before:
entity_registry: ~/.logforge/entities.yaml

# After:
entity_registry: ~/.logforge/entities-memorial.yaml
```

**Or use CLI command:**
```bash
logforge config set entity_registry ~/.logforge/entities-memorial.yaml
```

**Expected Output:**
```
Configuration updated:
  entity_registry: ~/.logforge/entities-memorial.yaml

To apply changes:
  Restart service: sudo systemctl restart logforge
  Or reload generators: logforge generators reload --all
```

**Restart service to apply changes:**
```bash
sudo systemctl restart logforge
logforge status
```

**Expected Output:**
```
LogForge Status
════════════════════════════════════════════════════════════════

Service:       RUNNING (uptime: 00:00:08)
Version:       1.0.0
Config:        ~/.logforge/config.yaml
Entity Reg:    15 users, 25 devices, 12 services  ← Updated!

Generators:       3 active, 0 disabled
Outputs:  2 connected, 0 errors
...
```

**Monitor output to verify custom entities:**
```bash
tail -f /var/log/logforge/output/microsoft-windows-security.log
```

**Sample Output (now shows Memorial Hospital entities):**
```
... <User>dr_smith@memorialhospital.org</User> ...
... <Computer>RADIOLOGY-WS001.memorialhospital.org</Computer> ...
... <Domain>MEMORIAL</Domain> ...
... <Department>Cardiology</Department> ...
```

**💡 Key Insight:** Sam sees their custom hospital entities (usernames, device names, domains) in the generated logs, making them realistic for their test environment.

**User State:** Sam has successfully customized the entity registry with hospital-specific data and verified it's working.

---

### **Phase 8: Air-Gapped Deployment (20 minutes)**

**Goal:** Deploy LogForge to isolated test environment without internet

**On internet-connected machine:**

```bash
# Download template packages as .forge files
logforge templates download paloalto-wildfire --output /tmp/packages/
logforge templates download microsoft-windows --output /tmp/packages/
logforge templates download cisco-asa --output /tmp/packages/
```

**Expected Output:**
```
Downloading paloalto-wildfire...
✓ Fetched metadata from repository
✓ Downloaded paloalto-wildfire-v1.0.0.forge (2.4 MB)
✓ Verified package signature
✓ Saved: /tmp/packages/paloalto-wildfire-v1.0.0.forge

Downloading microsoft-windows...
✓ Fetched metadata from repository
✓ Downloaded microsoft-windows-v2.1.0.forge (5.8 MB)
✓ Verified package signature
✓ Saved: /tmp/packages/microsoft-windows-v2.1.0.forge

Downloading cisco-asa...
✓ Fetched metadata from repository
✓ Downloaded cisco-asa-v1.5.0.forge (4.2 MB)
✓ Verified package signature
✓ Saved: /tmp/packages/cisco-asa-v1.5.0.forge

All packages downloaded successfully (12.4 MB total)

Transfer these files to your air-gapped system:
  /tmp/packages/paloalto-wildfire-v1.0.0.forge
  /tmp/packages/microsoft-windows-v2.1.0.forge
  /tmp/packages/cisco-asa-v1.5.0.forge
```

**Transfer .forge files to air-gapped system (via USB, secure file transfer, etc.)**

**On air-gapped machine:**

```bash
# Verify LogForge is installed
logforge --version

# Install templates from local .forge files
logforge templates install /media/usb/paloalto-wildfire-v1.0.0.forge
```

**Expected Output:**
```
Installing from local package: paloalto-wildfire-v1.0.0.forge

✓ Package file exists and is readable
✓ Verified package signature (trusted)
✓ Extracted package contents
✓ Validated 2 template schemas
✓ Installed to ~/.logforge/templates/paloalto-wildfire/
✓ Updated local template registry

Installed Templates:
  └─ paloalto-wildfire/threats/wildfire_threat_detected
  └─ paloalto-wildfire/analysis/file_analysis_complete

Package paloalto-wildfire v1.0.0 installed successfully
```

```bash
# Install remaining packages
logforge templates install /media/usb/microsoft-windows-v2.1.0.forge
logforge templates install /media/usb/cisco-asa-v1.5.0.forge
```

**Verify installed templates:**
```bash
logforge templates list --installed
```

**Expected Output:**
```
Installed Template Collections (Local):

📦 paloalto-wildfire (v1.0.0) - installed from local package
   2 templates
   └─ threats/wildfire_threat_detected
   └─ analysis/file_analysis_complete

📦 microsoft-windows (v2.1.0) - installed from local package
   8 templates
   └─ [templates listed]

📦 cisco-asa (v1.5.0) - installed from local package
   12 templates
   └─ [templates listed]

Total: 3 collections, 22 templates

Note: Air-gapped mode - repository updates unavailable
```

**Sam can now configure generators using installed templates:**
```bash
logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
# Proceed with normal configuration...
```

**User State:** Sam has successfully deployed LogForge to an air-gapped environment with offline template packages.

---

### **Phase 9: Ad-Hoc Testing - One-Shot Generation (10 minutes)**

**Goal:** Generate specific event counts for immediate testing

**Generate 1000 test events:**
```bash
logforge generate once paloalto-wildfire/threats/wildfire_threat_detected \
  --count 1000 \
  --output /tmp/test-wildfire.log
```

**Expected Output:**
```
One-Shot Generation
═══════════════════════════════════════════════════════════════

Template:       paloalto-wildfire/threats/wildfire_threat_detected
Entity Reg:     ~/.logforge/entities-memorial.yaml
Output:         /tmp/test-wildfire.log
Target Count:   1000 events

Generating events...
[████████████████████████████████████████] 1000/1000 (100%)

✓ Generated 1000 events in 2.3 seconds (434 events/sec)
✓ Output: /tmp/test-wildfire.log (847 KB)

Sample events (first 3 lines):
  1,2025/01/15 14:23:45,0010101010,THREAT,ransomware,0,2025/01/15...
  1,2025/01/15 14:23:46,0010101010,THREAT,spyware,0,2025/01/15...
  1,2025/01/15 14:23:47,0010101010,THREAT,virus,0,2025/01/15...

Ready to use for testing!
```

**View sample output:**
```bash
head -n 5 /tmp/test-wildfire.log
```

**Generate to specific output:**
```bash
logforge generate once microsoft-windows/security/login_success \
  --count 500 \
  --output splunk-hec
```

**Expected Output:**
```
One-Shot Generation
═══════════════════════════════════════════════════════════════

Template:       microsoft-windows/security/login_success
Output:    splunk-hec (http)
Target Count:   500 events

Generating and sending events...
[████████████████████████████████████████] 500/500 (100%)

✓ Generated 500 events in 1.8 seconds (277 events/sec)
✓ Sent to splunk-hec: 500 events, 0 errors

All events successfully delivered to output
```

**Generate backdated events (historical data):**
```bash
logforge generate once paloalto-wildfire/threats/wildfire_threat_detected \
  --count 5000 \
  --start-time "2025-01-01T00:00:00Z" \
  --end-time "2025-01-31T23:59:59Z" \
  --output january-threats.log
```

**Expected Output:**
```
One-Shot Generation (Historical)
═══════════════════════════════════════════════════════════════

Template:       paloalto-wildfire/threats/wildfire_threat_detected
Time Range:     2025-01-01 00:00:00 → 2025-01-31 23:59:59 UTC
                (31 days, 0 hours)
Target Count:   5000 events
Output:         january-threats.log

✓ Events will be distributed across time range
✓ Time patterns (business hours, etc.) will be applied

Generating events...
[████████████████████████████████████████] 5000/5000 (100%)

✓ Generated 5000 events in 8.7 seconds (574 events/sec)
✓ Output: january-threats.log (4.2 MB)
✓ Events span: 2025-01-01 00:04:23 → 2025-01-31 23:51:47

Distribution:
  - Business hours: 3,247 events (65%)
  - Night hours:     987 events (20%)
  - Weekend:         766 events (15%)

Ready for historical SIEM ingestion!
```

**Generate to stdout (for piping/processing):**
```bash
logforge generate once microsoft-windows/security/login_success \
  --count 10 \
  --output stdout \
  --format json | jq .
```

**Expected Output:**
```json
{
  "timestamp": "2025-01-15T14:23:45.123Z",
  "event_id": 4624,
  "computer": "RADIOLOGY-WS001.memorialhospital.org",
  "user": "dr_smith@memorialhospital.org",
  "generator_ip": "10.50.1.100",
  "logon_type": "Interactive",
  "status": "success"
}
...
```

**User State:** Sam can generate ad-hoc test data for immediate use, with flexibility for different counts, time ranges, and outputs.

---

## 📚 Complete CLI Command Reference

### **Service Management**

```bash
# Start/stop service
logforge start                          # Run in foreground
logforge stop                           # Stop foreground process
sudo logforge service install           # Install systemd service
sudo logforge service uninstall         # Remove systemd service
sudo logforge service start             # Start systemd service
sudo logforge service stop              # Stop systemd service
sudo logforge service restart           # Restart systemd service
sudo logforge service status            # Check systemd service status

# Or use systemd directly
sudo systemctl start logforge
sudo systemctl stop logforge
sudo systemctl restart logforge
sudo systemctl status logforge
sudo systemctl enable logforge          # Start on boot
```

### **Configuration Management**

```bash
# Bootstrap
logforge init                      # Initialize configuration

# Validation
logforge config validate                # Validate all configs
logforge config validate --entities FILE # Validate specific entity registry

# Configuration viewing/editing
logforge config show                    # Display current configuration
logforge config set KEY VALUE           # Set configuration value
logforge config reset                   # Reset to defaults

# Examples:
logforge config set entity_registry ~/.logforge/entities-custom.yaml
logforge config set outputs.definitions[0].path /custom/output/
logforge config set outputs.definitions[0].rotation.max_size 500MB
```

### **Template Management**

```bash
# Browse templates
logforge templates list                 # List available templates (from repository)
logforge templates list --installed     # List installed templates
logforge templates info TEMPLATE        # Show template details

# Install templates
logforge templates install COLLECTION   # Install from repository
logforge templates install FILE.forge   # Install from local .forge file

# Download for offline use
logforge templates download COLLECTION --output PATH

# Update templates
logforge templates update               # Update all templates
logforge templates update COLLECTION    # Update specific collection

# Remove templates
logforge templates remove COLLECTION
```

### **Output Management**

```bash
# List and view
logforge outputs list                  # List all outputs
logforge outputs list --enabled        # List only enabled
logforge outputs list --disabled       # List only disabled
logforge outputs info OUTPUT_NAME      # Show output details

# Add/edit outputs
logforge outputs add                   # Interactive add
logforge outputs add --config FILE     # Add from YAML
logforge outputs edit OUTPUT_NAME      # Edit output (opens editor)

# Enable/disable
logforge outputs enable OUTPUT_NAME
logforge outputs disable OUTPUT_NAME

# Test and monitor
logforge outputs test OUTPUT_NAME        # Test connectivity
logforge outputs metrics OUTPUT_NAME     # View output metrics

# Remove
logforge outputs remove OUTPUT_NAME
logforge outputs remove OUTPUT_NAME --force

# Export configuration
logforge outputs export > outputs-backup.yaml
```

### **Generator Management**

```bash
# List and view
logforge generators list                   # List all generators
logforge generators list --enabled         # List only enabled
logforge generators list --disabled        # List only disabled
logforge generators list --template TEMPLATE # Filter by template
logforge generators info GENERATOR_NAME      # Show generator details
logforge generators status                   # Show runtime status of all generators
logforge generators status GENERATOR_NAME    # Show specific generator status

# Add/edit generators
logforge generators add TEMPLATE               # Interactive add from template
logforge generators apply -f FILE              # Apply generators from YAML
logforge generators edit GENERATOR_NAME        # Edit generator (opens editor)

# Enable/disable
logforge generators enable GENERATOR_NAME
logforge generators disable GENERATOR_NAME

# Control
logforge generators reload GENERATOR_NAME      # Reload configuration
logforge generators reload --all               # Reload all generators

# Monitor
logforge generators metrics GENERATOR_NAME     # View detailed generator metrics

# Remove
logforge generators remove GENERATOR_NAME

# Validate and export
logforge generators validate -f FILE       # Validate generators YAML
logforge generators export > generators-backup.yaml
```

### **Generation - One-Shot (Ad-Hoc)**

```bash
# Basic generation
logforge generate once TEMPLATE --count N --output FILE

# To specific output
logforge generate once TEMPLATE --count N --output OUTPUT_NAME

# Historical/backdated events
logforge generate once TEMPLATE \
  --count N \
  --start-time "2025-01-01T00:00:00Z" \
  --end-time "2025-01-31T23:59:59Z" \
  --output FILE

# Custom entity registry
logforge generate once TEMPLATE \
  --count N \
  --entities /path/to/custom-entities.yaml \
  --output FILE

# To stdout (for piping)
logforge generate once TEMPLATE \
  --count N \
  --output stdout \
  --format json

# Examples:
logforge generate once paloalto-wildfire/threats/wildfire_threat_detected \
  --count 1000 \
  --output /tmp/test.log

logforge generate once microsoft-windows/security/login_success \
  --count 500 \
  --output splunk-hec
```

### **Monitoring & Status**

```bash
# Service status
logforge status                         # Overall status
logforge status --watch                 # Real-time updates (refresh every 5s)

# Health check
logforge health                         # Comprehensive health check

# Metrics
logforge metrics                        # Aggregated metrics (last hour)
logforge generators metrics GENERATOR_NAME     # Detailed generator metrics
logforge outputs metrics OUTPUT_NAME           # Detailed output metrics

# Logs
logforge logs                           # View service logs
logforge logs --follow                  # Tail logs in real-time
logforge logs --generator GENERATOR_NAME       # Filter by generator
logforge logs --level debug|info|warn|error # Filter by level
logforge logs --since "10m"             # Logs from last 10 minutes
logforge logs --since "2025-01-15T14:00:00Z" # Logs since specific time
```

### **Utility Commands**

```bash
# Version and help
logforge --version                      # Show version
logforge --help                         # Show help
logforge COMMAND --help                 # Show command-specific help

# Examples:
logforge templates --help
logforge generators --help
logforge outputs --help
```

---

## 🚨 Error Scenarios & Recovery

### **Scenario 1: Invalid Entity Registry (Syntax Error)**

**User Action:**
```bash
vim ~/.logforge/entities.yaml
# Sam accidentally breaks YAML syntax (missing quote)

logforge config validate
```

**Error Output:**
```
Validating configuration...

✗ Entity Registry Validation Failed

File: ~/.logforge/entities.yaml
Error: YAML syntax error at line 47

  45 |   devices:
  46 |     - hostname: "WS001"
  47 |       ip_address: "192.168.1.101
               ^─────────────────────────^
               Missing closing quote

Fix the syntax error and run validation again:
  logforge config validate
```

**Recovery:**
```bash
vim ~/.logforge/entities.yaml
# Fix: add closing quote
logforge config validate
# ✓ Entity Registry is valid!
```

---

### **Scenario 2: Invalid Entity Registry (Validation Error)**

**User Action:**
```bash
vim ~/.logforge/entities.yaml
# Sam adds duplicate username

logforge config validate
```

**Error Output:**
```
Validating entity registry: ~/.logforge/entities.yaml

✗ Validation failed

Errors found:

  Line 82: Duplicate username
    Username: "jsmith"
    First defined at line 23
    Duplicate at line 82
    
    Fix: Each username must be unique across all users
    Suggestion: Change to "jsmith2" or use a different identifier

  Line 115: Invalid IP address format
    Device: WS005
    Field: ip_address
    Value: "192.168.1"
    Expected: Complete IPv4 address (e.g., "192.168.1.100")

2 errors found. Fix these issues and validate again.
```

**Recovery:**
```bash
vim ~/.logforge/entities.yaml
# Fix duplicate username and invalid IP
logforge config validate
# ✓ Entity Registry is valid!
```

---

### **Scenario 3: Service Not Running**

**User Action:**
```bash
logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
```

**Error Output:**
```
✗ Error: LogForge service is not running

Generators can only be added while the service is running.

Start the service:
  Foreground:      logforge start
  System service:  sudo systemctl start logforge
  Or:              sudo logforge service start

Then try again:
  logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
```

**Recovery:**
```bash
logforge start
# Service starts...

logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
# Now succeeds
```

---

### **Scenario 4: Template Not Found**

**User Action:**
```bash
logforge generators add paloalto-wildfire/threats/unknown_template
```

**Error Output:**
```
✗ Error: Template not found

Template: paloalto-wildfire/threats/unknown_template

Available templates in 'paloalto-wildfire' collection:
  └─ paloalto-wildfire/threats/wildfire_threat_detected
  └─ paloalto-wildfire/analysis/file_analysis_complete

Did you mean?
  └─ paloalto-wildfire/threats/wildfire_threat_detected

To see all templates:
  logforge templates list --installed
```

**Recovery:**
```bash
logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
# Corrected template name
```

---

### **Scenario 5: Template Not Installed**

**User Action:**
```bash
logforge generators add cisco-asa/firewall/access_denied
```

**Error Output:**
```
✗ Error: Template collection not installed

Collection: cisco-asa
Template:   cisco-asa/firewall/access_denied

The 'cisco-asa' template collection is not installed.

To install:
  From repository:       logforge templates install cisco-asa
  From local package:    logforge templates install /path/to/cisco-asa-v1.5.0.forge

After installation, try again:
  logforge generators add cisco-asa/firewall/access_denied
```

**Recovery:**
```bash
logforge templates install cisco-asa
# Template collection installs...

logforge generators add cisco-asa/firewall/access_denied
# Now succeeds
```

---

### **Scenario 6: Output Not Connected**

**User Action:**
```bash
logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
# Selects output: splunk-hec
```

**Warning Output:**
```
⚠ Warning: Output 'splunk-hec' is not responding

Testing connection to splunk-hec...
✗ TCP connection failed: connection refused
✗ Host: splunk.memorial.local (10.50.1.100)
✗ Port: 8088

The generator will be created, but events may not be delivered until
the output is reachable.

Troubleshooting:
  1. Verify Splunk HEC is running: check Splunk service status
  2. Verify network connectivity: ping 10.50.1.100
  3. Verify port is open: telnet 10.50.1.100 8088
  4. Test output: logforge outputs test splunk-hec

Continue creating generator? [y/N]
```

**Recovery:**
```bash
# Fix Splunk HEC connectivity issue
# Then test output
logforge outputs test splunk-hec
# ✓ Output is healthy

# Generator will automatically resume sending when output is available
```

---

### **Scenario 7: Output Directory Not Writable**

**User Action:**
```bash
sudo logforge service start
```

**Error Output:**
```
✗ Error: Cannot write to output directory

Directory: /var/log/logforge/output/
Error:     Permission denied

The LogForge service user 'logforge' does not have write permissions
to the output directory.

Fix permissions:
  sudo chown -R logforge:logforge /var/log/logforge/
  sudo chmod 755 /var/log/logforge/

Then restart the service:
  sudo systemctl restart logforge
```

**Recovery:**
```bash
sudo chown -R logforge:logforge /var/log/logforge/
sudo chmod 755 /var/log/logforge/
sudo systemctl restart logforge
# Service starts successfully
```

---

### **Scenario 8: Output Batch Error**

**Runtime Error (shown in logs):**
```bash
logforge logs --follow
```

**Log Output:**
```
[14:45:23] ERROR Output 'splunk-hec' batch send failed
[14:45:23] ERROR   URL: https://splunk.memorial.local:8088/services/collector/event
[14:45:23] ERROR   HTTP 403 Forbidden: Invalid token
[14:45:23] ERROR   Batch: 100 events failed
[14:45:23] INFO  Retrying batch (attempt 1/3)...
[14:45:24] ERROR Retry failed: 403 Forbidden
[14:45:24] INFO  Retrying batch (attempt 2/3)...
[14:45:25] ERROR Retry failed: 403 Forbidden
[14:45:25] INFO  Retrying batch (attempt 3/3)...
[14:45:26] ERROR Retry failed: 403 Forbidden
[14:45:26] ERROR Batch permanently failed - events will be lost
[14:45:26] WARN  Output 'splunk-hec' disabled due to persistent errors
```

**Check output status:**
```bash
logforge outputs list
```

**Output:**
```
Name        | Type | Status       | Events | Errors | Description
splunk-hec  | http | error        | 2,847  | 100    | Authentication failed
                     (disabled)
```

**Recovery:**
```bash
# Fix Splunk HEC token
vim ~/.logforge/config.yaml
# Update Authorization header with correct token

# Re-enable output
logforge outputs enable splunk-hec

# Test connectivity
logforge outputs test splunk-hec
# ✓ Output is healthy

# Generators will automatically resume sending
```

---

## 🎯 Success Metrics

### **Immediate Success (First Hour)**
- ✅ LogForge installed and service running
- ✅ 3 template collections installed (Palo Alto, Windows, Cisco)
- ✅ 2 outputs configured and tested (local files, Splunk HEC)
- ✅ 3 generators configured and generating events
- ✅ 10,000+ realistic events generated
- ✅ Events visible in Splunk and local files
- ✅ Entity registry validated

### **Short-Term Success (First Week)**
- ✅ Custom entity registry deployed with hospital-specific data
- ✅ 20+ generators configured across multiple vendors
- ✅ Events flowing consistently with realistic time patterns
- ✅ Monitoring dashboard showing healthy metrics
- ✅ Zero service interruptions
- ✅ SIEM correlation rules tested with synthetic data

### **Long-Term Success (First Month)**
- ✅ Air-gapped deployment completed for isolated test environment
- ✅ 100,000+ events generated for compliance testing
- ✅ Custom templates created for hospital-specific applications
- ✅ LogForge integrated into CI/CD pipeline for automated testing
- ✅ Team trained on LogForge operations
- ✅ Documentation created for internal procedures

---

## 🎬 Key User Experience Principles

### **1. Progressive Disclosure**
- Start simple: init → install templates → configure generators → start
- Advanced features available but not required initially
- Interactive prompts guide new users; YAML configs for power users

### **2. Clear Feedback**
- Every command provides actionable output
- Errors include specific line numbers and fix suggestions
- Success messages confirm what was accomplished
- Status commands show real-time state

### **3. Safety Nets**
- Validation before applying changes
- Test commands for outputs
- Preview before bulk operations
- Non-destructive by default (enable/disable vs. delete)

### **4. Discoverability**
- Helpful error messages suggest next steps
- Commands include examples in help text
- Tab completion for commands (future enhancement)
- Contextual suggestions (e.g., "Did you mean?")

### **5. Operational Excellence**
- Monitoring built-in (status, metrics, logs, health)
- Graceful error handling with retries
- Clear service lifecycle (start, stop, restart)
- Production-ready defaults

---

## 🔄 Configuration File Examples

### **~/.logforge/config.yaml (Main Config)**

```yaml
# LogForge Main Configuration

version: "1.0.0"

engine:
  max_generators: 10              # null for unlimited based on CPU
  thread_pool_size: null          # null = cores × 5
  log_level: INFO

api:
  enabled: true
  host: 127.0.0.1
  port: 8080
  auth:
    enabled: false
    key: null

entity_registry:
  path: ~/.logforge/entities.yaml
  auto_save: true
  save_interval: 60
  backup_enabled: true
  backup_count: 3

templates:
  local_path: ~/.logforge/templates
  community_api_url: https://logforge.io/api/v1
  auto_update_check: true
  cache_ttl: 3600

logging:
  level: INFO
  file: ~/.logforge/logforge.log
  rotation:
    max_size: 50MB
    backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

outputs:
  retry:
    max_attempts: -1
    retry_interval: 5s
    backoff_multiplier: 2.0
    max_backoff: 300
  buffer_size: 10000
  definitions:
    - name: local-files
      type: file
      enabled: true
      path: /var/log/logforge/output/
      rotation:
        type: size
        max_size: 100MB
        max_files: 10
      format: raw

generators:
  - name: windows_security
    template: microsoft/windows/eventlog/security
    enabled: true
    frequency:
      base_rate: 10
      variation:
        - days: [1, 2, 3, 4, 5]
          time: "09:00-17:00"
          multiplier: 2.0
    outputs:
      - local-files
```

---

### **Outputs Section (config.yaml)**

```yaml
outputs:
  retry:
    max_attempts: -1
    retry_interval: 5s
    backoff_multiplier: 2.0
    max_backoff: 5m
  buffer_size: 10000
  definitions:
    # Local file output
    - name: local-files
      type: file
      enabled: true
      path: /var/log/logforge/output/
      rotation:
        type: size
        max_size: 100MB
        max_age: 7d
        max_files: 10
      format: raw
      filename_pattern: "${vendor}-${product}-${data_source}.log"
  
    # Splunk HEC
    - name: splunk-hec
      type: http
      enabled: true
      url: https://splunk.memorial.local:8088/services/collector/event
      method: POST
      headers:
        Authorization: "Splunk ${SPLUNK_HEC_TOKEN}"
        Content-Type: "application/json"
      batch_size: 100
      batch_timeout: 5s
      retry:
        max_attempts: 3
        backoff: exponential
        initial_delay: 1s
        max_delay: 30s
      timeout: 30s
      tls_verify: true
  
    # Syslog server
    - name: syslog-server
      type: syslog
      enabled: false
      host: syslog.memorial.local
      port: 514
      protocol: tcp  # tcp, udp, tls
      format: rfc5424
      facility: local0
      severity: info
  
    # Kafka cluster
    - name: kafka-cluster
      type: kafka
      enabled: false
      brokers:
        - kafka1.memorial.local:9092
        - kafka2.memorial.local:9092
        - kafka3.memorial.local:9092
      topic: logforge-events
      partition_key: "${vendor}-${product}"
      compression: gzip
      acks: 1
      batch_size: 100
      linger_ms: 5000
  
    # Stdout (for testing/debugging)
    - name: stdout
      type: stdout
      enabled: false
      format: json  # json, raw
      pretty_print: true
```

---

### **Generators Section (config.yaml)**

```yaml
generators:
  # Palo Alto WildFire Threats
  - name: paloalto-wildfire-threats
    template: paloalto-wildfire/threats/wildfire_threat_detected
    enabled: true
    outputs:
      - local-files
      - splunk-hec
    generation:
      base_frequency: 12  # events per hour
      time_patterns:
        - business_hours
        - night_hours
        - weekend
      multipliers:
        business_hours: 3.0
        night_hours: 0.4
        weekend: 0.6
    context:
      # Optional: override template variables
      custom_severity_distribution:
        critical: 0.1
        high: 0.3
        medium: 0.4
        low: 0.2
  
  # Windows Security - Login Success
  - name: windows-login-success
    template: microsoft-windows/security/login_success
    enabled: true
    outputs:
      - local-files
      - splunk-hec
    generation:
      base_frequency: 50
      time_patterns:
        - business_hours
        - night_hours
        - weekend
      multipliers:
        business_hours: 4.0
        night_hours: 0.2
        weekend: 0.3
  
  # Windows Security - Login Failures
  - name: windows-login-failures
    template: microsoft-windows/security/login_failure
    enabled: true
    outputs:
      - local-files
      - splunk-hec
    generation:
      base_frequency: 5
      time_patterns:
        - business_hours
        - night_hours
        - weekend
      multipliers:
        business_hours: 2.0
        night_hours: 0.5
        weekend: 0.4
  
  # Cisco ASA - Connection Denied
  - name: cisco-asa-denied
    template: cisco-asa/firewall/connection_denied
    enabled: false
    outputs:
      - local-files
    generation:
      base_frequency: 20
      multipliers:
        business_hours: 2.0
        night_hours: 0.8
        weekend: 0.5
```

---

## 📦 Package Format Specification

### **.forge Package Structure**

A `.forge` file is a renamed `.tar.gz` archive containing:

```
paloalto-wildfire-v1.0.0.forge (tar.gz)
│
├── manifest.json                   # Package metadata
├── vendor.meta.yaml                # Vendor metadata
├── product.meta.yaml               # Product metadata
├── collection.json                 # Collection index
├── templates/
│   ├── threats/
│   │   ├── wildfire_threat_detected.j2
│   │   └── wildfire_threat_detected.meta.yaml
│   └── analysis/
│       ├── file_analysis_complete.j2
│       └── file_analysis_complete.meta.yaml
├── schemas/                        # JSON schemas for validation
│   ├── vendor.schema.json
│   ├── product.schema.json
│   ├── template.schema.json
│   └── collection.schema.json
└── signature.asc                   # GPG signature (optional)
```

### **manifest.json**

```json
{
  "package_format_version": "1.0",
  "name": "paloalto-wildfire",
  "version": "1.0.0",
  "vendor": "paloalto",
  "product": "wildfire",
  "templates": [
    "threats/wildfire_threat_detected",
    "analysis/file_analysis_complete"
  ],
  "created_at": "2025-01-15T14:23:45Z",
  "checksum": "sha256:a8f3c9d2b3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"
}
```

---

## 🎓 Learning Path for New Users

### **Beginner (First Session - 30 minutes)**
1. Install LogForge
2. Run `logforge init`
3. Install one template collection
4. Add one generator to local file output
5. Start service and view generated events

**Commands:**
```bash
logforge init
logforge templates install paloalto-wildfire
logforge generators add paloalto-wildfire/threats/wildfire_threat_detected
logforge start
tail -f /var/log/logforge/output/paloalto-wildfire-threats.log
```

---

### **Intermediate (Week 1 - 2-4 hours)**
1. Configure multiple generators across vendors
2. Add Splunk HEC output
3. Customize entity registry with sample data
4. Monitor with `logforge status` and `logforge metrics`
5. Practice stopping/starting/reloading generators

**Commands:**
```bash
logforge outputs add  # Add Splunk HEC
logforge generators add microsoft-windows/security/login_success
logforge generators add cisco-asa/firewall/traffic_log
vim ~/.logforge/entities.yaml  # Customize entities
logforge config validate
logforge status --watch
```

---

### **Advanced (Month 1 - Ongoing)**
1. Deploy to air-gapped environment
2. Create custom entity registries for multiple environments
3. Bulk configure generators via YAML
4. Integrate with CI/CD for automated testing
5. Create custom templates (future enhancement)
6. Monitor with external tools (Prometheus, Grafana)

**Commands:**
```bash
logforge templates download paloalto-wildfire --output /tmp/
logforge templates install /path/to/package.forge
logforge generators apply -f generators-production.yaml
logforge generators validate -f generators-staging.yaml
logforge metrics  # Export for monitoring tools
```