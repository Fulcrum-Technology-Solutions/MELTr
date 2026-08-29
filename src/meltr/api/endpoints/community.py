"""Community registry integration endpoints."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from meltr.api.auth import require_api_key
from meltr.community.client import CommunityAPIClient, CommunityAPIError
from meltr.community.updates import find_stale_updates
from meltr.core.config import Config

router = APIRouter(
    prefix="/api/community",
    tags=["community"],
    dependencies=[Depends(require_api_key)],
)


def get_config(request: Request) -> Config:
    """Dependency to read server configuration from app state."""
    return request.app.state.server.config


@router.get("/updates")
async def list_community_updates(
    config: Annotated[Config, Depends(get_config)],
) -> dict:
    """List installed community products with newer remote collection versions."""
    client = CommunityAPIClient(base_url=config.templates.community_api_url)
    templates_path = Path(config.templates.local_path)

    try:
        updates = find_stale_updates(client, templates_path)
    except CommunityAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"updates": updates}
