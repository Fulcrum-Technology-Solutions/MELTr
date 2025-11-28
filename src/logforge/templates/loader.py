"""Template loader and discovery."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from logforge.core.config import Config
from logforge.core.paths import get_logforge_home
from logforge.templates.metadata import TemplateMetadata, parse_metadata
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class TemplateLoader:
    """Loads and discovers templates from filesystem."""
    
    def __init__(self, config: Config) -> None:
        """Initialize template loader.
        
        Args:
            config: Configuration object
        """
        self.config = config
        templates_config = config.templates
        
        self.local_path = Path(templates_config.local_path)
        self.default_path = Path(templates_config.default_path) if templates_config.default_path else self.local_path / 'default'
        self.custom_path = Path(templates_config.custom_path) if templates_config.custom_path else self.local_path / 'custom'
        self.precedence = templates_config.precedence
        
        # Ensure directories exist
        self.default_path.mkdir(parents=True, exist_ok=True)
        self.custom_path.mkdir(parents=True, exist_ok=True)
    
    def discover_templates(self) -> Dict[str, 'TemplateInfo']:
        """Discover all templates in default/ and custom/ directories.
        
        Returns:
            Dictionary mapping template ID to TemplateInfo
        """
        templates = {}
        
        # Discover default templates
        default_templates = self._scan_directory(self.default_path, 'default')
        templates.update(default_templates)
        
        # Discover custom templates (may override defaults)
        custom_templates = self._scan_directory(self.custom_path, 'custom')
        for template_id, template_info in custom_templates.items():
            # Custom templates override defaults
            templates[template_id] = template_info
        
        return templates
    
    def _scan_directory(self, base_path: Path, location: str) -> Dict[str, 'TemplateInfo']:
        """Scan directory for templates.
        
        Args:
            base_path: Base directory to scan
            location: Location identifier ('default' or 'custom')
            
        Returns:
            Dictionary of template ID to TemplateInfo
        """
        templates = {}
        
        if not base_path.exists():
            return templates
        
        # Walk directory structure: vendor/product/data_source/template_name
        for vendor_dir in base_path.iterdir():
            if not vendor_dir.is_dir():
                continue
            
            vendor_id = vendor_dir.name
            vendor_meta_path = vendor_dir / 'vendor.meta.yaml'
            
            for product_dir in vendor_dir.iterdir():
                if not product_dir.is_dir():
                    continue
                
                product_id = product_dir.name
                product_meta_path = product_dir / 'product.meta.yaml'
                
                # Look for data_source directories or templates directly in product
                for item in product_dir.iterdir():
                    if not item.is_dir():
                        continue
                    
                    # Check if this is a data_source directory
                    data_source_id = item.name
                    data_source_path = item
                    
                    # Look for template files in this data_source directory
                    for template_file in data_source_path.glob('*.j2'):
                        template_name = template_file.stem
                        meta_file = data_source_path / f'{template_name}.meta.yaml'
                        
                        if meta_file.exists():
                            template_id = f'{vendor_id}/{product_id}/{data_source_id}/{template_name}'
                            
                            try:
                                metadata = parse_metadata(meta_file)
                                
                                # Validate metadata matches directory structure
                                if metadata.vendor != vendor_id:
                                    logger.warning(f"Template {template_id}: vendor mismatch in metadata")
                                    continue
                                if metadata.product != product_id:
                                    logger.warning(f"Template {template_id}: product mismatch in metadata")
                                    continue
                                if metadata.data_source != data_source_id:
                                    logger.warning(f"Template {template_id}: data_source mismatch in metadata")
                                    continue
                                
                                templates[template_id] = TemplateInfo(
                                    id=template_id,
                                    name=template_name,
                                    vendor=vendor_id,
                                    product=product_id,
                                    data_source=data_source_id,
                                    location=location,
                                    template_path=template_file,
                                    metadata_path=meta_file,
                                    metadata=metadata,
                                )
                            except Exception as e:
                                logger.error(f"Failed to load template {template_id}: {e}", exc_info=True)
        
        return templates
    
    def resolve_template(self, template_id: str) -> Optional['TemplateInfo']:
        """Resolve template path based on precedence.
        
        Args:
            template_id: Template ID (vendor/product/data_source/template_name)
            
        Returns:
            TemplateInfo if found, None otherwise
        """
        all_templates = self.discover_templates()
        return all_templates.get(template_id)
    
    def get_template_path(self, template_id: str) -> Optional[Path]:
        """Get path to template.j2 file.
        
        Args:
            template_id: Template ID
            
        Returns:
            Path to template file or None if not found
        """
        template_info = self.resolve_template(template_id)
        if template_info:
            return template_info.template_path
        return None
    
    def get_metadata(self, template_id: str) -> Optional[TemplateMetadata]:
        """Get template metadata.
        
        Args:
            template_id: Template ID
            
        Returns:
            TemplateMetadata or None if not found
        """
        template_info = self.resolve_template(template_id)
        if template_info:
            return template_info.metadata
        return None


class TemplateInfo:
    """Information about a discovered template."""
    
    def __init__(
        self,
        id: str,
        name: str,
        vendor: str,
        product: str,
        data_source: str,
        location: str,
        template_path: Path,
        metadata_path: Path,
        metadata: TemplateMetadata,
    ) -> None:
        """Initialize template info.
        
        Args:
            id: Template ID
            name: Template name
            vendor: Vendor ID
            product: Product ID
            data_source: Data source ID
            location: Location ('default' or 'custom')
            template_path: Path to template.j2 file
            metadata_path: Path to metadata.yaml file
            metadata: Parsed metadata
        """
        self.id = id
        self.name = name
        self.vendor = vendor
        self.product = product
        self.data_source = data_source
        self.location = location
        self.template_path = template_path
        self.metadata_path = metadata_path
        self.metadata = metadata
    
    def __repr__(self) -> str:
        return f"TemplateInfo(id={self.id!r}, location={self.location!r})"

