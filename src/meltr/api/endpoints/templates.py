"""Template management API endpoints."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from meltr.api.auth import require_api_key
from meltr.api.endpoints.entities import get_registry
from meltr.community.client import CommunityAPIClient
from meltr.community.updates import ProductVersionLookup
from meltr.core.config import Config
from meltr.entities.registry import EntityRegistry
from meltr.templates.cache import TemplateCache
from meltr.templates.renderer import TemplateRenderer

router = APIRouter(
    prefix="/api/templates",
    tags=["templates"],
    dependencies=[Depends(require_api_key)],
)


class PreviewRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=20)


def get_template_cache(request: Request) -> TemplateCache:
    """Dependency to get template cache from app state."""
    # TODO: This will be set when engine is initialized
    if not hasattr(request.app.state, "template_cache"):
        raise HTTPException(status_code=503, detail="Template cache not initialized")
    return request.app.state.template_cache


def get_config(request: Request) -> Config:
    """Dependency to read server configuration from app state."""
    return request.app.state.server.config


def get_version_lookup(
    config: Annotated[Config, Depends(get_config)],
) -> ProductVersionLookup:
    """Build a version lookup backed by the configured community API."""
    client = CommunityAPIClient(base_url=config.templates.community_api_url)
    return ProductVersionLookup(Path(config.templates.local_path), client=client)


@router.get("")
async def list_templates(
    cache: Annotated[TemplateCache, Depends(get_template_cache)],
    version_lookup: Annotated[ProductVersionLookup, Depends(get_version_lookup)],
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
        if (
            local_only
            and template_info.location != "default"
            and template_info.location != "custom"
        ):
            continue

        metadata = template_info.metadata
        local_version, remote_version = version_lookup.for_product(
            template_info.vendor,
            template_info.product,
        )

        templates_list.append(
            {
                "id": template_id,
                "name": (
                    metadata.description.split(".")[0]
                    if metadata.description
                    else template_info.name
                ),
                "vendor": template_info.vendor,
                "product": template_info.product,
                "data_source": template_info.data_source,
                "version": local_version,
                "local": True,
                "remote_version": remote_version,
                "location": template_info.location,
                "format": metadata.format,
            }
        )

    return {"templates": templates_list}


@router.get("/{template_id:path}")
async def get_template(
    template_id: str,
    cache: Annotated[TemplateCache, Depends(get_template_cache)],
    version_lookup: Annotated[ProductVersionLookup, Depends(get_version_lookup)],
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
    local_version, remote_version = version_lookup.for_product(
        template_info.vendor,
        template_info.product,
    )

    return {
        "id": template_id,
        "name": metadata.description.split(".")[0] if metadata.description else template_info.name,
        "description": metadata.description,
        "vendor": template_info.vendor,
        "product": template_info.product,
        "data_source": template_info.data_source,
        "version": local_version,
        "format": metadata.format,
        "local": True,
        "remote_version": remote_version,
        "location": template_info.location,
        "metadata": {
            "frequency": metadata.frequency,
            "is_generator": metadata.is_generator,
            "base_frequency": metadata.base_frequency,
            "time_patterns": metadata.time_patterns,
            "documentation": metadata.documentation,
        },
    }


@router.post("/{template_id:path}/preview")
async def preview_template(
    template_id: str,
    body: PreviewRequest,
    cache: Annotated[TemplateCache, Depends(get_template_cache)],
    registry: Annotated[EntityRegistry, Depends(get_registry)],
) -> dict:
    """Render sample events from a template without starting a generator."""
    template_info = cache.get_template(template_id)
    if not template_info:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

    renderer = TemplateRenderer(registry)
    events: list[str] = []
    try:
        for _ in range(body.count):
            events.append(renderer.render_template(str(template_info.template_path)))
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return {"template_id": template_id, "count": body.count, "events": events}
