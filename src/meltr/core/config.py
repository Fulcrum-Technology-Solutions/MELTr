"""Configuration management."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from meltr.core.paths import (
    default_application_log_file,
    get_logforge_home,
    validate_path_within_home,
)


class RotationConfig(BaseModel):
    """Log rotation configuration."""

    max_size: int | str = Field(default=50 * 1024 * 1024, description="Max log file size")
    backup_count: int = Field(default=5, description="Number of backup files to keep")


class LoggingConfig(BaseModel):
    """Application logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    file: str | None = Field(default=None, description="Log file path")
    rotation: RotationConfig | None = Field(default=None, description="Log rotation settings")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )


class EngineConfig(BaseModel):
    """Core engine settings."""

    max_generators: int | None = Field(default=None, description="Max concurrent generators")
    thread_pool_size: int | None = Field(default=None, description="Thread pool size (null = auto)")
    log_level: str = Field(default="INFO", description="Engine log level")


class AuthConfig(BaseModel):
    """API authentication configuration.

    Key-implies-auth: authentication is active when ``enabled`` is true or when
    a non-empty API key is resolved from ``MELTR_API_KEY``, ``LOGFORGE_API_KEY``,
    or ``key`` in config (env vars take precedence over config).
    """

    enabled: bool = Field(default=False, description="Enable API key authentication")
    key: str | None = Field(default=None, description="API key (auto-generated if enabled)")


class APIConfig(BaseModel):
    """API server settings."""

    enabled: bool = Field(default=True, description="Enable API server")
    host: str = Field(default="127.0.0.1", description="Listen address")
    port: int = Field(default=8080, description="Listen port")
    auth: AuthConfig = Field(default_factory=AuthConfig, description="Authentication settings")


class EntityRegistryConfig(BaseModel):
    """Entity registry settings."""

    path: str = Field(description="Path to entities.yaml")
    auto_save: bool = Field(default=True, description="Auto-save entities")
    save_interval: int = Field(default=60, description="Save interval in seconds")
    backup_enabled: bool = Field(default=True, description="Enable backups")
    backup_count: int = Field(default=3, description="Number of backups to keep")


class TemplatesConfig(BaseModel):
    """Template settings."""

    local_path: str = Field(description="Local templates path")
    default_path: str | None = Field(default=None, description="Default templates path")
    custom_path: str | None = Field(default=None, description="Custom templates path")
    precedence: str = Field(default="custom_first", description="Template precedence")
    community_api_url: str = Field(
        default="https://logforge.io/api/v1", description="Community API URL"
    )
    auto_update_check: bool = Field(default=True, description="Auto-check for updates")
    cache_ttl: int = Field(default=3600, description="Template cache TTL in seconds")
    auto_backup_on_customize: bool = Field(default=True, description="Backup on customize")
    backup_count: int = Field(default=5, description="Number of template backups to keep")
    diff_tool: str = Field(default="auto", description="Diff tool for template comparison")


class RetryConfig(BaseModel):
    """Output retry configuration."""

    max_attempts: int = Field(default=-1, description="Max retry attempts (-1 = unlimited)")
    retry_interval: int = Field(default=5, description="Initial retry interval in seconds")
    backoff_multiplier: float = Field(default=2.0, description="Exponential backoff multiplier")
    max_backoff: int = Field(default=300, description="Max backoff in seconds")


class OutputRotationConfig(BaseModel):
    """Output file rotation configuration."""

    type: str = Field(description="Rotation type: size or time")
    max_size: int | str | None = Field(default=None, description="Max file size")
    max_age: str | None = Field(default=None, description="Max age (e.g., '7d', '24h')")
    max_files: int | None = Field(
        default=None, description="Maximum number of rotated files to keep"
    )
    compress: bool = Field(default=True, description="Compress rotated files")


class OutputDefinition(BaseModel):
    """Output destination definition."""

    name: str = Field(description="Output name")
    type: str = Field(description="Output type: file, console, http, tcp, syslog")
    path: str | None = Field(default=None, description="File path (for file type)")
    format: str | None = Field(default=None, description="Output format")
    stream: str | None = Field(default=None, description="Stream (stdout/stderr for console)")
    host: str | None = Field(default=None, description="Host (for tcp/syslog/http)")
    port: int | None = Field(default=None, description="Port (for tcp/syslog/http)")
    url: str | None = Field(default=None, description="URL (for http)")
    method: str | None = Field(default=None, description="HTTP method")
    headers: dict[str, str] | None = Field(default=None, description="HTTP headers")
    batch_size: int | None = Field(default=None, description="Batch size (for http)")
    batch_interval: int | None = Field(default=None, description="Batch interval in seconds")
    streaming: bool | None = Field(
        default=True,
        description="Stream events individually (True) or batch them (False) for HTTP output",
    )
    protocol: str | None = Field(default=None, description="Protocol (tcp/udp for syslog)")
    facility: str | None = Field(default=None, description="Syslog facility")
    severity: str | None = Field(default=None, description="Syslog severity")
    delimiter: str | None = Field(default=None, description="Delimiter (for tcp)")
    keepalive: bool | None = Field(default=None, description="TCP keepalive")
    rotation: OutputRotationConfig | None = Field(default=None, description="File rotation")
    timeout: int | None = Field(default=None, description="Timeout in seconds")
    include_metadata: bool = Field(
        default=False, description="Include logforge_metadata wrapper for HTTP output"
    )
    buffer_overflow_policy: str = Field(
        default="drop_newest",
        description="When HTTP retry queue is full: drop_newest (reject incoming) or drop_oldest (evict oldest)",
    )

    @field_validator("buffer_overflow_policy")
    @classmethod
    def validate_buffer_overflow_policy(cls, v: str) -> str:
        allowed = {"drop_newest", "drop_oldest"}
        if v not in allowed:
            raise ValueError(f"buffer_overflow_policy must be one of {allowed}, got {v!r}")
        return v


class OutputsConfig(BaseModel):
    """Output handler settings."""

    retry: RetryConfig = Field(default_factory=RetryConfig, description="Retry configuration")
    buffer_size: int = Field(default=10000, description="Event buffer size")
    definitions: list[OutputDefinition] = Field(
        default_factory=list, description="Output definitions"
    )


class FrequencyVariation(BaseModel):
    """Frequency variation rule."""

    days: list[int] | None = Field(default=None, description="Days of week (1=Monday, 7=Sunday)")
    time: str | None = Field(default=None, description="Time range (e.g., '09:00-17:00')")
    multiplier: float = Field(description="Rate multiplier")


class FrequencyConfig(BaseModel):
    """Generator frequency configuration."""

    base_rate: float = Field(description="Base rate in events per second")
    variation: list[FrequencyVariation] | None = Field(default=None, description="Rate variations")


class GeneratorConfig(BaseModel):
    """Generator definition.

    Note: Frequency is read from template metadata (.meta.yaml), not from config.
    Customize frequency by copying template to custom/ directory and modifying .meta.yaml.
    """

    name: str = Field(description="Generator name")
    template: str = Field(description="Template ID")
    enabled: bool = Field(default=True, description="Generator enabled")
    outputs: list[str] = Field(description="Output destination names")
    timezone: str | None = Field(
        default=None,
        description="Timezone override (e.g., 'America/New_York'). Takes precedence over organization timezone.",
    )


class InternalLogsConfig(BaseModel):
    """Configuration for forwarding application logs to output destinations."""

    enabled: bool = Field(default=False, description="Enable internal log forwarding")
    outputs: list[str] = Field(
        default_factory=list, description="Output definition names to forward logs to"
    )


class Config(BaseModel):
    """Main configuration model."""

    version: str = Field(default="1.0", description="Config version")
    engine: EngineConfig = Field(default_factory=EngineConfig, description="Engine settings")
    api: APIConfig = Field(default_factory=APIConfig, description="API settings")
    entity_registry: EntityRegistryConfig = Field(description="Entity registry settings")
    templates: TemplatesConfig = Field(description="Template settings")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="Logging settings")
    outputs: OutputsConfig = Field(default_factory=OutputsConfig, description="Output settings")
    generators: list[GeneratorConfig] = Field(
        default_factory=list, description="Generator definitions"
    )
    internal_logs: InternalLogsConfig = Field(
        default_factory=lambda: InternalLogsConfig(enabled=False, outputs=[]),
        description="Forward application logs to outputs (built-in generator)",
    )


def substitute_env_vars(value: Any, home: Path) -> Any:
    """Recursively substitute environment variables in config values.

    Supports ${VAR} and ${LOGFORGE_HOME} substitution.

    Args:
        value: Config value (may be dict, list, or string)
        home: LOGFORGE_HOME path for ${LOGFORGE_HOME} substitution

    Returns:
        Value with environment variables substituted
    """
    if isinstance(value, dict):
        return {k: substitute_env_vars(v, home) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_env_vars(item, home) for item in value]
    elif isinstance(value, str):
        # Substitute ${VAR} patterns
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name == "MELTR_HOME":
                return str(home)
            return os.getenv(var_name, match.group(0))

        pattern = r"\$\{([^}]+)\}"
        result = re.sub(pattern, replace_var, value)

        # Normalize path separators (handle Windows-style backslashes in paths)
        # Only normalize if this looks like a file path
        if "/" in result or "\\" in result:
            result = result.replace("\\", "/")

        return result
    else:
        return value


def _validate_output_path_templates(config: Config) -> None:
    """Validate file output path templates in configuration.

    Args:
        config: Config object to validate

    Raises:
        ValueError: If any path template is invalid
    """
    if not config.outputs or not config.outputs.definitions:
        return

    # Import here to avoid circular dependency
    from meltr.outputs.path_resolver import validate_path_template
    from meltr.utils.logging import get_logger

    logger = get_logger(__name__)

    for output_def in config.outputs.definitions:
        if output_def.type == "file" and output_def.path:
            is_valid, template_warnings = validate_path_template(output_def.path)
            if not is_valid:
                raise ValueError(
                    f"Invalid path template for output '{output_def.name}': "
                    f"{', '.join(template_warnings)}"
                )
            if template_warnings:
                for warning in template_warnings:
                    logger.warning(f"Output '{output_def.name}' path template: {warning}")


def load_config(config_path: Path | None = None, create_if_missing: bool = True) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config.yaml. If None, uses default from LOGFORGE_HOME.
        create_if_missing: If True, create default config file if it doesn't exist.

    Returns:
        Config object with validated settings

    Raises:
        FileNotFoundError: If config file doesn't exist and create_if_missing is False
        ValueError: If config is invalid
    """
    home = get_logforge_home()

    if config_path is None:
        config_path = home / "config.yaml"
    else:
        # Validate config path is within LOGFORGE_HOME
        if not validate_path_within_home(config_path, home):
            raise ValueError(f"Config path {config_path} must be within LOGFORGE_HOME {home}")

    # Create default config if missing
    if not config_path.exists():
        if create_if_missing:
            from meltr.utils.logging import get_logger

            logger = get_logger(__name__)
            logger.info(f"Config file not found at {config_path}, creating default configuration")

            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Create default config
            default_config = create_default_config(home)
            save_config(default_config, config_path)
            logger.info(f"Created default config file at {config_path}")
            return default_config
        else:
            raise FileNotFoundError(f"Config file not found: {config_path}")

    # Load YAML
    try:
        with config_path.open("r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}") from e

    if not isinstance(raw_config, dict):
        raise ValueError("Config file must contain a YAML mapping/object")

    # Substitute environment variables
    raw_config = substitute_env_vars(raw_config, home)

    # Validate with Pydantic
    try:
        config = Config(**raw_config)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    # Validate file output path templates
    _validate_output_path_templates(config)

    return config


def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save configuration to YAML file.

    Args:
        config: Config object to save
        config_path: Path to save config.yaml. If None, uses default from LOGFORGE_HOME.

    Raises:
        ValueError: If config path is invalid
        RuntimeError: If save fails
    """
    home = get_logforge_home()

    if config_path is None:
        config_path = home / "config.yaml"
    else:
        # Validate config path is within LOGFORGE_HOME
        if not validate_path_within_home(config_path, home):
            raise ValueError(f"Config path {config_path} must be within LOGFORGE_HOME {home}")

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and save
    try:
        config_dict = config.model_dump(mode="json", exclude_none=False)

        # Write to temporary file first (atomic write)
        temp_path = config_path.with_suffix(".yaml.tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        # Atomic move
        temp_path.replace(config_path)

        # Set secure permissions (600)
        config_path.chmod(0o600)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to save config: {e}") from e


def create_default_config(home: Path | None = None) -> Config:
    """Create default configuration with sensible defaults.

    Args:
        home: LOGFORGE_HOME path. If None, resolves automatically.

    Returns:
        Default Config object
    """
    if home is None:
        home = get_logforge_home()

    return Config(
        version="1.0",
        engine=EngineConfig(),
        api=APIConfig(),
        entity_registry=EntityRegistryConfig(path=str(home / "entities.yaml")),
        templates=TemplatesConfig(
            local_path=str(home / "templates"),
            default_path=str(home / "templates" / "default"),
            custom_path=str(home / "templates" / "custom"),
        ),
        logging=LoggingConfig(
            file=str(default_application_log_file()),
            rotation=RotationConfig(),
        ),
        outputs=OutputsConfig(),
        generators=[],
        internal_logs=InternalLogsConfig(enabled=False, outputs=[]),
    )
