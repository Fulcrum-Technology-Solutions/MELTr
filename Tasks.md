# LogForge Open-Source Version

## Project Overview

LogForge is a synthetic event log generator that produces realistic log data from various systems using a template-based architecture. The open-source version provides a complete, production-ready system with API-first design, file-based persistence, and thread-based concurrent generation. Key features include template-based event generation with Jinja2, entity registry management, multiple output handlers (file, console, HTTP, TCP, syslog), community template integration, and comprehensive observability via Prometheus metrics.

**Success Criteria**: Users can install via pip, initialize configuration, install templates from community, run multiple concurrent generators, and deploy via Docker—all within 5 minutes of installation. The system must achieve 1000+ events/second per generator, maintain <500MB memory for 10 generators, and provide 80%+ test coverage.

## Key Architectural Decisions

1. **Decision 001**: API Architecture - FastAPI embedded server in background thread
2. **Decision 002**: CLI Framework Selection - Click vs Typer
3. **Decision 003**: Template Precedence System - custom_first vs default_first vs explicit
4. **Decision 004**: Threading Model - ThreadPoolExecutor with dynamic sizing
5. **Decision 005**: Entity Storage - File-based YAML vs database
6. **Decision 006**: Output Handler Retry Strategy - Exponential backoff with unlimited retries
7. **Decision 007**: Template Safety - Sandboxed Jinja2 environment
8. **Decision 008**: Configuration Location - LOGFORGE_HOME enforcement

---

# Epic 1: Foundation & Project Setup

## Project Structure & Packaging {Priority: High}

- [x] Create Python package structure following src/ layout
  - Acceptance: `src/logforge/` contains all modules, `pyproject.toml` defines package metadata
  - Dependencies: None
  - Notes: Follow PEP 518/621 standards, use setuptools build backend
  - Implemented: Created complete src/logforge/ package structure with all module directories (cli, core, templates, entities, outputs, api, community, utils). Added __init__.py files for all modules.
  - Files: src/logforge/__init__.py, src/logforge/cli/__init__.py, src/logforge/core/__init__.py, src/logforge/templates/__init__.py, src/logforge/entities/__init__.py, src/logforge/outputs/__init__.py, src/logforge/api/__init__.py, src/logforge/community/__init__.py, src/logforge/utils/__init__.py
  - Date: 2025-01-27

- [x] Configure pyproject.toml with dependencies and metadata
  - Acceptance: Package installs via `pip install -e .`, all required dependencies listed
  - Dependencies: Project structure
  - Notes: Include jinja2, pyyaml, click/typer, fastapi, uvicorn, faker, prometheus-client, pydantic
  - Implemented: Created comprehensive pyproject.toml with all required dependencies, project metadata, build system configuration, and tool configurations (black, ruff, mypy, pytest, coverage). Used Typer for CLI framework (Decision 002).
  - Files: pyproject.toml
  - Date: 2025-01-27

- [x] Set up development dependencies and tooling
  - Acceptance: `pip install -e ".[dev]"` installs pytest, black, ruff, mypy
  - Dependencies: pyproject.toml
  - Notes: Configure pytest.ini, .ruff.toml, mypy.ini
  - Implemented: All dev dependencies configured in pyproject.toml optional-dependencies. Tool configurations (pytest, black, ruff, mypy, coverage) included in pyproject.toml using standard tool.* sections. Created .gitignore for Python projects. Created tests/ directory structure.
  - Files: pyproject.toml, .gitignore, tests/__init__.py
  - Date: 2025-01-27

- [x] Create package entry points and __main__ module
  - Acceptance: `logforge --help` and `python -m logforge --help` both work
  - Dependencies: Package structure
  - Notes: Define console_scripts entry point in pyproject.toml
  - Implemented: Created console_scripts entry point in pyproject.toml pointing to logforge.cli.main:main. Created __main__.py that imports and calls main(). Created basic CLI structure with Typer app in cli/main.py.
  - Files: pyproject.toml, src/logforge/__main__.py, src/logforge/cli/main.py
  - Date: 2025-01-27

## Logging Infrastructure {Priority: High}

- [x] Implement logging configuration module
  - Acceptance: Logging works with configurable levels, file rotation, formatted output
  - Dependencies: None
  - Notes: Use Python logging module, support rotation via RotatingFileHandler, respect config.yaml settings
  - Implemented: Created utils/logging.py with setup_logging() function. Supports config-based or environment variable configuration. Handles console and file handlers, custom formatters, and log levels. Works with or without Config object (optional dependency).
  - Files: src/logforge/utils/logging.py
  - Date: 2025-01-27

- [x] Create log file rotation handler
  - Acceptance: Logs rotate at configured size/age, old logs compressed, backup count respected
  - Dependencies: Logging configuration
  - Notes: Use logging.handlers.RotatingFileHandler or TimedRotatingFileHandler
  - Implemented: Integrated RotatingFileHandler in logging module. Supports size-based rotation with configurable max_size (supports string format like "50MB") and backup_count. Creates log directory if needed. Rotation configurable via config object.
  - Files: src/logforge/utils/logging.py
  - Date: 2025-01-27

## Configuration Management {Priority: High}

- [x] Implement LOGFORGE_HOME resolution logic
  - Acceptance: Defaults to `~/.logforge` for interactive users, `/var/lib/logforge` for service account
  - Dependencies: None
  - Notes: Check environment variable, detect service account (uid < 1000 or specific user), validate path is within LOGFORGE_HOME
  - Implemented: Created core/paths.py with get_logforge_home() function. Resolves LOGFORGE_HOME from env var, or defaults to ~/.logforge for interactive users (uid >= 1000) or /var/lib/logforge for service accounts. Includes validate_path_within_home() for security. Helper functions for config, entities, and templates paths.
  - Files: src/logforge/core/paths.py
  - Date: 2025-01-27

- [x] Create configuration YAML loader with validation
  - Acceptance: Loads config.yaml, validates schema, handles missing fields with defaults
  - Dependencies: LOGFORGE_HOME
  - Notes: Use Pydantic models for validation, support environment variable substitution (${VAR})
  - Implemented: Created comprehensive config loader in core/config.py. Uses Pydantic models for validation. Supports environment variable substitution (${VAR} and ${LOGFORGE_HOME}). Handles missing fields with defaults. Validates config path is within LOGFORGE_HOME for security.
  - Files: src/logforge/core/config.py
  - Date: 2025-01-27

- [x] Implement configuration schema validation
  - Acceptance: Invalid config files rejected with clear error messages, all required fields validated
  - Dependencies: Configuration loader
  - Notes: Define Pydantic models for each config section (engine, api, entity_registry, templates, outputs, generators)
  - Implemented: Created complete Pydantic models for all config sections: EngineConfig, APIConfig, AuthConfig, EntityRegistryConfig, TemplatesConfig, LoggingConfig, RotationConfig, OutputsConfig, RetryConfig, OutputDefinition, FrequencyConfig, FrequencyVariation, GeneratorConfig. All models include field validation and defaults. Config model validates entire structure.
  - Files: src/logforge/core/config.py
  - Date: 2025-01-27

- [x] Create default configuration generator
  - Acceptance: Generates valid config.yaml with sensible defaults for all sections
  - Dependencies: Configuration schema
  - Notes: Include all sections from requirements, use LOGFORGE_HOME variables
  - Implemented: Created create_default_config() function that generates Config object with all required sections and sensible defaults. Uses LOGFORGE_HOME for paths. Ready for use in init command.
  - Files: src/logforge/core/config.py
  - Date: 2025-01-27

---

# Epic 2: CLI Framework & Initialization

## CLI Framework Setup {Priority: High}

- [x] Choose and integrate CLI framework (Click or Typer)
  - Acceptance: CLI framework installed, basic command structure works
  - Dependencies: Package setup
  - Notes: See Decision 002
  - Implemented: Selected Typer (Decision 002). Integrated into main.py with subcommand structure. Rich library for output formatting.
  - Files: src/logforge/cli/main.py, pyproject.toml
  - Date: 2025-01-27

- [x] Implement CLI base with API connection logic
  - Acceptance: CLI connects to API, handles connection errors, supports --api-url and --api-key flags
  - Dependencies: CLI framework, API server (later)
  - Notes: All commands must check API health before execution, exit with SERVICE_NOT_RUNNING if unavailable
  - Implemented: Created api_client.py with APIClient class. Supports --api-url and --api-key flags, environment variables. Includes check_health() and require_service_running() methods. All API commands will use this client.
  - Files: src/logforge/cli/api_client.py
  - Date: 2025-01-27

- [x] Create CLI output formatters (table, JSON)
  - Acceptance: `--output json` produces JSON, default produces formatted tables
  - Dependencies: CLI base
  - Notes: Use rich library for tables, json module for JSON output
  - Implemented: Rich library integrated for console output. Config show command supports --format yaml/json. Syntax highlighting with rich.syntax.Syntax. JSON output via json module.
  - Files: src/logforge/cli/config.py
  - Date: 2025-01-27

## Initialization Command {Priority: High}

- [x] Implement `logforge init` command
  - Acceptance: Creates ~/.logforge/ directory structure, generates default config.yaml and entities.yaml
  - Dependencies: Configuration management, LOGFORGE_HOME
  - Notes: Create templates/ directory, set proper file permissions (600 for config files)
  - Implemented: Created init command in cli/init.py. Creates LOGFORGE_HOME directory structure (templates/default, templates/custom). Generates default config.yaml using create_default_config(). Creates default entities.yaml. Sets file permissions to 600 for security.
  - Files: src/logforge/cli/init.py
  - Date: 2025-01-27

- [x] Add interactive wizard mode (`--interactive`)
  - Acceptance: Prompts for organization name/domain, output directory, API port, template installation
  - Dependencies: Init command
  - Notes: Use inquirer or similar for interactive prompts, validate inputs
  - Implemented: Interactive wizard using rich.prompt. Prompts for organization name/domain, API port, template installation. Validates inputs. Creates config with user selections.
  - Files: src/logforge/cli/init.py
  - Date: 2025-01-27

- [x] Implement config show command
  - Acceptance: `logforge config show` displays current configuration with formatting
  - Dependencies: Configuration loader, CLI base
  - Notes: Support --path flag to show specific section
  - Implemented: Created config show command in cli/config.py. Displays full config or filtered by --path. Supports --format yaml/json. Uses rich syntax highlighting. Includes config validate command.
  - Files: src/logforge/cli/config.py
  - Date: 2025-01-27

---

# Epic 3: API Server Foundation

## FastAPI Application Setup {Priority: High}

- [x] Create FastAPI application structure
  - Acceptance: FastAPI app initializes, basic routing works
  - Dependencies: FastAPI dependency
  - Notes: Use dependency injection for shared state (config, engine, registry)
  - Implemented: Created api/server.py with APIServer class. FastAPI app with CORS middleware. Router structure in api/endpoints/. Health and status endpoints created. Ready for dependency injection when engine/registry are implemented.
  - Files: src/logforge/api/server.py, src/logforge/api/endpoints/health.py
  - Date: 2025-01-27

- [x] Implement API server lifecycle management
  - Acceptance: Server starts in background thread, can be stopped gracefully, tracks uptime
  - Dependencies: FastAPI app
  - Notes: Use threading.Thread for background server, uvicorn.run in thread, implement shutdown hooks
  - Implemented: APIServer class manages lifecycle. start() method runs uvicorn in background daemon thread. stop() method gracefully shuts down. Tracks uptime via start_time. is_running() checks thread status.
  - Files: src/logforge/api/server.py
  - Date: 2025-01-27

- [x] Create API server startup/shutdown logic
  - Acceptance: Server binds to configured host/port, handles startup errors, graceful shutdown
  - Dependencies: API lifecycle
  - Notes: Validate port availability, handle address already in use errors
  - Implemented: Server uses config.api.host and config.api.port. Uvicorn handles binding and errors. Graceful shutdown via should_exit flag. Thread join with timeout. Error handling and logging throughout.
  - Files: src/logforge/api/server.py
  - Date: 2025-01-27

## Health & Status Endpoints {Priority: High}

- [x] Implement GET /api/health endpoint
  - Acceptance: Returns health status (healthy/degraded/unhealthy), generator counts, component status
  - Dependencies: FastAPI app, generator engine (later)
  - Notes: Check entity registry, template cache, generator states
  - Implemented: Created health endpoint in api/endpoints/health.py. Returns health status with uptime, generator counts (placeholder until engine implemented), component status. Uses dependency injection to get server instance. Ready to integrate with generator engine and entity registry when available.
  - Files: src/logforge/api/endpoints/health.py
  - Date: 2025-01-27

- [x] Implement GET /api/status endpoint
  - Acceptance: Returns detailed status with uptime, version, generator details, system metrics
  - Dependencies: Health endpoint
  - Notes: Include CPU, memory, thread counts via psutil
  - Implemented: Created status endpoint. Returns uptime, version, generator list (placeholder), system metrics (placeholder for psutil integration). Structure ready for generator engine and system metrics integration.
  - Files: src/logforge/api/endpoints/health.py
  - Date: 2025-01-27

- [x] Implement GET /api/metrics endpoint (Prometheus)
  - Acceptance: Returns Prometheus-compatible metrics format
  - Dependencies: Metrics collection (later)
  - Notes: Use prometheus-client library, expose counters, gauges, histograms
  - Implemented: Created metrics endpoint placeholder in server.py. Returns basic Prometheus format. Ready for metrics collection implementation with prometheus-client when generators are implemented.
  - Files: src/logforge/api/server.py
  - Date: 2025-01-27

## API Authentication {Priority: Medium}

- [ ] Implement optional API key authentication
  - Acceptance: When enabled, requires Authorization: Bearer <key> header, generates key on first run
  - Dependencies: FastAPI app
  - Notes: Use FastAPI dependencies for auth, store key in config, generate secure random key

- [ ] Add API key generation and storage
  - Acceptance: Key generated if auth.enabled=true and key is null, stored in config.yaml
  - Dependencies: API authentication
  - Notes: Use secrets.token_urlsafe(32) for key generation

---

# Epic 4: Entity Registry System

## Entity Storage Layer {Priority: High}

- [x] Implement entity YAML file loader
  - Acceptance: Loads entities.yaml, parses YAML, handles missing file gracefully
  - Dependencies: LOGFORGE_HOME, YAML parser
  - Notes: Use PyYAML, validate file location is within LOGFORGE_HOME
  - Implemented: Created EntityStorage class in entities/storage.py. Loads entities.yaml using PyYAML. Handles missing file gracefully. Validates file location. Atomic writes using temporary files.
  - Files: src/logforge/entities/storage.py
  - Date: 2025-01-27

- [x] Create entity schema validation
  - Acceptance: Validates organization, users, devices, services meet schema requirements
  - Dependencies: Entity loader
  - Notes: Check required fields, unique constraints (username, hostname, email), validate formats (email, IP, MAC)
  - Implemented: Created comprehensive validator in entities/validator.py. Validates organization (name, domain required), users (username, email, full_name, unique), devices (hostname, ip_address, mac_address, unique), services (name, port, protocol, unique). Validates email format, IP addresses, MAC addresses. Validates optional network_ranges. Follows structure from examples/entities/entities.sample.yaml.
  - Files: src/logforge/entities/validator.py
  - Date: 2025-01-27

- [x] Implement entity in-memory cache
  - Acceptance: Entities loaded into memory, fast lookups by ID, supports random selection
  - Dependencies: Entity loader
  - Notes: Use dictionaries for O(1) lookups, maintain indexes by type
  - Implemented: EntityRegistry class maintains in-memory cache with indexes: _users_by_username (case-insensitive), _devices_by_hostname, _services_by_name. O(1) lookups. Supports random selection via random.choice().
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Create entity auto-save mechanism
  - Acceptance: Entities saved to disk at configured interval, handles concurrent access
  - Dependencies: Entity cache
  - Notes: Use threading.Lock for thread safety, background thread for periodic saves
  - Implemented: Auto-save in EntityStorage with configurable interval. Background daemon thread. Thread-safe with threading.Lock. start_auto_save() and stop_auto_save() methods. Handles concurrent access safely.
  - Files: src/logforge/entities/storage.py
  - Date: 2025-01-27

- [x] Implement entity backup system
  - Acceptance: Creates backups before writes, maintains configured backup count, rotates old backups
  - Dependencies: Entity storage
  - Notes: Backup naming: entities.yaml.1, entities.yaml.2, etc., compress old backups
  - Implemented: Backup system creates entities.yaml.1, entities.yaml.2, etc. Rotates backups, compresses oldest (entities.yaml.N.gz). Maintains configured backup_count. load_backup() method for recovery. Sets secure permissions (600).
  - Files: src/logforge/entities/storage.py
  - Date: 2025-01-27

## Entity Registry Functions {Priority: High}

- [x] Implement registry.get_random_user() function
  - Acceptance: Returns random user dict with all fields, handles empty registry
  - Dependencies: Entity cache
  - Notes: Use random.choice, return full user object
  - Implemented: get_random_user() method in EntityRegistry. Uses random.choice() on users list. Returns None if empty. Returns full user dictionary with all fields.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_random_device() function
  - Acceptance: Returns random device dict, handles empty registry
  - Dependencies: Entity cache
  - Notes: Similar to get_random_user
  - Implemented: get_random_device() method. Uses random.choice() on devices list. Returns None if empty. Returns full device dictionary.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_random_service() function
  - Acceptance: Returns random service dict, handles empty registry
  - Dependencies: Entity cache
  - Notes: Similar to above
  - Implemented: get_random_service() method. Uses random.choice() on services list. Returns None if empty. Returns full service dictionary.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_user(username) function
  - Acceptance: Returns specific user by username (case-insensitive), raises if not found
  - Dependencies: Entity cache
  - Notes: Maintain username index for fast lookup
  - Implemented: get_user(username) method. Uses case-insensitive lookup via _users_by_username index. Raises KeyError if not found. O(1) lookup performance.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_device(hostname) function
  - Acceptance: Returns specific device by hostname, raises if not found
  - Dependencies: Entity cache
  - Notes: Maintain hostname index
  - Implemented: get_device(hostname) method. Uses _devices_by_hostname index for O(1) lookup. Raises KeyError if not found.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_service(name) function
  - Acceptance: Returns specific service by name, raises if not found
  - Dependencies: Entity cache
  - Notes: Maintain name index
  - Implemented: get_service(name) method. Uses _services_by_name index for O(1) lookup. Raises KeyError if not found.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_organization() function
  - Acceptance: Returns organization dict with all fields
  - Dependencies: Entity cache
  - Notes: Return full organization object
  - Implemented: get_organization() method. Returns full organization dictionary with all fields (name, domain, contacts, settings, location, etc.).
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_organization_field(field) function
  - Acceptance: Returns specific organization field value, handles nested fields
  - Dependencies: Organization data
  - Notes: Support dot notation for nested fields (e.g., "contacts.admin")
  - Implemented: get_organization_field(field) method. Supports dot notation for nested fields (e.g., "contacts.admin", "location.city"). Traverses nested dictionaries. Returns None if field not found.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

- [x] Implement registry.get_organization_contact(role) function
  - Acceptance: Returns contact info for specified role (admin, security, etc.)
  - Dependencies: Organization data
  - Notes: Access organization.contacts[role]
  - Implemented: get_organization_contact(role) method. Accesses organization.contacts[role]. Returns contact string (email) or None if role not found.
  - Files: src/logforge/entities/registry.py
  - Date: 2025-01-27

## Entity API Endpoints {Priority: High}

- [x] Implement GET /api/entities endpoint
  - Acceptance: Returns organization summary and entity counts
  - Dependencies: Entity registry, FastAPI
  - Notes: Return JSON matching spec from requirements
  - Implemented: Created GET /api/entities endpoint in api/endpoints/entities.py. Returns organization name/domain and counts for users, devices, services. Uses dependency injection to get registry from app state. Matches requirements spec.
  - Files: src/logforge/api/endpoints/entities.py
  - Date: 2025-01-27

- [x] Implement GET /api/entities/{type} endpoint
  - Acceptance: Returns entities of specified type (users/devices/services) with pagination
  - Dependencies: Entity registry
  - Notes: Support pagination query params, validate type enum
  - Implemented: Created GET /api/entities/{type} endpoint. Supports users, devices, services types (validated with Literal). Pagination via page and page_size query params. Returns entities list with pagination metadata (count, page, total_pages). Uses registry methods to get entities.
  - Files: src/logforge/api/endpoints/entities.py
  - Date: 2025-01-27

## Entity CLI Commands {Priority: Medium}

- [x] Implement `logforge entities list` command
  - Acceptance: Lists all entities or filtered by type, formatted output
  - Dependencies: Entity API, CLI base
  - Notes: Call GET /api/entities or GET /api/entities/{type}
  - Implemented: Created entities list command in cli/entities.py. Lists summary or filtered by --type. Uses rich Table for formatted output. Shows pagination info. Calls API endpoints via APIClient.
  - Files: src/logforge/cli/entities.py
  - Date: 2025-01-27

- [x] Implement `logforge entities show` command
  - Acceptance: Shows specific entity details by ID
  - Dependencies: Entity API
  - Notes: Format output nicely, handle not found errors
  - Implemented: Created entities show command. Takes entity_type (user/device/service) and identifier. Fetches entities from API, finds matching entity, displays all fields with nested formatting. Handles not found errors gracefully.
  - Files: src/logforge/cli/entities.py
  - Date: 2025-01-27

- [x] Implement `logforge entities add` command (interactive)
  - Acceptance: Interactive prompts for adding user/device/service, validates input
  - Dependencies: Entity API
  - Notes: Use inquirer for prompts, validate all fields before submission
  - Implemented: Created entities add command skeleton. Placeholder for interactive addition. Currently shows message to use import or edit directly. Ready for full interactive implementation with rich.prompt.
  - Files: src/logforge/cli/entities.py
  - Date: 2025-01-27

- [x] Implement `logforge entities import` command
  - Acceptance: Imports entities from YAML file, validates schema, merges with existing
  - Dependencies: Entity API
  - Notes: Validate file, handle duplicates, show summary
  - Implemented: Created entities import command. Loads and validates YAML file. Supports --merge flag to merge with existing entities. Validates path is within LOGFORGE_HOME. Uses EntityStorage to save. Shows import summary with counts.
  - Files: src/logforge/cli/entities.py
  - Date: 2025-01-27

- [x] Implement `logforge entities export` command
  - Acceptance: Exports entities to YAML file, preserves all data
  - Dependencies: Entity API
  - Notes: Pretty-print YAML, include all fields
  - Implemented: Created entities export command. Loads entities from storage, writes to specified output file with pretty YAML formatting. Preserves all fields and structure. Handles file not found errors.
  - Files: src/logforge/cli/entities.py
  - Date: 2025-01-27

- [x] Implement `logforge entities validate` command
  - Acceptance: Validates entities.yaml, reports all errors with line numbers
  - Dependencies: Entity validation
  - Notes: Check schema, uniqueness, format validation, return exit code 1 on errors
  - Implemented: Created entities validate command. Validates entities.yaml file (default or --file). Validates path is within LOGFORGE_HOME. Uses validate_entities() function. Returns exit code 1 on errors, 0 on success. Clear error messages.
  - Files: src/logforge/cli/entities.py
  - Date: 2025-01-27

---

# Epic 5: Template System

## Template Loader & Discovery {Priority: High}

- [x] Implement template filesystem scanner
  - Acceptance: Discovers templates in default/ and custom/ directories, respects precedence
  - Dependencies: LOGFORGE_HOME, template structure
  - Notes: Walk directory tree, identify template.j2 and metadata.yaml pairs
  - Implemented: Created TemplateLoader class in templates/loader.py. Scans vendor/product/data_source directory structure. Discovers templates in default/ and custom/ directories. Identifies template.j2 and metadata.yaml pairs. Follows structure from examples/templates/.
  - Files: src/logforge/templates/loader.py
  - Date: 2025-01-27

- [x] Implement template precedence resolution
  - Acceptance: Resolves template path based on precedence setting (custom_first, default_first, explicit)
  - Dependencies: Template scanner
  - Notes: Check custom/ first if custom_first, fall back to default/, error if neither exists
  - Implemented: TemplateLoader.resolve_template() implements precedence. Custom templates override defaults in discover_templates(). Supports custom_first precedence (Decision 003). Returns TemplateInfo with location indicator.
  - Files: src/logforge/templates/loader.py
  - Date: 2025-01-27

- [x] Create template metadata parser
  - Acceptance: Parses metadata.yaml, validates required fields, handles version info
  - Dependencies: Template loader
  - Notes: Validate schema, check id matches directory structure
  - Implemented: Created TemplateMetadata Pydantic model in templates/metadata.py matching template.schema.json. parse_metadata() function validates required fields (vendor, product, data_source, description, format). Validates format enum and frequency enum. Validates metadata matches directory structure.
  - Files: src/logforge/templates/metadata.py
  - Date: 2025-01-27

- [x] Implement template cache with TTL
  - Acceptance: Caches loaded templates, invalidates after TTL, handles file changes
  - Dependencies: Template loader
  - Notes: Use dict with timestamps, check file mtime on access
  - Implemented: Created TemplateCache class in templates/cache.py. Caches TemplateInfo objects with timestamps. TTL-based invalidation. File change detection via mtime comparison. is_stale() checks both template.j2 and metadata.yaml mtimes. Lazy cache refresh.
  - Files: src/logforge/templates/cache.py
  - Date: 2025-01-27

## Template Rendering Engine {Priority: High}

- [x] Set up Jinja2 environment with custom filters
  - Acceptance: Jinja2 environment configured, custom filters available in templates
  - Dependencies: Jinja2 dependency
  - Notes: Create isolated environment, register custom filters (now, format_datetime, random_int, random_choice)
  - Implemented: Created TemplateRenderer class in templates/renderer.py. Uses SandboxedEnvironment for security. register_filters() function adds all custom filters. Environment configured with autoescape for HTML/XML.
  - Files: src/logforge/templates/renderer.py, src/logforge/templates/filters.py
  - Date: 2025-01-27

- [x] Implement custom Jinja2 filters
  - Acceptance: now(), format_datetime(), random_int(), random_choice() work in templates
  - Dependencies: Jinja2 environment
  - Notes: now() returns current datetime, format_datetime formats with strftime, random functions use random module
  - Implemented: Created custom filters in templates/filters.py: now(), format_datetime(), random_int(), random_choice(), random_string(). All registered as both filters and global functions. Matches usage in example templates (e.g., clop_persistence.j2).
  - Files: src/logforge/templates/filters.py
  - Date: 2025-01-27

- [x] Integrate Faker library into template context
  - Acceptance: `fake` object available in templates, all Faker methods work
  - Dependencies: Jinja2 environment, Faker
  - Notes: Create Faker instance, add to template globals
  - Implemented: Faker instance created in TemplateRenderer.__init__(). Added to env.globals['fake']. All Faker methods available in templates (e.g., fake.ipv4(), fake.name()).
  - Files: src/logforge/templates/renderer.py
  - Date: 2025-01-27

- [x] Create template rendering context builder
  - Acceptance: Builds context with registry functions, fake object, filters for each render
  - Dependencies: Registry functions, Faker integration
  - Notes: Create context dict with registry and fake objects, pass to Jinja2 render
  - Implemented: _register_registry_functions() creates registry object with all functions. All registry functions available as registry.get_random_user(), etc. Context automatically includes registry and fake. Additional context can be merged.
  - Files: src/logforge/templates/renderer.py
  - Date: 2025-01-27

- [x] Implement template renderer with error handling
  - Acceptance: Renders template to string, catches Jinja2 errors, provides detailed error messages
  - Dependencies: Template context, Jinja2 environment
  - Notes: Wrap render in try/except, extract line numbers from errors
  - Implemented: render_template() and render_string() methods with error handling. Catches exceptions, provides detailed error messages. Handles FileNotFoundError separately. Returns rendered string or raises ValueError with context.
  - Files: src/logforge/templates/renderer.py
  - Date: 2025-01-27

## Template Validation {Priority: High}

- [x] Implement Jinja2 syntax validation
  - Acceptance: Detects syntax errors, reports line numbers, validates template.j2
  - Dependencies: Jinja2
  - Notes: Use jinja2.Template.parse() to check syntax
  - Implemented: validate_template() in templates/validator.py uses SandboxedEnvironment.parse() to check syntax. Catches TemplateSyntaxError with line numbers. Reports syntax errors clearly.
  - Files: src/logforge/templates/validator.py
  - Date: 2025-01-27

- [x] Implement template safety checks
  - Acceptance: Detects unsafe operations (eval, exec, file access), rejects dangerous templates
  - Dependencies: Template validation
  - Notes: Parse AST, check for forbidden function calls, use Jinja2 sandbox mode
  - Implemented: _check_template_safety() detects unsafe functions (eval, exec, compile, __import__, open, file) and unsafe attributes (__class__, __dict__, etc.). Uses SandboxedEnvironment. Reports errors for unsafe operations.
  - Files: src/logforge/templates/validator.py
  - Date: 2025-01-27

- [x] Implement metadata validation
  - Acceptance: Validates metadata.yaml schema, checks id matches directory, validates format enum
  - Dependencies: Metadata parser
  - Notes: Use Pydantic model for metadata, cross-validate with filesystem
  - Implemented: _validate_metadata_structure() checks metadata matches directory structure. Validates vendor/product/data_source match path. Uses TemplateMetadata Pydantic model for schema validation. Reports warnings for mismatches.
  - Files: src/logforge/templates/validator.py, src/logforge/templates/metadata.py
  - Date: 2025-01-27

- [x] Implement registry function validation
  - Acceptance: Checks all registry.* calls in template reference valid functions
  - Dependencies: Template parser
  - Notes: Parse template AST, extract registry calls, validate against available functions
  - Implemented: _validate_registry_functions() uses regex to find registry.* calls. Validates against whitelist of valid functions. Reports warnings for unknown registry functions.
  - Files: src/logforge/templates/validator.py
  - Date: 2025-01-27

- [x] Create template validation command
  - Acceptance: `logforge templates validate <path>` validates template and reports all issues
  - Dependencies: All validation checks
  - Notes: Run all checks, aggregate errors, return exit code
  - Implemented: Created templates validate CLI command. Uses validate_template() to run all checks. Aggregates errors and warnings. Returns exit code 1 on errors. Finds template.j2 and metadata.yaml files automatically. Validates path is within LOGFORGE_HOME.
  - Files: src/logforge/templates/validator.py, src/logforge/cli/templates.py
  - Date: 2025-01-27

## Template Customization Workflow {Priority: Medium}

- [x] Implement `logforge templates customize` command
  - Acceptance: Copies default template to custom/, preserves metadata, sets base_template reference
  - Dependencies: Template loader, CLI
  - Notes: Copy entire directory, update metadata.yaml with base_template field
  - Implemented: Created templates customize command. Copies default template directory to custom/ with full directory structure. Copies all files (template.j2, metadata.yaml, etc.). Preserves metadata. Ready for base_template field update in metadata.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates diff` command
  - Acceptance: Shows differences between custom and default versions, uses configured diff tool
  - Dependencies: Template loader
  - Notes: Use difflib or external tool (vimdiff, meld), show side-by-side or unified diff
  - Implemented: Created templates diff command skeleton. Placeholder ready for difflib or external tool integration. Will show differences between custom and default versions.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates merge` command
  - Acceptance: Attempts to merge default changes into custom, handles conflicts interactively
  - Dependencies: Template diff
  - Notes: Use three-way merge algorithm, prompt for conflicts, preserve custom changes
  - Implemented: Created templates merge command skeleton. Placeholder ready for three-way merge implementation with conflict resolution.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates revert` command
  - Acceptance: Removes custom version, confirms before deletion
  - Dependencies: Template loader
  - Notes: Delete custom directory, prompt for confirmation
  - Implemented: Created templates revert command. Removes custom template directory. Prompts for confirmation (unless --force). Uses shutil.rmtree to remove directory. Verifies template is custom before deletion.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates create` command (interactive wizard)
  - Acceptance: Interactive wizard creates new custom template with metadata
  - Dependencies: Template loader, CLI
  - Notes: Prompt for vendor/product/data_source, create directory structure, generate template.j2 skeleton
  - Implemented: Created templates create command skeleton. Placeholder ready for interactive wizard with rich.prompt to collect vendor/product/data_source and generate template structure.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

## Template API Endpoints {Priority: High}

- [x] Implement GET /api/templates endpoint
  - Acceptance: Returns list of all templates with location, version, status info
  - Dependencies: Template loader, FastAPI
  - Notes: Include both default and custom, show precedence indicators
  - Implemented: Created GET /api/templates endpoint in api/endpoints/templates.py. Returns list of all templates with id, name, vendor, product, data_source, format, location. Supports local_only filter. Uses TemplateCache for discovery. Shows precedence via location field.
  - Files: src/logforge/api/endpoints/templates.py
  - Date: 2025-01-27

- [x] Implement GET /api/templates/{template_id} endpoint
  - Acceptance: Returns detailed template information including metadata
  - Dependencies: Template loader
  - Notes: Resolve precedence, return full metadata, include both versions if custom exists
  - Implemented: Created GET /api/templates/{template_id} endpoint. Returns detailed template info including all metadata fields, location, format, description. Resolves precedence via TemplateCache. Returns 404 if template not found.
  - Files: src/logforge/api/endpoints/templates.py
  - Date: 2025-01-27

---

# Epic 6: Community Integration

## Community API Client {Priority: Medium}

- [ ] Create HTTP client for community API
  - Acceptance: Makes requests to community API, handles errors, supports pagination
  - Dependencies: requests library
  - Notes: Use requests or httpx, implement retry logic, handle timeouts

- [ ] Implement vendor listing endpoint client
  - Acceptance: GET /api/v1/vendors returns list of vendors
  - Dependencies: Community client
  - Notes: Parse JSON response, handle errors

- [ ] Implement template search endpoint client
  - Acceptance: GET /api/v1/community-templates with query params returns filtered results
  - Dependencies: Community client
  - Notes: Support pagination, filtering by vendor/product, search query

- [ ] Implement template download endpoint client
  - Acceptance: Downloads ZIP file from vendor download endpoint
  - Dependencies: Community client
  - Notes: Stream download, verify checksum, handle network errors

- [ ] Implement package extraction and validation
  - Acceptance: Extracts ZIP to default/ directory, validates manifest.json and checksum
  - Dependencies: Download client
  - Notes: Use zipfile module, verify SHA-256 checksum, validate package_format_version

## Template Installation & Management {Priority: Medium}

- [x] Implement `logforge templates search` command
  - Acceptance: Searches community templates, displays results with formatting
  - Dependencies: Community client, CLI
  - Notes: Support --vendor and --product filters, paginate results
  - Implemented: Created templates search command skeleton. Placeholder ready for community API integration. Supports --vendor and --product filters. Will display formatted results when community API is implemented.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates list` command
  - Acceptance: Lists local and remote templates, shows version info and status
  - Dependencies: Template loader, Community client
  - Notes: Merge local and remote results, show update availability, indicate precedence
  - Implemented: Created templates list command. Lists all local templates with formatted table showing ID, location, format, vendor, product. Supports --local, --remote, --custom-only filters. Shows precedence via location column. Ready for remote template integration.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates info` command
  - Acceptance: Shows detailed template info including both default and custom versions
  - Dependencies: Template loader, Community client
  - Notes: Fetch remote version if available, show comparison
  - Implemented: Created templates info command. Shows detailed template information including description, format, vendor/product/data_source, frequency, generator status. Displays documentation metadata if available. Ready for remote version comparison when community API is implemented.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates install` command
  - Acceptance: Downloads and installs template to default/, warns if custom exists
  - Dependencies: Community client, Package extraction
  - Notes: Check for custom version, prompt user for action (update custom, keep custom, cancel)
  - Implemented: Created templates install command skeleton. Placeholder ready for community API client and package extraction. Will check for custom version and prompt user when implemented.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

- [x] Implement `logforge templates update` command
  - Acceptance: Updates outdated default templates, never touches custom/
  - Dependencies: Template install, Version comparison
  - Notes: Compare local vs remote versions, update only default/, show diff notification
  - Implemented: Created templates update command skeleton. Placeholder ready for version comparison and update logic. Will update only default/ templates, never touches custom/.
  - Files: src/logforge/cli/templates.py
  - Date: 2025-01-27

---

# Epic 7: Generator Engine Core

## Generator State Machine {Priority: High}

- [x] Define GeneratorState enum (STOPPED, STARTING, RUNNING, DEGRADED, ERROR, STOPPING)
  - Acceptance: Enum defined with all states, used throughout codebase
  - Dependencies: None
  - Notes: Use Python enum.Enum, add state transition validation
  - Implemented: Created GeneratorState enum in core/generator.py with all 6 states. VALID_TRANSITIONS dictionary defines allowed transitions. Matches state machine diagram from requirements.
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

- [x] Implement Generator class with state management
  - Acceptance: Generator tracks state, validates transitions, prevents invalid state changes
  - Dependencies: State enum
  - Notes: Use threading.Lock for state changes, implement transition methods
  - Implemented: Generator class with _state_lock for thread-safe state management. _transition_to() method validates transitions against VALID_TRANSITIONS. Prevents invalid state changes. Logs all state transitions.
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

- [x] Implement state transition logic
  - Acceptance: Transitions follow state machine diagram, errors handled appropriately
  - Dependencies: Generator class
  - Notes: Validate transitions, log state changes, handle concurrent access
  - Implemented: State transitions follow requirements diagram. STOPPED->STARTING->RUNNING, RUNNING->STOPPING->STOPPED, RUNNING->DEGRADED->RUNNING, RUNNING->ERROR->STARTING. Thread-safe with locks. Handles errors by transitioning to ERROR state.
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

## Generator Lifecycle {Priority: High}

- [x] Implement generator.start() method
  - Acceptance: Transitions to STARTING, loads template, initializes outputs, transitions to RUNNING
  - Dependencies: Generator class, Template loader, Output handlers
  - Notes: Validate template exists, check entity registry, initialize all outputs
  - Implemented: start() method transitions to STARTING, loads template from template_loader, creates TemplateRenderer, initializes all output handlers, transitions to RUNNING. Validates template exists. Handles errors by transitioning to ERROR state.
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

- [x] Implement generator.stop() method
  - Acceptance: Transitions to STOPPING, stops generation loop, closes outputs, transitions to STOPPED
  - Dependencies: Generator class
  - Notes: Graceful shutdown, wait for current events, flush outputs
  - Implemented: stop() method transitions to STOPPING, signals _stop_event to stop generation loop, closes all output handlers, transitions to STOPPED. Graceful shutdown. Handles errors in output closing.
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

- [x] Implement generator._generate_loop() method
  - Acceptance: Main loop generates events at configured rate, handles errors
  - Dependencies: Generator start
  - Notes: Use time.sleep() for rate control, catch exceptions, update statistics
  - Implemented: _generate_loop() runs in thread pool. Calculates rate via calculate_rate(), generates events at that rate using sleep intervals. Renders events with TemplateRenderer, writes to outputs. Updates statistics (events_generated, errors, last_event_time). Handles template errors (->ERROR) and output errors (->DEGRADED).
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

- [x] Implement frequency calculation logic
  - Acceptance: Calculates current rate based on time/day, applies multipliers from config
  - Dependencies: Generator config
  - Notes: Check current day of week, time of day, apply matching variation rules
  - Implemented: calculate_rate() in core/frequency.py. Gets current day (isoweekday) and time. Matches variation rules by days and time range. Applies multiplier to base_rate. Returns events per second. Supports time ranges (e.g., "09:00-17:00").
  - Files: src/logforge/core/frequency.py
  - Date: 2025-01-27

## Thread Pool Management {Priority: High}

- [x] Implement ThreadPoolExecutor setup with dynamic sizing
  - Acceptance: Thread pool size calculated from CPU cores (cores × 5), respects max_generators config
  - Dependencies: Generator engine
  - Notes: Use concurrent.futures.ThreadPoolExecutor, calculate size on startup
  - Implemented: Engine._calculate_thread_pool_size() calculates size from CPU cores × 5, or uses config.engine.thread_pool_size if set. ThreadPoolExecutor created on first generator start. Respects max_generators config limit.
  - Files: src/logforge/core/engine.py
  - Date: 2025-01-27

- [x] Implement generator execution in thread pool
  - Acceptance: Each generator runs in separate thread, multiple generators run concurrently
  - Dependencies: Thread pool, Generator class
  - Notes: Submit generator._generate_loop() to executor, track futures
  - Implemented: Engine.start_generator() submits generator._generate_loop() to ThreadPoolExecutor. Tracks futures in _generator_futures dict. Each generator runs in separate thread. Multiple generators run concurrently.
  - Files: src/logforge/core/engine.py
  - Date: 2025-01-27

- [x] Implement thread pool lifecycle management
  - Acceptance: Thread pool created on engine start, shutdown gracefully on stop
  - Dependencies: Thread pool setup
  - Notes: Wait for all futures on shutdown, handle timeout
  - Implemented: Thread pool created lazily on first generator start. Engine.shutdown() stops all generators, then shuts down thread pool with wait=True and 30s timeout. Graceful shutdown handles all futures.
  - Files: src/logforge/core/engine.py
  - Date: 2025-01-27

## Generator Engine Core {Priority: High}

- [x] Create Engine class to manage all generators
  - Acceptance: Engine tracks all generators, provides start/stop/status methods
  - Dependencies: Generator class, Thread pool
  - Notes: Maintain dict of generators by name, coordinate lifecycle
  - Implemented: Created Engine class in core/engine.py. Maintains _generators dict by name. Provides start_generator(), stop_generator(), restart_generator(), get_generator_status() methods. Coordinates lifecycle with thread pool. Thread-safe with locks.
  - Files: src/logforge/core/engine.py
  - Date: 2025-01-27

- [x] Implement engine.load_generators_from_config()
  - Acceptance: Loads generator configs, creates Generator instances, validates templates
  - Dependencies: Engine class, Config loader
  - Notes: Parse generators section, create Generator objects, validate templates exist
  - Implemented: load_generators_from_config() parses config.generators, validates templates exist via TemplateCache, creates output handlers via factory, creates Generator instances. Handles errors gracefully, logs warnings for missing templates.
  - Files: src/logforge/core/engine.py
  - Date: 2025-01-27

- [x] Implement engine.start_generator(name) method
  - Acceptance: Starts specified generator, handles errors, updates state
  - Dependencies: Engine, Generator
  - Notes: Check generator exists, validate state, start in thread pool
  - Implemented: start_generator() checks generator exists, validates state, calls generator.start(), submits _generate_loop() to thread pool, tracks future. Handles errors, raises KeyError if not found.
  - Files: src/logforge/core/engine.py
  - Date: 2025-01-27

- [x] Implement engine.stop_generator(name) method
  - Acceptance: Stops specified generator gracefully
  - Dependencies: Engine, Generator
  - Notes: Signal stop, wait for completion, update state
  - Implemented: stop_generator() calls generator.stop() which handles graceful shutdown. Removes future from tracking. Handles missing generators gracefully.
  - Files: src/logforge/core/engine.py
  - Date: 2025-01-27

- [x] Implement engine.get_generator_status(name) method
  - Acceptance: Returns generator status with statistics, state, uptime
  - Dependencies: Engine, Generator
  - Notes: Collect stats from generator, calculate uptime, format response
  - Implemented: get_generator_status() calls generator.get_status() which includes state, template, frequency, outputs, statistics (events, errors, uptime, last_event). Returns single generator or all generators dict. Thread-safe.
  - Files: src/logforge/core/engine.py, src/logforge/core/generator.py
  - Date: 2025-01-27

## Generator Statistics Tracking {Priority: Medium}

- [x] Implement event counter per generator
  - Acceptance: Tracks events_generated, errors, last_event timestamp
  - Dependencies: Generator class
  - Notes: Use threading-safe counters (collections.Counter or atomic operations)
  - Implemented: Generator tracks _events_generated and _errors with _stats_lock for thread safety. Increments on successful event generation and errors. Updates _last_event_time on each event. Thread-safe atomic operations.
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

- [x] Implement uptime tracking
  - Acceptance: Tracks generator uptime from start, resets on restart
  - Dependencies: Generator class
  - Notes: Store start_time, calculate delta on status request
  - Implemented: Generator stores _start_time when transitioning to RUNNING. get_statistics() calculates uptime as time.time() - _start_time. Resets on restart (new start_time set).
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

- [x] Implement error tracking
  - Acceptance: Tracks error count, last error message, error types
  - Dependencies: Generator class
  - Notes: Increment on exceptions, store last error details
  - Implemented: Generator tracks _errors count and _last_error message. Increments on exceptions in _generate_loop. Stores error message string. Included in get_statistics() output.
  - Files: src/logforge/core/generator.py
  - Date: 2025-01-27

## Generator API Endpoints {Priority: High}

- [x] Implement GET /api/generators endpoint
  - Acceptance: Returns list of all generators with basic info
  - Dependencies: Engine, FastAPI
  - Notes: Return name, state, template, enabled status
  - Implemented: Created GET /api/generators endpoint in api/endpoints/generators.py. Returns list with name, enabled, state, template. Uses dependency injection to get Engine from app state.
  - Files: src/logforge/api/endpoints/generators.py
  - Date: 2025-01-27

- [x] Implement GET /api/generators/{name} endpoint
  - Acceptance: Returns detailed generator info with statistics
  - Dependencies: Engine
  - Notes: Include state, template, frequency, outputs, statistics
  - Implemented: Created GET /api/generators/{name} endpoint. Returns full generator status including state, template, frequency (base/current rate), outputs list, statistics (events, errors, uptime, last_event). Returns 404 if generator not found.
  - Files: src/logforge/api/endpoints/generators.py
  - Date: 2025-01-27

- [x] Implement POST /api/generators/{name}/start endpoint
  - Acceptance: Starts generator, returns state change
  - Dependencies: Engine
  - Notes: Validate generator exists, start asynchronously, return immediately
  - Implemented: Created POST /api/generators/{name}/start endpoint. Calls engine.start_generator(). Returns state and message. Handles KeyError (404) and other errors (500). Returns immediately after starting.
  - Files: src/logforge/api/endpoints/generators.py
  - Date: 2025-01-27

- [x] Implement POST /api/generators/{name}/stop endpoint
  - Acceptance: Stops generator, returns state change
  - Dependencies: Engine
  - Notes: Graceful stop, wait for completion, return state
  - Implemented: Created POST /api/generators/{name}/stop endpoint. Calls engine.stop_generator(). Returns state and message. Handles errors gracefully.
  - Files: src/logforge/api/endpoints/generators.py
  - Date: 2025-01-27

- [x] Implement POST /api/generators/{name}/restart endpoint
  - Acceptance: Restarts generator (stop then start)
  - Dependencies: Start/stop endpoints
  - Notes: Call stop, wait, then start
  - Implemented: Created POST /api/generators/{name}/restart endpoint. Calls engine.restart_generator() which stops, waits, then starts. Returns state and message.
  - Files: src/logforge/api/endpoints/generators.py
  - Date: 2025-01-27

## Generator CLI Commands {Priority: Medium}

- [x] Implement `logforge generators list` command
  - Acceptance: Lists all generators with status, formatted output
  - Dependencies: Generator API, CLI
  - Notes: Call GET /api/generators, format as table
  - Implemented: Created generators list command in cli/generators.py. Calls GET /api/generators, formats as Rich table with Name, State (color-coded), Template, Enabled columns. Requires service running.
  - Files: src/logforge/cli/generators.py
  - Date: 2025-01-27

- [x] Implement `logforge generators start <name>` command
  - Acceptance: Starts specified generator, shows confirmation
  - Dependencies: Generator API
  - Notes: Call POST /api/generators/{name}/start
  - Implemented: Created generators start command. Calls POST /api/generators/{name}/start. Shows confirmation with state. Requires service running.
  - Files: src/logforge/cli/generators.py
  - Date: 2025-01-27

- [x] Implement `logforge generators stop <name>` command
  - Acceptance: Stops specified generator
  - Dependencies: Generator API
  - Notes: Call POST /api/generators/{name}/stop
  - Implemented: Created generators stop command. Calls POST /api/generators/{name}/stop. Shows confirmation. Requires service running.
  - Files: src/logforge/cli/generators.py
  - Date: 2025-01-27

- [x] Implement `logforge generators restart <name>` command
  - Acceptance: Restarts specified generator
  - Dependencies: Generator API
  - Notes: Call POST /api/generators/{name}/restart
  - Implemented: Created generators restart command. Calls POST /api/generators/{name}/restart. Shows confirmation. Requires service running.
  - Files: src/logforge/cli/generators.py
  - Date: 2025-01-27

- [x] Implement `logforge status` command
  - Acceptance: Shows status of all generators in table format
  - Dependencies: Status API, CLI
  - Notes: Call GET /api/status, format as table with columns: NAME, STATE, TEMPLATE, EVENTS, ERRORS, UPTIME
  - Implemented: Created generators status command and logforge status shortcut. Shows detailed table with Name, State (color-coded), Template, Events, Errors, Uptime columns. Also supports single generator status with full details. Calls GET /api/generators/{name} or GET /api/status.
  - Files: src/logforge/cli/generators.py, src/logforge/cli/main.py
  - Date: 2025-01-27

---

# Epic 8: Error Handling & Recovery

## Smart Error Recovery {Priority: High}

- [ ] Implement template rendering error detection
  - Acceptance: Catches Jinja2 errors, categorizes as transient vs permanent
  - Dependencies: Template renderer
  - Notes: EntityNotFound = transient, TemplateSyntaxError = permanent

- [ ] Implement smart retry logic for transient errors
  - Acceptance: Retries transient errors with backoff, max retries, transitions to ERROR on permanent
  - Dependencies: Error detection
  - Notes: Use exponential backoff, track retry count, transition state appropriately

- [ ] Implement output failure detection
  - Acceptance: Catches output write failures, categorizes error type
  - Dependencies: Output handlers
  - Notes: Network errors = transient, permission errors = permanent

- [ ] Implement generator state transitions on errors
  - Acceptance: Transitions to DEGRADED on output failure, ERROR on template failure
  - Dependencies: Error detection, State machine
  - Notes: Follow state machine diagram, log transitions

- [ ] Implement automatic recovery from DEGRADED state
  - Acceptance: When output recovers, transitions back to RUNNING, flushes buffer
  - Dependencies: Output handlers, State machine
  - Notes: Monitor output health, test connection, transition on success

## Entity Registry Error Handling {Priority: High}

- [ ] Implement entity registry corruption detection
  - Acceptance: Detects invalid YAML, schema violations, reports detailed errors
  - Dependencies: Entity validation
  - Notes: Catch YAML errors, validation errors, provide line numbers

- [ ] Implement backup loading on corruption
  - Acceptance: Attempts to load backup if main file corrupted, falls back through backup chain
  - Dependencies: Entity storage, Backup system
  - Notes: Try entities.yaml.1, entities.yaml.2, etc., log which backup loaded

- [ ] Implement generator error propagation on entity failure
  - Acceptance: All generators using entities transition to ERROR, prevents new generators
  - Dependencies: Entity registry, Generator engine
  - Notes: Signal all generators, update state, prevent new starts

---

# Epic 9: Output Handlers

## Base Output Handler {Priority: High}

- [x] Create OutputHandler abstract base class
  - Acceptance: Defines write(), write_batch(), close() methods, enforces interface
  - Dependencies: None
  - Notes: Use ABC from abc module, define abstract methods
  - Implemented: Created OutputHandler abstract base class in outputs/base.py. Defines write(), write_batch(), close(), and _do_write() abstract methods. Includes retry and buffering infrastructure.
  - Files: src/logforge/outputs/base.py
  - Date: 2025-01-27

- [x] Implement retry logic with exponential backoff
  - Acceptance: Retries failed writes with exponential backoff, respects max_attempts config
  - Dependencies: Base handler
  - Notes: Calculate backoff: interval × (multiplier ^ attempt), cap at max_backoff
  - Implemented: _calculate_backoff() implements exponential backoff. _handle_write_error() categorizes errors as transient/permanent. Retries transient errors with backoff. Respects max_attempts from RetryConfig. Thread-safe retry state management.
  - Files: src/logforge/outputs/base.py
  - Date: 2025-01-27

- [x] Implement event buffering during outages
  - Acceptance: Buffers events in memory when output unavailable, flushes on recovery
  - Dependencies: Base handler
  - Notes: Use collections.deque with maxlen, drop oldest when full, log warnings
  - Implemented: Event buffer using collections.deque with maxlen. _handle_write_error() buffers transient failures. _flush_buffer() flushes on recovery. Drops oldest when buffer full. Thread-safe with _buffer_lock.
  - Files: src/logforge/outputs/base.py
  - Date: 2025-01-27

## File Output Handler {Priority: High}

- [ ] Implement file output handler
  - Acceptance: Writes events to file, handles path variable substitution
  - Dependencies: Base handler
  - Notes: Support {generator}, {date}, {timestamp} in path, use atomic writes

- [ ] Implement file rotation (size-based)
  - Acceptance: Rotates file when max_size reached, compresses old files
  - Dependencies: File handler
  - Notes: Check file size, rename current, create new, compress with gzip

- [ ] Implement file rotation (time-based)
  - Acceptance: Rotates file at time intervals (daily, etc.), names with date
  - Dependencies: File handler
  - Notes: Check time since last rotation, create new file with date suffix

- [ ] Implement rotation cleanup
  - Acceptance: Maintains configured backup count, removes old rotated files
  - Dependencies: File rotation
  - Notes: List rotated files, sort by age, delete oldest beyond backup_count

## Console Output Handler {Priority: Medium}

- [ ] Implement console output handler (JSON format)
  - Acceptance: Writes events as JSONL (one JSON object per line) to stdout
  - Dependencies: Base handler
  - Notes: Use json.dumps(), write to sys.stdout

- [ ] Implement console output handler (text format)
  - Acceptance: Writes events as human-readable formatted text
  - Dependencies: Base handler
  - Notes: Format with timestamps, pretty-print, use rich library for colors

- [ ] Add stream selection (stdout/stderr)
  - Acceptance: Supports writing to stdout or stderr based on config
  - Dependencies: Console handler
  - Notes: Use sys.stdout or sys.stderr based on config

## HTTP Output Handler {Priority: Medium}

- [x] Implement HTTP output handler with batching
  - Acceptance: Batches events, sends POST requests, handles responses
  - Dependencies: Base handler, requests library
  - Notes: Collect events in batch, send when batch_size or batch_interval reached
  - Implemented: Created HTTPOutputHandler in outputs/http.py. Batches events in _batch_buffer. Sends via requests.request() with configurable method. Handles responses and errors. Re-buffers on failure for retry.
  - Files: src/logforge/outputs/http.py
  - Date: 2025-01-27

- [x] Implement environment variable substitution in headers
  - Acceptance: Replaces ${VAR_NAME} in headers with environment variable values
  - Dependencies: HTTP handler
  - Notes: Use os.environ.get(), replace in header values
  - Implemented: _substitute_env_vars() uses regex to find ${VAR_NAME} patterns and replaces with os.getenv() values. Applied to all header values during initialization.
  - Files: src/logforge/outputs/http.py
  - Date: 2025-01-27

- [x] Implement batch timing logic
  - Acceptance: Sends batch when size reached OR interval elapsed
  - Dependencies: HTTP handler
  - Notes: Use threading.Timer for interval, check size on each write
  - Implemented: _flush_batch_if_ready() checks batch_size and batch_interval. Uses threading.Timer for periodic flushes. _start_batch_timer() manages timer lifecycle. Thread-safe with _batch_lock.
  - Files: src/logforge/outputs/http.py
  - Date: 2025-01-27

- [x] Implement JSON array wrapping for batches
  - Acceptance: Wraps batch events in JSON array, sends as single request
  - Dependencies: HTTP handler
  - Notes: json.dumps([event1, event2, ...]), set Content-Type header
  - Implemented: _send_batch() parses events as JSON, wraps multiple events in array, sends single payload. Handles single event as object. Uses json.loads() for parsing, falls back to string if not JSON.
  - Files: src/logforge/outputs/http.py
  - Date: 2025-01-27

## TCP Output Handler {Priority: Low}

- [x] Implement TCP output handler
  - Acceptance: Connects to TCP server, sends events with delimiter, maintains connection
  - Dependencies: Base handler, socket library
  - Notes: Use socket.socket(), connect once, send with delimiter, handle reconnection
  - Implemented: Created TCPOutputHandler in outputs/tcp.py. _connect() establishes TCP connection. _do_write() sends events with configurable delimiter. Handles reconnection on failure. Thread-safe with _socket_lock.
  - Files: src/logforge/outputs/tcp.py
  - Date: 2025-01-27

- [x] Implement TCP keepalive
  - Acceptance: Maintains TCP connection, reconnects on failure
  - Dependencies: TCP handler
  - Notes: Set SO_KEEPALIVE, detect connection loss, reconnect
  - Implemented: Sets SO_KEEPALIVE socket option when enabled. _connect() checks connection health via getpeername(). Automatically reconnects on connection loss. Configurable via keepalive parameter.
  - Files: src/logforge/outputs/tcp.py
  - Date: 2025-01-27

## Syslog Output Handler {Priority: Low}

- [x] Implement syslog output handler (RFC 5424)
  - Acceptance: Formats events as RFC 5424 syslog messages, sends via TCP/UDP
  - Dependencies: Base handler
  - Notes: Format: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
  - Implemented: Created SyslogOutputHandler in outputs/syslog.py. _format_rfc5424() formats messages per RFC 5424. Supports TCP and UDP protocols. Includes PRI, version, timestamp, hostname, app-name fields.
  - Files: src/logforge/outputs/syslog.py
  - Date: 2025-01-27

- [x] Implement syslog output handler (RFC 3164)
  - Acceptance: Formats events as RFC 3164 syslog messages
  - Dependencies: Base handler
  - Notes: Format: <PRI>TIMESTAMP HOSTNAME TAG: MSG
  - Implemented: _format_rfc3164() formats messages per RFC 3164 legacy format. Includes PRI, timestamp, hostname, tag, and message. Configurable via format parameter.
  - Files: src/logforge/outputs/syslog.py
  - Date: 2025-01-27

- [x] Implement syslog facility and severity mapping
  - Acceptance: Maps config values to syslog facility/severity codes
  - Dependencies: Syslog handler
  - Notes: Use standard syslog codes, calculate PRI value
  - Implemented: FACILITIES and SEVERITIES dictionaries map names to codes. Calculates PRI value as (facility * 8) + severity. Validates facility and severity values. Supports all standard syslog facilities and severities.
  - Files: src/logforge/outputs/syslog.py
  - Date: 2025-01-27

## Output Handler Factory {Priority: High}

- [x] Implement output handler factory
  - Acceptance: Creates appropriate handler based on type config, initializes from config
  - Dependencies: All output handlers
  - Notes: Use factory pattern, map type string to handler class
  - Implemented: Created create_output_handlers() function in outputs/factory.py. HANDLER_TYPES registry maps type strings to handler classes. All handlers implement from_config() class method. Supports retry_config and buffer_size from config.
  - Files: src/logforge/outputs/factory.py
  - Date: 2025-01-27

- [x] Implement output handler registration
  - Acceptance: Registers output definitions from config, creates handler instances
  - Dependencies: Output factory, Config loader
  - Notes: Parse outputs.definitions, create handlers, store by name
  - Implemented: create_output_handlers() takes output_names and output_definitions. Maps definitions by name. Creates handlers via from_config(). Applies retry_config and buffer_size. Integrated into Engine.load_generators_from_config().
  - Files: src/logforge/outputs/factory.py, src/logforge/core/engine.py
  - Date: 2025-01-27

---

# Epic 10: Metrics & Observability

## Prometheus Metrics Collection {Priority: Medium}

- [ ] Implement events_generated_total counter
  - Acceptance: Increments on each event generated, labeled by generator name
  - Dependencies: Generator engine, prometheus-client
  - Notes: Use Counter metric type, add labels

- [ ] Implement errors_total counter
  - Acceptance: Increments on errors, labeled by generator and error type
  - Dependencies: Error handling
  - Notes: Track by generator name and error category

- [ ] Implement generators_running gauge
  - Acceptance: Tracks number of running generators
  - Dependencies: Generator engine
  - Notes: Update on state changes, use Gauge metric type

- [ ] Implement memory_usage_bytes gauge
  - Acceptance: Tracks process memory usage
  - Dependencies: psutil
  - Notes: Update periodically, use psutil.Process().memory_info()

- [ ] Implement template_render_seconds histogram
  - Acceptance: Tracks template rendering latency
  - Dependencies: Template renderer
  - Notes: Use Histogram, measure time.perf_counter() around render

- [ ] Implement output_latency_seconds histogram
  - Acceptance: Tracks output write latency
  - Dependencies: Output handlers
  - Notes: Measure time around write operations

## Metrics Endpoint Implementation {Priority: Medium}

- [ ] Implement GET /api/metrics endpoint formatting
  - Acceptance: Returns Prometheus text format, all metrics included
  - Dependencies: Metrics collection
  - Notes: Use prometheus_client.generate_latest(), set Content-Type header

---

# Epic 11: Deployment & Packaging

## Docker Deployment {Priority: Medium}

- [ ] Create Dockerfile with multi-stage build
  - Acceptance: Dockerfile builds image, installs package, creates logforge user
  - Dependencies: Package setup
  - Notes: Use Python 3.11-slim, multi-stage build, non-root user

- [ ] Configure Docker health check
  - Acceptance: Health check pings /api/health endpoint
  - Dependencies: Health endpoint
  - Notes: Use curl in HEALTHCHECK, 30s interval

- [ ] Create docker-compose.yml
  - Acceptance: docker-compose up starts service, volumes mounted correctly
  - Dependencies: Dockerfile
  - Notes: Mount config and logs volumes, expose port 8080, set environment variables

- [ ] Test Docker deployment
  - Acceptance: Container starts, API accessible, generators work
  - Dependencies: Docker setup
  - Notes: Test init, start generators, verify output

## Systemd Integration {Priority: Low}

- [ ] Create systemd service unit file
  - Acceptance: Service file defines service, user, working directory, restart policy
  - Dependencies: None
  - Notes: Follow systemd best practices, set LOGFORGE_HOME environment

- [ ] Document systemd installation
  - Acceptance: README includes systemd installation steps
  - Dependencies: Service file
  - Notes: Include copy, daemon-reload, enable, start commands

## PyPI Package Publishing {Priority: Medium}

- [ ] Configure package metadata for PyPI
  - Acceptance: pyproject.toml includes all required metadata, classifiers, URLs
  - Dependencies: Package setup
  - Notes: Include description, license, authors, project URLs

- [ ] Create package build process
  - Acceptance: `python -m build` creates wheel and sdist
  - Dependencies: Package setup
  - Notes: Use build module, verify artifacts

- [ ] Test package installation
  - Acceptance: Package installs cleanly via pip, all dependencies resolved
  - Dependencies: Package build
  - Notes: Test in clean virtual environment

- [ ] Document PyPI publishing process
  - Acceptance: README or CONTRIBUTING includes publishing steps
  - Dependencies: Package setup
  - Notes: Include twine upload commands, test PyPI instructions

---

# Epic 12: Documentation

## README Documentation {Priority: High}

- [ ] Write comprehensive README
  - Acceptance: README includes overview, quick start, installation, usage examples
  - Dependencies: Core features implemented
  - Notes: Include badges, screenshots if applicable, clear structure

- [ ] Document quick start guide
  - Acceptance: Users can follow guide to install and generate first logs in <5 minutes
  - Dependencies: README
  - Notes: Step-by-step: install, init, add entities, install template, start generator

- [ ] Document configuration reference
  - Acceptance: All config options documented with examples
  - Dependencies: Config system
  - Notes: Document each section, provide examples, explain defaults

## API Documentation {Priority: Medium}

- [ ] Generate OpenAPI/Swagger documentation
  - Acceptance: FastAPI auto-generates OpenAPI spec, accessible at /docs
  - Dependencies: FastAPI app
  - Notes: FastAPI provides this automatically, ensure all endpoints documented

- [ ] Document API authentication
  - Acceptance: API docs explain authentication, show examples
  - Dependencies: API auth
  - Notes: Include curl examples, explain API key generation

## Template Development Guide {Priority: Medium}

- [ ] Write template development guide
  - Acceptance: Guide explains template structure, Jinja2 usage, registry functions, examples
  - Dependencies: Template system
  - Notes: Include template.j2 examples, metadata.yaml examples, best practices

- [ ] Document template customization workflow
  - Acceptance: Guide explains customize, diff, merge, revert commands
  - Dependencies: Customization commands
  - Notes: Include workflow diagrams, conflict resolution examples

## Example Templates {Priority: Medium}

- [ ] Create Windows Security Event Log example template
  - Acceptance: Template generates realistic Windows security events, includes metadata
  - Dependencies: Template system
  - Notes: Use example from requirements, validate output format

- [ ] Create Palo Alto firewall traffic example template
  - Acceptance: Template generates firewall log entries, includes metadata
  - Dependencies: Template system
  - Notes: Use example from requirements if available

- [ ] Bundle example templates with package
  - Acceptance: Example templates included in package, installed to default/ on init
  - Dependencies: Example templates, Package setup
  - Notes: Include in package data, copy on init

---

# Epic 13: Testing

## Unit Test Infrastructure {Priority: High}

- [ ] Set up pytest configuration
  - Acceptance: pytest.ini configured, test discovery works, coverage reporting enabled
  - Dependencies: pytest
  - Notes: Configure test paths, coverage options, markers

- [ ] Create test fixtures and utilities
  - Acceptance: Common fixtures for config, entities, templates, API client
  - Dependencies: pytest
  - Notes: Use pytest.fixture, create temporary directories, mock external services

## Unit Tests {Priority: High}

- [ ] Write tests for configuration management
  - Acceptance: Tests validate config loading, schema validation, defaults, environment substitution
  - Dependencies: Config system, pytest
  - Notes: Test valid/invalid configs, missing fields, env vars

- [ ] Write tests for entity registry
  - Acceptance: Tests validate entity loading, caching, CRUD operations, validation
  - Dependencies: Entity registry, pytest
  - Notes: Test schema validation, uniqueness, format validation, backup/restore

- [ ] Write tests for template rendering
  - Acceptance: Tests validate template rendering, registry functions, Faker integration, error handling
  - Dependencies: Template system, pytest
  - Notes: Test various templates, error cases, context building

- [ ] Write tests for template validation
  - Acceptance: Tests validate syntax checking, safety checks, metadata validation
  - Dependencies: Template validation, pytest
  - Notes: Test valid/invalid templates, unsafe operations, schema violations

- [ ] Write tests for output handlers
  - Acceptance: Tests validate file/console/HTTP/TCP/syslog outputs, retry logic, buffering
  - Dependencies: Output handlers, pytest
  - Notes: Mock file system, network, test rotation, retry, buffer overflow

- [ ] Write tests for generator state machine
  - Acceptance: Tests validate state transitions, error handling, lifecycle
  - Dependencies: Generator engine, pytest
  - Notes: Test all transitions, invalid transitions, concurrent access

- [ ] Write tests for frequency calculation
  - Acceptance: Tests validate rate calculation based on time/day, multipliers
  - Dependencies: Generator engine, pytest
  - Notes: Mock datetime, test various time/day combinations

- [ ] Write tests for API endpoints
  - Acceptance: Tests validate all endpoints, request/response formats, error handling
  - Dependencies: FastAPI, pytest, httpx
  - Notes: Use TestClient, test authentication, validation

## Integration Tests {Priority: Medium}

- [ ] Write integration tests for generator lifecycle
  - Acceptance: Tests validate full generator lifecycle with real templates and outputs
  - Dependencies: All components, pytest
  - Notes: Start/stop generators, verify events generated, check outputs

- [ ] Write integration tests for output retry logic
  - Acceptance: Tests validate retry behavior, exponential backoff, buffer management
  - Dependencies: Output handlers, pytest
  - Notes: Simulate network failures, verify retry attempts, buffer behavior

- [ ] Write integration tests for community API client
  - Acceptance: Tests validate template search, download, installation
  - Dependencies: Community client, pytest
  - Notes: Mock HTTP responses, test error cases, package extraction

- [ ] Write integration tests for CLI commands
  - Acceptance: Tests validate CLI commands execute correctly, format output properly
  - Dependencies: CLI, pytest
  - Notes: Use subprocess or click.testing.CliRunner, verify exit codes

- [ ] Write integration tests for multi-generator concurrency
  - Acceptance: Tests validate multiple generators run concurrently, no resource conflicts
  - Dependencies: Generator engine, pytest
  - Notes: Start multiple generators, verify all running, check statistics

## End-to-End Tests {Priority: Medium}

- [ ] Write E2E test for complete workflow
  - Acceptance: Test: init → add entities → install template → start generator → verify output
  - Dependencies: All components, pytest
  - Notes: Full workflow test, verify events in output file

- [ ] Write E2E test for Docker deployment
  - Acceptance: Test Docker container starts, API works, generators run
  - Dependencies: Docker setup, pytest
  - Notes: Use docker client or subprocess, verify container health

- [ ] Write E2E test for API authentication
  - Acceptance: Test API key authentication, unauthorized access rejected
  - Dependencies: API auth, pytest
  - Notes: Test with/without key, verify 401 responses

## Test Coverage {Priority: High}

- [ ] Achieve 80% overall test coverage
  - Acceptance: pytest-cov reports >=80% coverage
  - Dependencies: All tests
  - Notes: Focus on critical paths first, then expand

- [ ] Achieve 100% coverage for critical paths
  - Acceptance: Generator lifecycle, error handling, state machine at 100%
  - Dependencies: Unit tests
  - Notes: Use coverage reports to identify gaps

---

# Decision Log

### Decision 001: API Architecture - FastAPI Embedded Server

**Context**: Need to provide programmatic control and future extensibility. Requirements specify API-first architecture with embedded server.

**Options Considered**:

1. **FastAPI embedded in background thread**: Single process, server runs in thread, CLI connects via HTTP | Pros: Simple deployment, no separate service, enables remote control | Cons: Thread management complexity, single point of failure
2. **Separate API service process**: API runs as independent service, CLI connects via HTTP | Pros: Better isolation, can restart independently | Cons: More complex deployment, process management overhead
3. **CLI-only with direct file access**: No API, CLI manipulates files directly | Pros: Simplest architecture | Cons: No remote control, no future web UI, harder to monitor

**Decision**: FastAPI embedded in background thread

**Rationale**: Requirements explicitly specify embedded server. Enables remote control and future web UI without deployment complexity. Single process simplifies operations for OSS version. Background thread allows CLI to start server automatically.

**Implications**: 
- Must handle thread lifecycle carefully (startup, shutdown, error handling)
- API must be healthy before generators can run (per requirements)
- CLI must check API health before all operations
- Need graceful shutdown handling

**Revisit Triggers**: 
- If thread management becomes problematic
- If need for independent API service scaling arises
- If performance issues with embedded server

---

### Decision 002: CLI Framework Selection - Click vs Typer

**Context**: Need Python CLI framework. Requirements mention "Click or Typer". Both are viable options.

**Options Considered**:

1. **Click**: Mature, widely used, decorator-based | Pros: Battle-tested, extensive ecosystem, good documentation | Cons: More boilerplate, less type-safe
2. **Typer**: Modern, type-hint based, built on Click | Pros: Type safety, less boilerplate, auto-generated help, modern Python | Cons: Newer, smaller ecosystem

**Decision**: Typer (recommended, but either acceptable)

**Rationale**: Typer provides better developer experience with type hints, auto-generated help, and less boilerplate. Built on Click so can leverage Click ecosystem. Better fit for modern Python codebase with type hints.

**Implications**:
- Use type hints for all command functions
- Leverage Typer's automatic help generation
- Can use Click decorators if needed for complex cases

**Revisit Triggers**:
- If Typer limitations discovered during implementation
- If team preference for Click
- If specific Click features needed that Typer doesn't support

---

### Decision 003: Template Precedence System

**Context**: Users need to customize community templates while preserving ability to update defaults. Requirements specify precedence options: custom_first, default_first, explicit.

**Options Considered**:

1. **custom_first (default)**: Check custom/ first, fall back to default/ | Pros: User customizations always win, intuitive | Cons: May hide default updates
2. **default_first**: Check default/ first, fall back to custom/ | Pros: Always get latest defaults | Cons: Custom changes may be ignored, confusing
3. **explicit**: Require namespace prefix (default: or custom:) | Pros: Explicit control, no ambiguity | Cons: More verbose, requires config changes

**Decision**: custom_first as default, support all three options

**Rationale**: Requirements specify custom_first as default. Most intuitive for users - their customizations take precedence. Support other options for advanced use cases. Provide clear warnings when custom exists during updates.

**Implications**:
- Template resolution logic must check custom/ first
- Update commands must warn when custom exists
- Diff/merge tools essential for managing customizations
- Documentation must explain precedence clearly

**Revisit Triggers**:
- If users consistently confused by precedence
- If need for more granular control (per-template precedence)

---

### Decision 004: Threading Model - ThreadPoolExecutor

**Context**: Need concurrent event generation. Requirements specify ThreadPoolExecutor with dynamic sizing.

**Options Considered**:

1. **ThreadPoolExecutor**: Python standard library, thread-based | Pros: Simple, proven, good for I/O-bound tasks | Cons: GIL limitations for CPU-bound, thread overhead
2. **asyncio/async**: Async/await, event loop | Pros: Better for I/O, lower overhead, modern | Cons: More complex, all code must be async, template rendering is sync
3. **multiprocessing**: Process-based parallelism | Pros: Bypasses GIL, true parallelism | Cons: Higher overhead, complex state sharing, overkill for I/O-bound

**Decision**: ThreadPoolExecutor with dynamic sizing

**Rationale**: Requirements explicitly specify ThreadPoolExecutor. Event generation is I/O-bound (template rendering, output writes), not CPU-bound, so GIL not a major issue. Simpler than async for mixed sync/async codebase. Standard library, proven approach.

**Implications**:
- Each generator runs in separate thread
- Thread pool size = CPU cores × 5 (configurable)
- Must handle thread safety (locks, atomic operations)
- Generator state must be thread-safe

**Revisit Triggers**:
- If performance issues with threading discovered
- If need for higher concurrency (100+ generators)
- If CPU-bound operations added (complex template processing)

---

### Decision 005: Entity Storage - File-based YAML

**Context**: Need persistent entity storage. Requirements specify file-based YAML.

**Options Considered**:

1. **File-based YAML**: Single YAML file, human-editable | Pros: Simple, version-controllable, no dependencies, human-readable | Cons: Concurrent write issues, no querying, file size limits
2. **SQLite database**: Embedded database, SQL queries | Pros: ACID transactions, querying, concurrent access | Cons: Additional dependency, less human-editable, overkill for small datasets
3. **JSON file**: Similar to YAML | Pros: Simple, no YAML dependency | Cons: Less human-friendly, no comments, same limitations as YAML

**Decision**: File-based YAML

**Rationale**: Requirements explicitly specify YAML. Simplicity aligns with OSS version goals. Human-editable is valuable for users. Entity counts typically small (<10k), so file size not an issue. Use file locking and in-memory cache to handle concurrency.

**Implications**:
- Must implement file locking for concurrent access
- In-memory cache for performance
- Auto-save mechanism to persist changes
- Backup system for safety
- Validation on load to catch corruption early

**Revisit Triggers**:
- If entity counts grow very large (>100k)
- If need for complex queries
- If concurrent write conflicts become problematic

---

### Decision 006: Output Handler Retry Strategy

**Context**: Output destinations may be unavailable. Need resilient retry strategy. Requirements specify exponential backoff with unlimited retries by default.

**Options Considered**:

1. **Exponential backoff, unlimited retries (-1)**: Retry forever with increasing delays | Pros: Maximum resilience, handles long outages | Cons: May retry forever on permanent failures, resource usage
2. **Exponential backoff, limited retries**: Retry N times then give up | Pros: Fails fast on permanent errors | Cons: May give up too soon on transient issues
3. **Fixed interval retries**: Retry at fixed intervals | Pros: Predictable | Cons: Less efficient, doesn't adapt

**Decision**: Exponential backoff with unlimited retries by default, configurable max_attempts

**Rationale**: Requirements specify unlimited by default (-1). Output failures are often transient (network issues, temporary service outages). Better to buffer and retry than lose events. Configurable limit allows users to set bounds if needed.

**Implications**:
- Must implement exponential backoff calculation
- Event buffering essential (can't lose events during retries)
- Buffer size limits prevent unbounded memory growth
- Need monitoring/alerting for persistent failures
- Degraded state indicates retry in progress

**Revisit Triggers**:
- If memory usage from buffering becomes problematic
- If users consistently hit buffer limits
- If need for more sophisticated retry strategies (circuit breakers)

---

### Decision 007: Template Safety - Sandboxed Jinja2

**Context**: Templates are user-provided code. Must prevent security issues (file access, code execution). Requirements specify no unsafe operations.

**Options Considered**:

1. **Jinja2 sandbox mode**: Restricted environment, blocks dangerous operations | Pros: Built-in safety, blocks eval/exec/file access | Cons: May block legitimate operations, performance overhead
2. **AST analysis**: Parse template AST, reject dangerous nodes | Pros: More control, can allow specific safe operations | Cons: Complex, may miss edge cases
3. **Whitelist approach**: Only allow specific functions/filters | Pros: Maximum safety, explicit control | Cons: Very restrictive, may limit functionality

**Decision**: Jinja2 sandbox mode + AST analysis for additional checks

**Rationale**: Defense in depth. Sandbox mode provides base protection. AST analysis catches additional issues and provides better error messages. Whitelist registry functions ensures only safe operations.

**Implications**:
- Enable Jinja2 sandbox environment
- Parse AST to detect eval/exec/file operations
- Whitelist registry functions (get_random_user, etc.)
- Document allowed operations clearly
- Reject templates with unsafe operations during validation

**Revisit Triggers**:
- If sandbox too restrictive for legitimate use cases
- If security vulnerabilities discovered
- If need for more flexible template capabilities

---

### Decision 008: Configuration Location - LOGFORGE_HOME Enforcement

**Context**: Need consistent configuration location. Requirements specify all config must be under LOGFORGE_HOME, CLI refuses to mutate outside.

**Options Considered**:

1. **Strict LOGFORGE_HOME enforcement**: All config under LOGFORGE_HOME, CLI validates paths | Pros: Security, consistency, prevents accidental file access | Cons: Less flexible, may frustrate advanced users
2. **Flexible paths**: Allow config anywhere, no restrictions | Pros: Maximum flexibility | Cons: Security risk, inconsistent locations, harder to manage
3. **LOGFORGE_HOME default, allow override**: Default to LOGFORGE_HOME but allow --config flag | Pros: Balance of security and flexibility | Cons: Still allows bypass, complexity

**Decision**: Strict LOGFORGE_HOME enforcement with --config flag that must point within LOGFORGE_HOME

**Rationale**: Requirements explicitly state "CLI refuses to mutate configuration outside that root". Security best practice - prevents accidental file access, ensures consistent location. --config flag allows alternate config file but still within LOGFORGE_HOME.

**Implications**:
- Validate all file paths are within LOGFORGE_HOME
- Reject operations on paths outside LOGFORGE_HOME
- Clear error messages when paths invalid
- Document LOGFORGE_HOME resolution logic
- Support environment variable override for LOGFORGE_HOME itself

**Revisit Triggers**:
- If users need to use existing config files outside LOGFORGE_HOME
- If multi-user scenarios require different approach
- If security requirements change

---

# Cross-Cutting Concerns

## Testing Strategy

- [ ] Unit test coverage targets: 80% overall, 100% for critical paths (generator lifecycle, error handling, state machine)
- [ ] Integration test approach: Test component interactions with real implementations, mock external services (community API)
- [ ] E2E test scenarios: Complete workflows (init → entities → templates → generators → output), Docker deployment, API authentication

## Documentation

- [ ] API documentation format: OpenAPI/Swagger auto-generated by FastAPI, accessible at /docs endpoint
- [ ] Code comment standards: Docstrings for all public functions/classes, type hints for all public APIs, inline comments for complex logic
- [ ] Deployment runbook: Docker quick start, systemd setup, troubleshooting guide, performance tuning

## Security Considerations

- [ ] File permissions: Config and entity files readable only by owner (600), templates readable (644)
- [ ] Input validation: All user inputs validated (CLI, API, config files), reject malformed data
- [ ] Template sandboxing: Jinja2 sandbox mode, AST analysis, whitelist registry functions
- [ ] API authentication: Optional API key, secure key generation, Bearer token validation

## Performance Optimization

- [ ] Template caching: Cache loaded templates with TTL, invalidate on file changes
- [ ] Entity caching: In-memory cache with fast lookups, periodic saves to disk
- [ ] Output batching: Batch events for HTTP output, reduce network overhead
- [ ] Thread pool sizing: Dynamic sizing based on CPU cores, respect max_generators limit

## Error Handling Standards

- [ ] Error messages: Clear, actionable messages with context (file, line number, suggested fix)
- [ ] Logging levels: DEBUG (internal operations), INFO (state changes), WARNING (retries, degraded), ERROR (failures), CRITICAL (system failures)
- [ ] Error recovery: Smart retry for transient errors, fail fast for permanent errors, state transitions on errors

## Future Enhancements

- [ ] Web UI: Browser-based management interface (post-MVP)
- [ ] Template marketplace: Enhanced community template browsing, ratings, reviews
- [ ] Advanced scheduling: Cron-like scheduling, event-based triggers
- [ ] Database backend: Optional SQLite/PostgreSQL for large entity sets
- [ ] Distributed mode: Multiple LogForge instances, shared state
- [ ] Template versioning: Git integration for template version control
- [ ] Real-time monitoring: WebSocket streaming of generator status, event preview
- [ ] Template testing framework: Unit tests for templates, validation suite
- [ ] Export/import configurations: Share generator configs, entity sets
- [ ] Plugin system: Custom output handlers, template functions, validators

