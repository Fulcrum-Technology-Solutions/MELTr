"""Template metadata parsing and validation."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class TemplateMetadata(BaseModel):
    """Template metadata model matching schema."""
    
    vendor: str = Field(description="Vendor identifier")
    product: str = Field(description="Product identifier")
    data_source: str = Field(description="Data source identifier")
    description: str = Field(description="Template description")
    format: str = Field(description="Output format")
    
    # Optional fields
    frequency: Optional[str] = Field(default=None, description="Event frequency category")
    is_generator: bool = Field(default=False, description="Whether template is used for generation")
    base_frequency: Optional[float] = Field(default=None, description="Base events per hour")
    time_patterns: Optional[list[str]] = Field(default=None, description="Time patterns")
    business_hours_multiplier: Optional[float] = Field(default=None, description="Business hours multiplier")
    night_hours_multiplier: Optional[float] = Field(default=None, description="Night hours multiplier")
    weekend_multiplier: Optional[float] = Field(default=None, description="Weekend multiplier")
    documentation: Optional[Dict[str, Any]] = Field(default=None, description="Documentation object")
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate format enum."""
        valid_formats = ['JSON', 'XML', 'CSV', 'Syslog', 'CEF', 'LEEF', 'Plain Text', 'Custom']
        if v not in valid_formats:
            raise ValueError(f"Format must be one of {valid_formats}")
        return v
    
    @field_validator('frequency')
    @classmethod
    def validate_frequency(cls, v: Optional[str]) -> Optional[str]:
        """Validate frequency enum."""
        if v is None:
            return v
        valid_frequencies = ['critical', 'high', 'medium', 'low']
        if v not in valid_frequencies:
            raise ValueError(f"Frequency must be one of {valid_frequencies}")
        return v


def parse_metadata(metadata_path: Path) -> TemplateMetadata:
    """Parse template metadata from YAML file.
    
    Args:
        metadata_path: Path to metadata.yaml file
        
    Returns:
        TemplateMetadata object
        
    Raises:
        ValueError: If metadata is invalid
        FileNotFoundError: If file doesn't exist
    """
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
    
    try:
        with metadata_path.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in metadata file: {e}") from e
    
    if not isinstance(data, dict):
        raise ValueError("Metadata file must contain a YAML mapping/object")
    
    try:
        return TemplateMetadata(**data)
    except Exception as e:
        raise ValueError(f"Invalid metadata: {e}") from e









