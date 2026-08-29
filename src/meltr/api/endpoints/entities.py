"""Entity management API endpoints."""

from typing import Annotated, Any, Dict, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from meltr.api.auth import require_api_key
from meltr.api.errors import log_api_exception
from meltr.entities.registry import EntityRegistry
from meltr.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/entities",
    tags=["entities"],
    dependencies=[Depends(require_api_key)],
)


def get_registry(request: Request) -> EntityRegistry:
    """Dependency to get entity registry from app state."""
    # TODO: This will be set when engine is initialized
    if not hasattr(request.app.state, 'registry'):
        raise HTTPException(status_code=503, detail="Entity registry not initialized")
    return request.app.state.registry


@router.get("")
async def get_entities_summary(
    registry: Annotated[EntityRegistry, Depends(get_registry)]
) -> dict:
    """Get entity registry summary.
    
    Returns:
        Summary with organization info and entity counts
    """
    org = registry.get_organization()
    users = registry.get_all_users()
    devices = registry.get_all_devices()
    services = registry.get_all_services()
    
    return {
        "organization": {
            "name": org.get("name", ""),
            "domain": org.get("domain", ""),
        },
        "users": len(users),
        "devices": len(devices),
        "services": len(services),
    }


@router.post("/import")
async def import_entities(
    registry: Annotated[EntityRegistry, Depends(get_registry)],
    entities_data: Annotated[Dict[str, Any], Body(description="Entity data to import")],
    merge: bool = Query(False, description="Merge with existing entities"),
) -> dict:
    """Import entities into the registry.
    
    Args:
        registry: Entity registry instance
        entities_data: Entity data to import
        merge: If True, merge with existing entities
        
    Returns:
        Import summary
    """
    from meltr.entities.validator import validate_entities
    
    # Validate import data
    try:
        validate_entities(entities_data, schema_path=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid entities: {e}")
    except Exception as e:
        detail = log_api_exception(logger, "Validate entities import", e)
        raise HTTPException(status_code=400, detail=detail)
    
    # Get current data
    current_data = registry._data or {
        'organization': {},
        'users': [],
        'devices': [],
        'services': [],
        'network_ranges': [],
    }
    
    if merge:
        # Merge logic
        merged_data = current_data.copy()
        merged_data['users'] = current_data.get('users', []) + entities_data.get('users', [])
        merged_data['devices'] = current_data.get('devices', []) + entities_data.get('devices', [])
        merged_data['services'] = current_data.get('services', []) + entities_data.get('services', [])
        # Update organization if provided
        if 'organization' in entities_data:
            merged_data['organization'] = entities_data['organization']
        # Merge network ranges
        if 'network_ranges' in entities_data:
            merged_data['network_ranges'] = current_data.get('network_ranges', []) + entities_data.get('network_ranges', [])
        
        # Re-validate
        validate_entities(merged_data, schema_path=None)
        registry._data = merged_data
    else:
        # Replace
        registry._data = entities_data
    
    # Rebuild indexes and save
    registry._rebuild_indexes()
    registry.save()
    
    return {
        "message": "Entities imported successfully",
        "users": len(registry.get_all_users()),
        "devices": len(registry.get_all_devices()),
        "services": len(registry.get_all_services()),
    }


@router.post("/reload")
async def reload_entities(
    registry: Annotated[EntityRegistry, Depends(get_registry)]
) -> dict:
    """Reload entities from disk.
    
    Returns:
        Reload summary
    """
    registry.reload(strict=False)
    
    return {
        "message": "Entities reloaded successfully",
        "users": len(registry.get_all_users()),
        "devices": len(registry.get_all_devices()),
        "services": len(registry.get_all_services()),
    }


@router.get("/{entity_type}")
async def get_entities_by_type(
    entity_type: Literal["users", "devices", "services"],
    registry: Annotated[EntityRegistry, Depends(get_registry)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
) -> dict:
    """Get entities of specified type with pagination.
    
    Args:
        entity_type: Type of entities to retrieve
        registry: Entity registry instance
        page: Page number (1-indexed)
        page_size: Number of items per page
        
    Returns:
        Entities list with pagination info
    """
    if entity_type == "users":
        all_entities = registry.get_all_users()
    elif entity_type == "devices":
        all_entities = registry.get_all_devices()
    elif entity_type == "services":
        all_entities = registry.get_all_services()
    else:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")
    
    # Pagination
    total = len(all_entities)
    start = (page - 1) * page_size
    end = start + page_size
    entities = all_entities[start:end]
    
    return {
        "type": entity_type,
        "count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "entities": entities,
    }








