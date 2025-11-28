"""Template management API endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from logforge.templates.cache import TemplateCache
from logforge.templates.loader import TemplateLoader

router = APIRouter(prefix="/api/templates", tags=["templates"])


def get_template_cache(request: Request) -> TemplateCache:
    """Dependency to get template cache from app state."""
    # TODO: This will be set when engine is initialized
    if not hasattr(request.app.state, 'template_cache'):
        raise HTTPException(status_code=503, detail="Template cache not initialized")
    return request.app.state.template_cache


@router.get("")
async def list_templates(
    cache: Annotated[TemplateCache, Depends(get_template_cache)],
    local_only: bool = False,
    remote_only: bool = False,
) -> dict:
    """List all templates.
    
    Args:
        cache: Template cache instance
        local_only: Only return local templates
        remote_only: Only return remote templates (not yet implemented)
        
    Returns:
        List of templates with metadata
    """
    if remote_only:
        # TODO: Implement remote template listing
        return {"templates": []}
    
    all_templates = cache.get_all_templates()
    
    templates_list = []
    for template_id, template_info in all_templates.items():
        if local_only and template_info.location != 'default' and template_info.location != 'custom':
            continue
        
        metadata = template_info.metadata
        
        templates_list.append({
            "id": template_id,
            "name": metadata.description.split('.')[0] if metadata.description else template_info.name,
            "vendor": template_info.vendor,
            "product": template_info.product,
            "data_source": template_info.data_source,
            "version": None,  # TODO: Get version from metadata if available
            "local": True,
            "remote_version": None,  # TODO: Check remote version
            "location": template_info.location,
            "format": metadata.format,
        })
    
    return {"templates": templates_list}


@router.get("/{template_id:path}")
async def get_template(
    template_id: str,
    cache: Annotated[TemplateCache, Depends(get_template_cache)],
) -> dict:
    """Get detailed template information.
    
    Args:
        template_id: Template ID (vendor/product/data_source/template_name)
        cache: Template cache instance
        
    Returns:
        Detailed template information
    """
    template_info = cache.get_template(template_id)
    
    if not template_info:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    metadata = template_info.metadata
    
    return {
        "id": template_id,
        "name": metadata.description.split('.')[0] if metadata.description else template_info.name,
        "description": metadata.description,
        "vendor": template_info.vendor,
        "product": template_info.product,
        "data_source": template_info.data_source,
        "version": None,  # TODO: Get version if available
        "format": metadata.format,
        "local": True,
        "remote_version": None,  # TODO: Check remote version
        "location": template_info.location,
        "metadata": {
            "frequency": metadata.frequency,
            "is_generator": metadata.is_generator,
            "base_frequency": metadata.base_frequency,
            "time_patterns": metadata.time_patterns,
            "documentation": metadata.documentation,
        },
    }
