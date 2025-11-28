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

- [ ] Create Python package structure following src/ layout
  - Acceptance: `src/logforge/` contains all modules, `pyproject.toml` defines package metadata
  - Dependencies: None
  - Notes: Follow PEP 518/621 standards, use setuptools build backend

- [ ] Configure pyproject.toml with dependencies and metadata
  - Acceptance: Package installs via `pip install -e .`, all required dependencies listed
  - Dependencies: Project structure
  - Notes: Include jinja2, pyyaml, click/typer, fastapi, uvicorn, faker, prometheus-client, pydantic

- [ ] Set up development dependencies and tooling
  - Acceptance: `pip install -e ".[dev]"` installs pytest, black, ruff, mypy
  - Dependencies: pyproject.toml
  - Notes: Configure pytest.ini, .ruff.toml, mypy.ini

- [ ] Create package entry points and __main__ module
  - Acceptance: `logforge --help` and `python -m logforge --help` both work
  - Dependencies: Package structure
  - Notes: Define console_scripts entry point in pyproject.toml

## Logging Infrastructure {Priority: High}

- [ ] Implement logging configuration module
  - Acceptance: Logging works with configurable levels, file rotation, formatted output
  - Dependencies: None
  - Notes: Use Python logging module, support rotation via RotatingFileHandler, respect config.yaml settings

- [ ] Create log file rotation handler
  - Acceptance: Logs rotate at configured size/age, old logs compressed, backup count respected
  - Dependencies: Logging configuration
  - Notes: Use logging.handlers.RotatingFileHandler or TimedRotatingFileHandler

## Configuration Management {Priority: High}

- [ ] Implement LOGFORGE_HOME resolution logic
  - Acceptance: Defaults to `~/.logforge` for interactive users, `/var/lib/logforge` for service account
  - Dependencies: None
  - Notes: Check environment variable, detect service account (uid < 1000 or specific user), validate path is within LOGFORGE_HOME

- [ ] Create configuration YAML loader with validation
  - Acceptance: Loads config.yaml, validates schema, handles missing fields with defaults
  - Dependencies: LOGFORGE_HOME
  - Notes: Use Pydantic models for validation, support environment variable substitution (${VAR})

- [ ] Implement configuration schema validation
  - Acceptance: Invalid config files rejected with clear error messages, all required fields validated
  - Dependencies: Configuration loader
  - Notes: Define Pydantic models for each config section (engine, api, entity_registry, templates, outputs, generators)

- [ ] Create default configuration generator
  - Acceptance: Generates valid config.yaml with sensible defaults for all sections
  - Dependencies: Configuration schema
  - Notes: Include all sections from requirements, use LOGFORGE_HOME variables

---

# Epic 2: CLI Framework & Initialization

## CLI Framework Setup {Priority: High}

- [ ] Choose and integrate CLI framework (Click or Typer)
  - Acceptance: CLI framework installed, basic command structure works
  - Dependencies: Package setup
  - Notes: See Decision 002

- [ ] Implement CLI base with API connection logic
  - Acceptance: CLI connects to API, handles connection errors, supports --api-url and --api-key flags
  - Dependencies: CLI framework, API server (later)
  - Notes: All commands must check API health before execution, exit with SERVICE_NOT_RUNNING if unavailable

- [ ] Create CLI output formatters (table, JSON)
  - Acceptance: `--output json` produces JSON, default produces formatted tables
  - Dependencies: CLI base
  - Notes: Use rich library for tables, json module for JSON output

## Initialization Command {Priority: High}

- [ ] Implement `logforge init` command
  - Acceptance: Creates ~/.logforge/ directory structure, generates default config.yaml and entities.yaml
  - Dependencies: Configuration management, LOGFORGE_HOME
  - Notes: Create templates/ directory, set proper file permissions (600 for config files)

- [ ] Add interactive wizard mode (`--interactive`)
  - Acceptance: Prompts for organization name/domain, output directory, API port, template installation
  - Dependencies: Init command
  - Notes: Use inquirer or similar for interactive prompts, validate inputs

- [ ] Implement config show command
  - Acceptance: `logforge config show` displays current configuration with formatting
  - Dependencies: Configuration loader, CLI base
  - Notes: Support --path flag to show specific section

---

# Epic 3: API Server Foundation

## FastAPI Application Setup {Priority: High}

- [ ] Create FastAPI application structure
  - Acceptance: FastAPI app initializes, basic routing works
  - Dependencies: FastAPI dependency
  - Notes: Use dependency injection for shared state (config, engine, registry)

- [ ] Implement API server lifecycle management
  - Acceptance: Server starts in background thread, can be stopped gracefully, tracks uptime
  - Dependencies: FastAPI app
  - Notes: Use threading.Thread for background server, uvicorn.run in thread, implement shutdown hooks

- [ ] Create API server startup/shutdown logic
  - Acceptance: Server binds to configured host/port, handles startup errors, graceful shutdown
  - Dependencies: API lifecycle
  - Notes: Validate port availability, handle address already in use errors

## Health & Status Endpoints {Priority: High}

- [ ] Implement GET /api/health endpoint
  - Acceptance: Returns health status (healthy/degraded/unhealthy), generator counts, component status
  - Dependencies: FastAPI app, generator engine (later)
  - Notes: Check entity registry, template cache, generator states

- [ ] Implement GET /api/status endpoint
  - Acceptance: Returns detailed status with uptime, version, generator details, system metrics
  - Dependencies: Health endpoint
  - Notes: Include CPU, memory, thread counts via psutil

- [ ] Implement GET /api/metrics endpoint (Prometheus)
  - Acceptance: Returns Prometheus-compatible metrics format
  - Dependencies: Metrics collection (later)
  - Notes: Use prometheus-client library, expose counters, gauges, histograms

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

- [ ] Implement entity YAML file loader
  - Acceptance: Loads entities.yaml, parses YAML, handles missing file gracefully
  - Dependencies: LOGFORGE_HOME, YAML parser
  - Notes: Use PyYAML, validate file location is within LOGFORGE_HOME

- [ ] Create entity schema validation
  - Acceptance: Validates organization, users, devices, services meet schema requirements
  - Dependencies: Entity loader
  - Notes: Check required fields, unique constraints (username, hostname, email), validate formats (email, IP, MAC)

- [ ] Implement entity in-memory cache
  - Acceptance: Entities loaded into memory, fast lookups by ID, supports random selection
  - Dependencies: Entity loader
  - Notes: Use dictionaries for O(1) lookups, maintain indexes by type

- [ ] Create entity auto-save mechanism
  - Acceptance: Entities saved to disk at configured interval, handles concurrent access
  - Dependencies: Entity cache
  - Notes: Use threading.Lock for thread safety, background thread for periodic saves

- [ ] Implement entity backup system
  - Acceptance: Creates backups before writes, maintains configured backup count, rotates old backups
  - Dependencies: Entity storage
  - Notes: Backup naming: entities.yaml.1, entities.yaml.2, etc., compress old backups

## Entity Registry Functions {Priority: High}

- [ ] Implement registry.get_random_user() function
  - Acceptance: Returns random user dict with all fields, handles empty registry
  - Dependencies: Entity cache
  - Notes: Use random.choice, return full user object

- [ ] Implement registry.get_random_device() function
  - Acceptance: Returns random device dict, handles empty registry
  - Dependencies: Entity cache
  - Notes: Similar to get_random_user

- [ ] Implement registry.get_random_service() function
  - Acceptance: Returns random service dict, handles empty registry
  - Dependencies: Entity cache
  - Notes: Similar to above

- [ ] Implement registry.get_user(username) function
  - Acceptance: Returns specific user by username (case-insensitive), raises if not found
  - Dependencies: Entity cache
  - Notes: Maintain username index for fast lookup

- [ ] Implement registry.get_device(hostname) function
  - Acceptance: Returns specific device by hostname, raises if not found
  - Dependencies: Entity cache
  - Notes: Maintain hostname index

- [ ] Implement registry.get_service(name) function
  - Acceptance: Returns specific service by name, raises if not found
  - Dependencies: Entity cache
  - Notes: Maintain name index

- [ ] Implement registry.get_organization() function
  - Acceptance: Returns organization dict with all fields
  - Dependencies: Entity cache
  - Notes: Return full organization object

- [ ] Implement registry.get_organization_field(field) function
  - Acceptance: Returns specific organization field value, handles nested fields
  - Dependencies: Organization data
  - Notes: Support dot notation for nested fields (e.g., "contacts.admin")

- [ ] Implement registry.get_organization_contact(role) function
  - Acceptance: Returns contact info for specified role (admin, security, etc.)
  - Dependencies: Organization data
  - Notes: Access organization.contacts[role]

## Entity API Endpoints {Priority: High}

- [ ] Implement GET /api/entities endpoint
  - Acceptance: Returns organization summary and entity counts
  - Dependencies: Entity registry, FastAPI
  - Notes: Return JSON matching spec from requirements

- [ ] Implement GET /api/entities/{type} endpoint
  - Acceptance: Returns entities of specified type (users/devices/services) with pagination
  - Dependencies: Entity registry
  - Notes: Support pagination query params, validate type enum

## Entity CLI Commands {Priority: Medium}

- [ ] Implement `logforge entities list` command
  - Acceptance: Lists all entities or filtered by type, formatted output
  - Dependencies: Entity API, CLI base
  - Notes: Call GET /api/entities or GET /api/entities/{type}

- [ ] Implement `logforge entities show` command
  - Acceptance: Shows specific entity details by ID
  - Dependencies: Entity API
  - Notes: Format output nicely, handle not found errors

- [ ] Implement `logforge entities add` command (interactive)
  - Acceptance: Interactive prompts for adding user/device/service, validates input
  - Dependencies: Entity API
  - Notes: Use inquirer for prompts, validate all fields before submission

- [ ] Implement `logforge entities import` command
  - Acceptance: Imports entities from YAML file, validates schema, merges with existing
  - Dependencies: Entity API
  - Notes: Validate file, handle duplicates, show summary

- [ ] Implement `logforge entities export` command
  - Acceptance: Exports entities to YAML file, preserves all data
  - Dependencies: Entity API
  - Notes: Pretty-print YAML, include all fields

- [ ] Implement `logforge entities validate` command
  - Acceptance: Validates entities.yaml, reports all errors with line numbers
  - Dependencies: Entity validation
  - Notes: Check schema, uniqueness, format validation, return exit code 1 on errors

---

# Epic 5: Template System

## Template Loader & Discovery {Priority: High}

- [ ] Implement template filesystem scanner
  - Acceptance: Discovers templates in default/ and custom/ directories, respects precedence
  - Dependencies: LOGFORGE_HOME, template structure
  - Notes: Walk directory tree, identify template.j2 and metadata.yaml pairs

- [ ] Implement template precedence resolution
  - Acceptance: Resolves template path based on precedence setting (custom_first, default_first, explicit)
  - Dependencies: Template scanner
  - Notes: Check custom/ first if custom_first, fall back to default/, error if neither exists

- [ ] Create template metadata parser
  - Acceptance: Parses metadata.yaml, validates required fields, handles version info
  - Dependencies: Template loader
  - Notes: Validate schema, check id matches directory structure

- [ ] Implement template cache with TTL
  - Acceptance: Caches loaded templates, invalidates after TTL, handles file changes
  - Dependencies: Template loader
  - Notes: Use dict with timestamps, check file mtime on access

## Template Rendering Engine {Priority: High}

- [ ] Set up Jinja2 environment with custom filters
  - Acceptance: Jinja2 environment configured, custom filters available in templates
  - Dependencies: Jinja2 dependency
  - Notes: Create isolated environment, register custom filters (now, format_datetime, random_int, random_choice)

- [ ] Implement custom Jinja2 filters
  - Acceptance: now(), format_datetime(), random_int(), random_choice() work in templates
  - Dependencies: Jinja2 environment
  - Notes: now() returns current datetime, format_datetime formats with strftime, random functions use random module

- [ ] Integrate Faker library into template context
  - Acceptance: `fake` object available in templates, all Faker methods work
  - Dependencies: Jinja2 environment, Faker
  - Notes: Create Faker instance, add to template globals

- [ ] Create template rendering context builder
  - Acceptance: Builds context with registry functions, fake object, filters for each render
  - Dependencies: Registry functions, Faker integration
  - Notes: Create context dict with registry and fake objects, pass to Jinja2 render

- [ ] Implement template renderer with error handling
  - Acceptance: Renders template to string, catches Jinja2 errors, provides detailed error messages
  - Dependencies: Template context, Jinja2 environment
  - Notes: Wrap render in try/except, extract line numbers from errors

## Template Validation {Priority: High}

- [ ] Implement Jinja2 syntax validation
  - Acceptance: Detects syntax errors, reports line numbers, validates template.j2
  - Dependencies: Jinja2
  - Notes: Use jinja2.Template.parse() to check syntax

- [ ] Implement template safety checks
  - Acceptance: Detects unsafe operations (eval, exec, file access), rejects dangerous templates
  - Dependencies: Template validation
  - Notes: Parse AST, check for forbidden function calls, use Jinja2 sandbox mode

- [ ] Implement metadata validation
  - Acceptance: Validates metadata.yaml schema, checks id matches directory, validates format enum
  - Dependencies: Metadata parser
  - Notes: Use Pydantic model for metadata, cross-validate with filesystem

- [ ] Implement registry function validation
  - Acceptance: Checks all registry.* calls in template reference valid functions
  - Dependencies: Template parser
  - Notes: Parse template AST, extract registry calls, validate against available functions

- [ ] Create template validation command
  - Acceptance: `logforge templates validate <path>` validates template and reports all issues
  - Dependencies: All validation checks
  - Notes: Run all checks, aggregate errors, return exit code

## Template Customization Workflow {Priority: Medium}

- [ ] Implement `logforge templates customize` command
  - Acceptance: Copies default template to custom/, preserves metadata, sets base_template reference
  - Dependencies: Template loader, CLI
  - Notes: Copy entire directory, update metadata.yaml with base_template field

- [ ] Implement `logforge templates diff` command
  - Acceptance: Shows differences between custom and default versions, uses configured diff tool
  - Dependencies: Template loader
  - Notes: Use difflib or external tool (vimdiff, meld), show side-by-side or unified diff

- [ ] Implement `logforge templates merge` command
  - Acceptance: Attempts to merge default changes into custom, handles conflicts interactively
  - Dependencies: Template diff
  - Notes: Use three-way merge algorithm, prompt for conflicts, preserve custom changes

- [ ] Implement `logforge templates revert` command
  - Acceptance: Removes custom version, confirms before deletion
  - Dependencies: Template loader
  - Notes: Delete custom directory, prompt for confirmation

- [ ] Implement `logforge templates create` command (interactive wizard)
  - Acceptance: Interactive wizard creates new custom template with metadata
  - Dependencies: Template loader, CLI
  - Notes: Prompt for vendor/product/data_source, create directory structure, generate template.j2 skeleton

## Template API Endpoints {Priority: High}

- [ ] Implement GET /api/templates endpoint
  - Acceptance: Returns list of all templates with location, version, status info
  - Dependencies: Template loader, FastAPI
  - Notes: Include both default and custom, show precedence indicators

- [ ] Implement GET /api/templates/{template_id} endpoint
  - Acceptance: Returns detailed template information including metadata
  - Dependencies: Template loader
  - Notes: Resolve precedence, return full metadata, include both versions if custom exists

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

- [ ] Implement `logforge templates search` command
  - Acceptance: Searches community templates, displays results with formatting
  - Dependencies: Community client, CLI
  - Notes: Support --vendor and --product filters, paginate results

- [ ] Implement `logforge templates list` command
  - Acceptance: Lists local and remote templates, shows version info and status
  - Dependencies: Template loader, Community client
  - Notes: Merge local and remote results, show update availability, indicate precedence

- [ ] Implement `logforge templates info` command
  - Acceptance: Shows detailed template info including both default and custom versions
  - Dependencies: Template loader, Community client
  - Notes: Fetch remote version if available, show comparison

- [ ] Implement `logforge templates install` command
  - Acceptance: Downloads and installs template to default/, warns if custom exists
  - Dependencies: Community client, Package extraction
  - Notes: Check for custom version, prompt user for action (update custom, keep custom, cancel)

- [ ] Implement `logforge templates update` command
  - Acceptance: Updates outdated default templates, never touches custom/
  - Dependencies: Template install, Version comparison
  - Notes: Compare local vs remote versions, update only default/, show diff notification

---

# Epic 7: Generator Engine Core

## Generator State Machine {Priority: High}

- [ ] Define GeneratorState enum (STOPPED, STARTING, RUNNING, DEGRADED, ERROR, STOPPING)
  - Acceptance: Enum defined with all states, used throughout codebase
  - Dependencies: None
  - Notes: Use Python enum.Enum, add state transition validation

- [ ] Implement Generator class with state management
  - Acceptance: Generator tracks state, validates transitions, prevents invalid state changes
  - Dependencies: State enum
  - Notes: Use threading.Lock for state changes, implement transition methods

- [ ] Implement state transition logic
  - Acceptance: Transitions follow state machine diagram, errors handled appropriately
  - Dependencies: Generator class
  - Notes: Validate transitions, log state changes, handle concurrent access

## Generator Lifecycle {Priority: High}

- [ ] Implement generator.start() method
  - Acceptance: Transitions to STARTING, loads template, initializes outputs, transitions to RUNNING
  - Dependencies: Generator class, Template loader, Output handlers
  - Notes: Validate template exists, check entity registry, initialize all outputs

- [ ] Implement generator.stop() method
  - Acceptance: Transitions to STOPPING, stops generation loop, closes outputs, transitions to STOPPED
  - Dependencies: Generator class
  - Notes: Graceful shutdown, wait for current events, flush outputs

- [ ] Implement generator._generate_loop() method
  - Acceptance: Main loop generates events at configured rate, handles errors
  - Dependencies: Generator start
  - Notes: Use time.sleep() for rate control, catch exceptions, update statistics

- [ ] Implement frequency calculation logic
  - Acceptance: Calculates current rate based on time/day, applies multipliers from config
  - Dependencies: Generator config
  - Notes: Check current day of week, time of day, apply matching variation rules

## Thread Pool Management {Priority: High}

- [ ] Implement ThreadPoolExecutor setup with dynamic sizing
  - Acceptance: Thread pool size calculated from CPU cores (cores × 5), respects max_generators config
  - Dependencies: Generator engine
  - Notes: Use concurrent.futures.ThreadPoolExecutor, calculate size on startup

- [ ] Implement generator execution in thread pool
  - Acceptance: Each generator runs in separate thread, multiple generators run concurrently
  - Dependencies: Thread pool, Generator class
  - Notes: Submit generator._generate_loop() to executor, track futures

- [ ] Implement thread pool lifecycle management
  - Acceptance: Thread pool created on engine start, shutdown gracefully on stop
  - Dependencies: Thread pool setup
  - Notes: Wait for all futures on shutdown, handle timeout

## Generator Engine Core {Priority: High}

- [ ] Create Engine class to manage all generators
  - Acceptance: Engine tracks all generators, provides start/stop/status methods
  - Dependencies: Generator class, Thread pool
  - Notes: Maintain dict of generators by name, coordinate lifecycle

- [ ] Implement engine.load_generators_from_config()
  - Acceptance: Loads generator configs, creates Generator instances, validates templates
  - Dependencies: Engine class, Config loader
  - Notes: Parse generators section, create Generator objects, validate templates exist

- [ ] Implement engine.start_generator(name) method
  - Acceptance: Starts specified generator, handles errors, updates state
  - Dependencies: Engine, Generator
  - Notes: Check generator exists, validate state, start in thread pool

- [ ] Implement engine.stop_generator(name) method
  - Acceptance: Stops specified generator gracefully
  - Dependencies: Engine, Generator
  - Notes: Signal stop, wait for completion, update state

- [ ] Implement engine.get_generator_status(name) method
  - Acceptance: Returns generator status with statistics, state, uptime
  - Dependencies: Engine, Generator
  - Notes: Collect stats from generator, calculate uptime, format response

## Generator Statistics Tracking {Priority: Medium}

- [ ] Implement event counter per generator
  - Acceptance: Tracks events_generated, errors, last_event timestamp
  - Dependencies: Generator class
  - Notes: Use threading-safe counters (collections.Counter or atomic operations)

- [ ] Implement uptime tracking
  - Acceptance: Tracks generator uptime from start, resets on restart
  - Dependencies: Generator class
  - Notes: Store start_time, calculate delta on status request

- [ ] Implement error tracking
  - Acceptance: Tracks error count, last error message, error types
  - Dependencies: Generator class
  - Notes: Increment on exceptions, store last error details

## Generator API Endpoints {Priority: High}

- [ ] Implement GET /api/generators endpoint
  - Acceptance: Returns list of all generators with basic info
  - Dependencies: Engine, FastAPI
  - Notes: Return name, state, template, enabled status

- [ ] Implement GET /api/generators/{name} endpoint
  - Acceptance: Returns detailed generator info with statistics
  - Dependencies: Engine
  - Notes: Include state, template, frequency, outputs, statistics

- [ ] Implement POST /api/generators/{name}/start endpoint
  - Acceptance: Starts generator, returns state change
  - Dependencies: Engine
  - Notes: Validate generator exists, start asynchronously, return immediately

- [ ] Implement POST /api/generators/{name}/stop endpoint
  - Acceptance: Stops generator, returns state change
  - Dependencies: Engine
  - Notes: Graceful stop, wait for completion, return state

- [ ] Implement POST /api/generators/{name}/restart endpoint
  - Acceptance: Restarts generator (stop then start)
  - Dependencies: Start/stop endpoints
  - Notes: Call stop, wait, then start

## Generator CLI Commands {Priority: Medium}

- [ ] Implement `logforge generators list` command
  - Acceptance: Lists all generators with status, formatted output
  - Dependencies: Generator API, CLI
  - Notes: Call GET /api/generators, format as table

- [ ] Implement `logforge generators start <name>` command
  - Acceptance: Starts specified generator, shows confirmation
  - Dependencies: Generator API
  - Notes: Call POST /api/generators/{name}/start

- [ ] Implement `logforge generators stop <name>` command
  - Acceptance: Stops specified generator
  - Dependencies: Generator API
  - Notes: Call POST /api/generators/{name}/stop

- [ ] Implement `logforge generators restart <name>` command
  - Acceptance: Restarts specified generator
  - Dependencies: Generator API
  - Notes: Call POST /api/generators/{name}/restart

- [ ] Implement `logforge status` command
  - Acceptance: Shows status of all generators in table format
  - Dependencies: Status API, CLI
  - Notes: Call GET /api/status, format as table with columns: NAME, STATE, TEMPLATE, EVENTS, ERRORS, UPTIME

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

- [ ] Create OutputHandler abstract base class
  - Acceptance: Defines write(), write_batch(), close() methods, enforces interface
  - Dependencies: None
  - Notes: Use ABC from abc module, define abstract methods

- [ ] Implement retry logic with exponential backoff
  - Acceptance: Retries failed writes with exponential backoff, respects max_attempts config
  - Dependencies: Base handler
  - Notes: Calculate backoff: interval × (multiplier ^ attempt), cap at max_backoff

- [ ] Implement event buffering during outages
  - Acceptance: Buffers events in memory when output unavailable, flushes on recovery
  - Dependencies: Base handler
  - Notes: Use collections.deque with maxlen, drop oldest when full, log warnings

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

- [ ] Implement HTTP output handler with batching
  - Acceptance: Batches events, sends POST requests, handles responses
  - Dependencies: Base handler, requests library
  - Notes: Collect events in batch, send when batch_size or batch_interval reached

- [ ] Implement environment variable substitution in headers
  - Acceptance: Replaces ${VAR_NAME} in headers with environment variable values
  - Dependencies: HTTP handler
  - Notes: Use os.environ.get(), replace in header values

- [ ] Implement batch timing logic
  - Acceptance: Sends batch when size reached OR interval elapsed
  - Dependencies: HTTP handler
  - Notes: Use threading.Timer for interval, check size on each write

- [ ] Implement JSON array wrapping for batches
  - Acceptance: Wraps batch events in JSON array, sends as single request
  - Dependencies: HTTP handler
  - Notes: json.dumps([event1, event2, ...]), set Content-Type header

## TCP Output Handler {Priority: Low}

- [ ] Implement TCP output handler
  - Acceptance: Connects to TCP server, sends events with delimiter, maintains connection
  - Dependencies: Base handler, socket library
  - Notes: Use socket.socket(), connect once, send with delimiter, handle reconnection

- [ ] Implement TCP keepalive
  - Acceptance: Maintains TCP connection, reconnects on failure
  - Dependencies: TCP handler
  - Notes: Set SO_KEEPALIVE, detect connection loss, reconnect

## Syslog Output Handler {Priority: Low}

- [ ] Implement syslog output handler (RFC 5424)
  - Acceptance: Formats events as RFC 5424 syslog messages, sends via TCP/UDP
  - Dependencies: Base handler
  - Notes: Format: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG

- [ ] Implement syslog output handler (RFC 3164)
  - Acceptance: Formats events as RFC 3164 syslog messages
  - Dependencies: Base handler
  - Notes: Format: <PRI>TIMESTAMP HOSTNAME TAG: MSG

- [ ] Implement syslog facility and severity mapping
  - Acceptance: Maps config values to syslog facility/severity codes
  - Dependencies: Syslog handler
  - Notes: Use standard syslog codes, calculate PRI value

## Output Handler Factory {Priority: High}

- [ ] Implement output handler factory
  - Acceptance: Creates appropriate handler based on type config, initializes from config
  - Dependencies: All output handlers
  - Notes: Use factory pattern, map type string to handler class

- [ ] Implement output handler registration
  - Acceptance: Registers output definitions from config, creates handler instances
  - Dependencies: Output factory, Config loader
  - Notes: Parse outputs.definitions, create handlers, store by name

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

