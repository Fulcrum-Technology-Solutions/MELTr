"""Pipeline management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from meltr.api.auth import require_api_key
from meltr.api.errors import log_api_exception
from meltr.core.engine import Engine
from meltr.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/pipelines",
    tags=["pipelines"],
    dependencies=[Depends(require_api_key)],
)


def get_engine(request: Request) -> Engine:
    """Dependency to get engine from app state."""
    if not hasattr(request.app.state, "engine"):
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return request.app.state.engine


@router.get("")
async def list_pipelines(
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict:
    """List all pipelines."""
    return {"pipelines": engine.list_pipelines()}


@router.get("/{name}")
async def get_pipeline(
    name: str,
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict:
    """Get detailed pipeline information."""
    try:
        return engine.get_pipeline_status(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {name}")


@router.post("/{name}/start")
async def start_pipeline(
    name: str,
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict:
    """Start a pipeline and all child generators."""
    try:
        engine.start_pipeline(name)
        status = engine.get_pipeline_status(name)
        return {
            "name": name,
            "state": status["state"],
            "message": (
                "Pipeline starting"
                if status["state"] == "STARTING"
                else "Pipeline started"
            ),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {name}")
    except Exception as e:
        detail = log_api_exception(logger, "Start pipeline", e)
        raise HTTPException(status_code=500, detail=detail)


@router.post("/{name}/stop")
async def stop_pipeline(
    name: str,
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict:
    """Stop a pipeline and all child generators."""
    try:
        engine.stop_pipeline(name)
        status = engine.get_pipeline_status(name)
        return {
            "name": name,
            "state": status["state"],
            "message": (
                "Pipeline stopping"
                if status["state"] == "STOPPING"
                else "Pipeline stopped"
            ),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {name}")
    except Exception as e:
        detail = log_api_exception(logger, "Stop pipeline", e)
        raise HTTPException(status_code=500, detail=detail)
