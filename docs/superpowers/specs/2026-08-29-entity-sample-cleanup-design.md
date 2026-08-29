# Entity sample cleanup design

**Date:** 2026-08-29  
**Status:** Approved  
**Repo:** MELTr

## Goal

Sample entity registries should read like `schemas/entity.schema.json`. One file demos `additionalProperties` for vertical extensibility.

## Decisions

| Decision | Choice |
|----------|--------|
| Layout | One showcase + rest schema-lean |
| Showcase | `examples/entities/acme_healthcare_entities.yaml` |
| Lean field set | Required + common documented optionals (not required-only, not every schema prop dump) |
| Showcase customs | Small healthcare set on users/devices/services |
| Method | Scripted allowlist strip + light rewrite pass |

## Scope

**In**

- All `examples/entities/*.yaml`
- Verify `src/meltr/data/entities.sample.yaml` already lean

**Out**

- Schema changes
- Deleting themed files
- Shrinking entity counts / renaming characters
- Changing packaged init sample unless it has extras

## Field policy

### Lean allowlist (documented schema properties)

- **Org:** `name`, `domain`, `netbios_domain`, `timezone`, `industry`, `location`, `contacts`, `settings`
- **Org location:** `address`, `city`, `state`, `zip`, `country`, `lat`, `long`
- **Org settings:** `password_expiry_days`, `account_lockout_threshold`, `session_timeout_minutes`, `max_login_attempts`, `min_password_length`, `require_mfa`
- **Users:** `username`, `email`, `full_name`, `user_id`, `department`, `title`, `is_admin`, `employee_type`, `location`, `organization`
- **User location:** `city`, `state`, `country`
- **Devices:** `hostname`, `fqdn`, `ip_address`, `mac_address`, `device_id`, `os_type`, `os_version`, `owner`, `device_type`, `model`, `department`, `status`, `last_updated`
- **Services:** `name`, `port`, `protocol`, `service_id`, `description`, `owner`, `url`
- **Network ranges:** `cidr` / `start_ip`+`end_ip`, `name`, `description`, `location`, `security_level`

Drop undocumented org keys (`motto`, `founded`, `ticker_symbol`, `corporate_status`, `secondary_locations`, …) and all joke/lore extras.

### Acme showcase customs (keep / re-add after strip)

- Users (role-appropriate): `hipaa_trained`, `medical_license`, `nursing_license`
- Devices (subset): `hipaa_compliant`, `medical_device_class`
- Services (clinical): `hipaa_compliant`

### Light rewrite pass

- Trim joke contact roles to normal IT/security/hr-style roles (Acme may keep `compliance` / `privacy`)
- Preserve theme in names/hostnames/depts
- Fix broken `owner` → username refs if any
- Optional header comment: schema-lean vs extensibility showcase

## Verify

Validate each file against `schemas/entity.schema.json` after edits.
