# Template Repository Schema

## Introduction

This document defines the structure and schemas for MELTr template repositories. Template repositories are collections of vendor-specific log templates organized in a standardized, community-driven format that enables easy sharing, validation, and integration.

### Purpose

- **Standardization**: Consistent structure across all vendor templates
- **Validation**: JSON schemas ensure metadata integrity
- **Community**: Clear guidelines for community contributions
- **Discoverability**: Hierarchical organization for easy template discovery

---

## Repository Structure

Template repositories follow a strict **three-level hierarchy**:
```
{vendor}/                           ← Level 1: Vendor
  vendor.meta.yaml                  ← Vendor metadata
  {product}/                        ← Level 2: Product
    product.meta.yaml               ← Product metadata
    collection.json                 ← Collection index
    {data_source}/                  ← Level 3: Data source
      {template_name}.j2            ← Template (Jinja2)
      {template_name}.meta.yaml     ← Template metadata
```

### Key Rules

1. **Exactly three directory levels**: vendor → product → data_source
2. **Multiple data sources per product**: Each product can have many data source directories
3. **Multiple templates per data source**: Each data source can contain many templates
4. **No nested data sources**: Data source level is always the third and final level

### Example Structure
```
paloalto/
  vendor.meta.yaml
  wildfire/
    product.meta.yaml
    collection.json
    threats/
      wildfire_threat_detected.j2
      wildfire_threat_detected.meta.yaml
      advanced_threat.j2
      advanced_threat.meta.yaml
    analysis/
      file_analysis_complete.j2
      file_analysis_complete.meta.yaml
  firewall/
    product.meta.yaml
    collection.json
    network/
      traffic_log.j2
      traffic_log.meta.yaml
    security/
      threat_log.j2
      threat_log.meta.yaml
```

---

## Metadata Files

Every directory level includes metadata files that describe the vendor, product, and templates.

### 1. vendor.meta.yaml

**Location**: `{vendor}/vendor.meta.yaml`

**Schema**: `schemas/vendor.schema.json`

**Purpose**: Describes the vendor/organization producing the logs

**Required Fields**:
- `vendor` (string): Machine-friendly ID matching directory name (lowercase, alphanumeric, hyphens)
- `name` (string): Human-friendly display name

**Optional Fields**:
- `product` (string): Single product name for single-product vendors
- `website` (string): Vendor website URL
- `description` (string): Brief vendor description
- `logo` (string): Logo filename (png, jpg, svg)

**Example**:
```yaml
vendor: paloalto
name: "Palo Alto Networks"
website: "https://www.paloaltonetworks.com"
description: "Palo Alto Networks provides firewalls, VPN, and threat detection solutions."
logo: "paloalto-logo.png"
```

---

### 2. product.meta.yaml

**Location**: `{vendor}/{product}/product.meta.yaml`

**Schema**: `schemas/product.schema.json`

**Purpose**: Describes a specific product within a vendor's portfolio

**Required Fields**:
- `vendor` (string): Must match parent vendor directory name
- `product` (string): Machine-friendly ID matching directory name (lowercase, alphanumeric, hyphens)
- `name` (string): Human-friendly product display name

**Optional Fields**:
- `description` (string): Product description
- `version` (string): Product version or version range
- `documentation_url` (string): Link to product documentation

**Example**:
```yaml
vendor: paloalto
product: wildfire
name: "WildFire"
description: "Palo Alto Networks WildFire Threat Detection"
version: "All"
documentation_url: "https://docs.paloaltonetworks.com/wildfire"
```

---

### 3. collection.json

**Location**: `{vendor}/{product}/collection.json`

**Schema**: `schemas/collection.schema.json`

**Purpose**: Index of all templates for a product

**Required Fields**:
- `name` (string): Collection name, typically `{vendor}-{product}`
- `version` (string): Semantic version (semver format: `1.0.0`)
- `templates` (array): List of template paths

**Optional Fields**:
- `description` (string): Collection description
- `maintainers` (array): List of maintainer objects with `name`, `email`, `github`
- `tags` (array): Searchable tags for categorization

**Template Path Format**: 
- Format: `{data_source}/{template_name}`
- Example: `threats/wildfire_threat_detected`
- The system automatically appends `.j2` and `.meta.yaml` extensions

**Example**:
```json
{
  "name": "paloalto-wildfire",
  "version": "1.0.0",
  "description": "MELTr templates for Palo Alto WildFire threat detection logs",
  "maintainers": [
    {
      "name": "John Owen",
      "email": "jowen@ftsc.com",
      "github": "jowen-ftsc"
    }
  ],
  "tags": ["wildfire", "threat", "malware", "security"],
  "templates": [
    "threats/wildfire_threat_detected",
    "threats/advanced_threat",
    "analysis/file_analysis_complete"
  ]
}
```

---

### 4. template_name.meta.yaml

**Location**: `{vendor}/{product}/{data_source}/{template_name}.meta.yaml`

**Schema**: `schemas/template.schema.json`

**Purpose**: Metadata describing an individual template

**Required Fields**:
- `vendor` (string): Vendor identifier
- `product` (string): Product identifier
- `data_source` (string): Data source/log type (**only required at template level**)
- `description` (string): What this template generates
- `format` (string): Output format (JSON, XML, CSV, Syslog, CEF, LEEF, Plain Text, Custom)

**Optional Generation Fields**:
- `is_generator` (boolean, default: false): Whether this is a generator template
- `base_frequency` (number, min: 0, default: 1): Base events per hour
- `time_patterns` (array): Time patterns to follow (e.g., `business_hours`, `weekend`)
- `business_hours_multiplier` (number, min: 0, max: 10, default: 1.0): Business hours multiplier
- `night_hours_multiplier` (number, min: 0, max: 10, default: 1.0): Night hours multiplier
- `weekend_multiplier` (number, min: 0, max: 10, default: 1.0): Weekend multiplier

**Optional Documentation Fields**:
- `documentation` (object): Rich documentation for UI/user guidance
  - `display`: UI display properties (title, subtitle, icon, color_scheme, tags)
  - `overview`: Summary, scenarios, security relevance, compliance frameworks
  - `fields`: Array of field documentation objects
  - `resources`: Links to documentation and tools

**Example**:
```yaml
vendor: paloalto
product: wildfire
data_source: threats
description: "WildFire threat detection events with file analysis results"
format: "CSV"
frequency: "high"

is_generator: true
base_frequency: 12
time_patterns:
  - business_hours
  - night_hours
business_hours_multiplier: 3.0
night_hours_multiplier: 0.4
weekend_multiplier: 0.6

documentation:
  display:
    title: "WildFire Threat Detection"
    subtitle: "Malware and threat analysis events"
    icon: "🛡️"
    color_scheme: "error"
    tags:
      - "threat-detection"
      - "malware"
      - "file-analysis"
```

---

## Validation

All metadata files **must validate** against their respective JSON schemas before submission.

### Schema Files

| Metadata File | Schema File |
|---------------|-------------|
| `vendor.meta.yaml` | `schemas/vendor.schema.json` |
| `product.meta.yaml` | `schemas/product.schema.json` |
| `collection.json` | `schemas/collection.schema.json` |
| `{template_name}.meta.yaml` | `schemas/template.schema.json` |

**Note**: The `schemas/entity.schema.json` file defines the schema for MELTr entity registry files (`entities.yaml`), which are used by the MELTr application itself for synthetic log generation. This is separate from template repository schemas.

### Validation Tools

**Python (recommended)**:
```bash
pip install pyyaml jsonschema
python validate.py vendor.meta.yaml schemas/vendor.schema.json
```

**Node.js**:
```bash
npm install -g ajv-cli
ajv validate -s schemas/vendor.schema.json -d vendor.meta.yaml
```

**Online**:
- Convert YAML to JSON: https://onlineyamltools.com/convert-yaml-to-json
- Validate JSON Schema: https://www.jsonschemavalidator.net/

### Common Validation Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `vendor` does not match directory name | Mismatch between directory and metadata | Ensure `vendor` field matches directory name exactly |
| Missing required field | Required field omitted | Add all required fields per schema |
| Invalid template path format | Wrong path structure in `collection.json` | Use format: `{data_source}/{template_name}` |
| `data_source` at wrong level | Field in vendor/product metadata | Only include `data_source` in template metadata |
| Invalid multiplier value | Value outside 0-10 range | Keep frequency multipliers between 0 and 10 |

---

## Best Practices

### Naming Conventions

**Vendor IDs** (`vendor` field):
- Lowercase only
- Alphanumeric characters
- Hyphens for separation (no underscores)
- Examples: `paloalto`, `microsoft`, `cisco-meraki`

**Product IDs** (`product` field):
- Lowercase only
- Alphanumeric characters
- Hyphens for separation (no underscores)
- Examples: `wildfire`, `windows`, `asa-firewall`

**Data Source Names** (directory names):
- Lowercase only
- Alphanumeric characters
- Underscores for separation (no hyphens)
- Examples: `threats`, `security`, `user_activity`, `network_traffic`

**Template Names** (file names without extensions):
- Lowercase only
- Alphanumeric characters
- Underscores for separation (no hyphens)
- Descriptive and specific
- Examples: `login_success`, `threat_detected`, `file_analysis_complete`

### Metadata Completeness

**Minimum viable metadata**:
- All required fields populated
- Clear, concise descriptions
- Valid URLs where applicable

**Recommended metadata**:
- Logo for vendor (improves UI/UX)
- Documentation URLs for products
- Maintainer information in collections
- Tags for discoverability
- Rich documentation for frequently-used templates

### Version Management

**Collection versions** follow semantic versioning:
- `MAJOR.MINOR.PATCH` format (e.g., `1.0.0`)
- Increment `MAJOR` for breaking changes
- Increment `MINOR` for new templates
- Increment `PATCH` for template fixes/improvements

### Frequency Multipliers

**Multiplier Guidelines**:
- Use **1.0** for no change (default)
- Use **0.0** to completely disable during that time period
- Use **0.1-0.5** for significantly reduced activity
- Use **2.0-5.0** for moderate increases
- Use **5.0-10.0** for major spikes (use sparingly)

**Realistic patterns**:
- Business hours: 2.0-4.0 (2-4x normal activity)
- Night hours: 0.2-0.5 (20-50% of normal)
- Weekends: 0.3-0.7 (30-70% of normal)

---

## Contributing

### Quick Start for New Vendors

**Checklist**:
1. ✅ Create vendor directory: `{vendor}/`
2. ✅ Add `vendor.meta.yaml` with required fields
3. ✅ Create product directory: `{vendor}/{product}/`
4. ✅ Add `product.meta.yaml` with required fields
5. ✅ Add `collection.json` with template index
6. ✅ Create data source directory: `{vendor}/{product}/{data_source}/`
7. ✅ Add template files: `{template_name}.j2` and `{template_name}.meta.yaml`
8. ✅ Validate all metadata files against schemas
9. ✅ Test template rendering
10. ✅ Submit pull request

### Quick Start for New Products

**Checklist** (assuming vendor exists):
1. ✅ Create product directory: `{vendor}/{product}/`
2. ✅ Add `product.meta.yaml` with required fields
3. ✅ Add `collection.json` with template index
4. ✅ Create data source directory: `{vendor}/{product}/{data_source}/`
5. ✅ Add template files: `{template_name}.j2` and `{template_name}.meta.yaml`
6. ✅ Validate all metadata files against schemas
7. ✅ Test template rendering
8. ✅ Update vendor `vendor.meta.yaml` if needed
9. ✅ Submit pull request

### Quick Start for New Templates

**Checklist** (assuming vendor and product exist):
1. ✅ Create or navigate to data source directory: `{vendor}/{product}/{data_source}/`
2. ✅ Add template file: `{template_name}.j2`
3. ✅ Add metadata file: `{template_name}.meta.yaml`
4. ✅ Add template path to `collection.json` templates array
5. ✅ Validate metadata file against `schemas/template.schema.json`
6. ✅ Test template rendering
7. ✅ Update collection version in `collection.json`
8. ✅ Submit pull request

### Contribution Guidelines

**Before submitting**:
- Validate all metadata files against schemas
- Ensure directory structure follows three-level hierarchy
- Test templates with sample entity registry
- Include clear commit messages
- Reference any related issues

**Pull request structure**:
```
[Vendor] Action: Brief description

- Added/Updated/Fixed: specific changes
- Validated against schemas
- Tested with: test configuration details
```

**Example PR titles**:
- `[PaloAlto] Add: WildFire threat detection templates`
- `[Microsoft] Update: Windows Security event metadata`
- `[Cisco] Fix: ASA firewall log format correction`

---

## Directory Reference

### Complete Example Structure
```
repository-root/
├── schemas/
│   ├── vendor.schema.json
│   ├── product.schema.json
│   ├── collection.schema.json
│   └── template.schema.json
├── paloalto/
│   ├── vendor.meta.yaml
│   ├── wildfire/
│   │   ├── product.meta.yaml
│   │   ├── collection.json
│   │   ├── threats/
│   │   │   ├── wildfire_threat_detected.j2
│   │   │   ├── wildfire_threat_detected.meta.yaml
│   │   │   ├── advanced_threat.j2
│   │   │   └── advanced_threat.meta.yaml
│   │   └── analysis/
│   │       ├── file_analysis_complete.j2
│   │       └── file_analysis_complete.meta.yaml
│   └── firewall/
│       ├── product.meta.yaml
│       ├── collection.json
│       └── network/
│           ├── traffic_log.j2
│           └── traffic_log.meta.yaml
├── microsoft/
│   ├── vendor.meta.yaml
│   └── windows/
│       ├── product.meta.yaml
│       ├── collection.json
│       ├── security/
│       │   ├── login_success.j2
│       │   ├── login_success.meta.yaml
│       │   ├── login_failure.j2
│       │   └── login_failure.meta.yaml
│       └── system/
│           ├── service_start.j2
│           └── service_start.meta.yaml
└── README.md
```

---

## Entity Registry Schema

The `entity.schema.json` file defines the schema for MELTr entity registry files (`entities.yaml`). This schema is used by the MELTr application itself for synthetic log generation, separate from template repository schemas.

### Purpose

Entity registry files define the organizational structure, users, devices, and services that are used as data sources when generating synthetic logs. Templates reference these entities to create realistic log entries.

### Schema File

| File | Schema File |
|------|-------------|
| `entities.yaml` | `schemas/entity.schema.json` |

### Required Sections

1. **`organization`** (object, required): Organization-wide configuration
   - Required fields: `name`, `domain`
   - Optional fields: `netbios_domain`, `timezone`, `industry`, `location`, `contacts`, `settings`

2. **`users`** (array, required, min 1): List of user entities
   - Required fields per user: `username`, `email`, `full_name`
   - Usernames and emails must be unique (case-insensitive)
   - Optional fields: `user_id`, `department`, `title`, `is_admin`, `employee_type`, `location`, `organization`, and custom attributes

3. **`devices`** (array, required, min 1): List of device entities
   - Required fields per device: `hostname`, `ip_address`, `mac_address`
   - Hostnames must be unique
   - IP addresses validated as IPv4 or IPv6
   - MAC addresses validated (format: `XX:XX:XX:XX:XX:XX` or `XX-XX-XX-XX-XX-XX`)
   - Optional fields: `fqdn`, `device_id`, `os_type`, `os_version`, `owner`, `device_type`, `model`, `department`, `status`, `last_updated`, and custom attributes

4. **`services`** (array, required, min 1): List of service entities
   - Required fields per service: `name`, `port`, `protocol`
   - Service names must be unique
   - Ports must be integers between 1 and 65535
   - Optional fields: `service_id`, `description`, `owner`, `url`, and custom attributes

5. **`network_ranges`** (array, optional): Network ranges for IP generation
   - Each range must have either:
     - `cidr` (CIDR notation), OR
     - `start_ip` and `end_ip` (both required, start_ip < end_ip)
   - Optional fields: `name`, `description`, `location`, `security_level`

### Validation

Entity registry files are validated by the MELTr application using both:
- JSON Schema validation (`entity.schema.json`)
- Programmatic validation (`src/meltr/entities/validator.py`)

The programmatic validator enforces additional constraints:
- Uniqueness checks (usernames, emails, hostnames, service names)
- Format validation (email, IP address, MAC address)
- Business logic (e.g., start_ip < end_ip for network ranges)

### Example Structure

```yaml
organization:
  name: "Acme Corporation"
  domain: "acme.com"
  timezone: "America/New_York"
  contacts:
    security: "security@acme.com"
    it_support: "support@acme.com"

network_ranges:
  - cidr: "10.1.0.0/16"
    name: "office"
  - start_ip: "192.168.1.0"
    end_ip: "192.168.1.255"
    name: "vpn"

users:
  - username: "jsmith"
    email: "jsmith@acme.com"
    full_name: "John Smith"
    department: "IT"
    is_admin: true

devices:
  - hostname: "WS001"
    ip_address: "192.168.1.101"
    mac_address: "00:1A:2B:3C:4D:5E"
    os_type: "Windows 10"
    device_type: "desktop"

services:
  - name: "Web Server"
    port: 80
    protocol: "HTTP"
```

### Validation Tools

**Python**:
```bash
pip install pyyaml jsonschema
python -c "import yaml, json, jsonschema; data = yaml.safe_load(open('entities.yaml')); schema = json.load(open('schemas/entity.schema.json')); jsonschema.validate(data, schema)"
```

**Using MELTr CLI**:
```bash
meltr entities validate
```
