"""Entity management API endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from logforge.entities.registry import EntityRegistry

router = APIRouter(prefix="/api/entities", tags=["entities"])


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

