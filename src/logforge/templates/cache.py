"""Template cache with TTL support."""

import time
from pathlib import Path
from typing import Dict, Optional

from logforge.templates.loader import TemplateInfo, TemplateLoader
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class TemplateCache:
    """Caches loaded templates with TTL and file change detection."""
    
    def __init__(self, loader: TemplateLoader, ttl: int = 3600) -> None:
        """Initialize template cache.
        
        Args:
            loader: TemplateLoader instance
            ttl: Cache TTL in seconds
        """
        self.loader = loader
        self.ttl = ttl
        self._cache: Dict[str, 'CachedTemplate'] = {}
        self._last_scan: float = 0.0
    
    def get_template(self, template_id: str) -> Optional[TemplateInfo]:
        """Get template from cache or load it.
        
        Args:
            template_id: Template ID
            
        Returns:
            TemplateInfo or None if not found
        """
        # Check if cache needs refresh
        if self._needs_refresh():
            self._refresh_cache()
        
        # Check cache
        cached = self._cache.get(template_id)
        if cached:
            # Check if file has changed
            if cached.is_stale():
                logger.debug(f"Template {template_id} is stale, reloading")
                self._cache.pop(template_id, None)
            else:
                return cached.template_info
        
        # Load template
        template_info = self.loader.resolve_template(template_id)
        if template_info:
            self._cache[template_id] = CachedTemplate(template_info)
        
        return template_info
    
    def get_all_templates(self) -> Dict[str, TemplateInfo]:
        """Get all templates (refreshes cache if needed).
        
        Returns:
            Dictionary of template ID to TemplateInfo
        """
        if self._needs_refresh():
            self._refresh_cache()
        
        # Update cache with any new templates
        all_templates = self.loader.discover_templates()
        for template_id, template_info in all_templates.items():
            if template_id not in self._cache:
                self._cache[template_id] = CachedTemplate(template_info)
            else:
                # Check if file changed
                cached = self._cache[template_id]
                if cached.is_stale():
                    self._cache[template_id] = CachedTemplate(template_info)
        
        return {tid: cached.template_info for tid, cached in self._cache.items()}
    
    def _needs_refresh(self) -> bool:
        """Check if cache needs refresh based on TTL."""
        return time.time() - self._last_scan > self.ttl
    
    def _refresh_cache(self) -> None:
        """Refresh cache by rescanning filesystem."""
        self._last_scan = time.time()
        # Cache will be updated lazily as templates are accessed
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._last_scan = 0.0


class CachedTemplate:
    """Cached template with file modification time tracking."""
    
    def __init__(self, template_info: TemplateInfo) -> None:
        """Initialize cached template.
        
        Args:
            template_info: TemplateInfo to cache
        """
        self.template_info = template_info
        self.cached_time = time.time()
        self.template_mtime = template_info.template_path.stat().st_mtime if template_info.template_path.exists() else 0
        self.metadata_mtime = template_info.metadata_path.stat().st_mtime if template_info.metadata_path.exists() else 0
    
    def is_stale(self) -> bool:
        """Check if cached template is stale (file changed).
        
        Returns:
            True if file has been modified since cache
        """
        if not self.template_info.template_path.exists():
            return True
        
        current_template_mtime = self.template_info.template_path.stat().st_mtime
        current_metadata_mtime = self.template_info.metadata_path.stat().st_mtime if self.template_info.metadata_path.exists() else 0
        
        return (current_template_mtime > self.template_mtime or
                current_metadata_mtime > self.metadata_mtime)









