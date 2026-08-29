"""Generator management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from meltr.api.auth import require_api_key
from meltr.api.errors import log_api_exception
from meltr.core.engine import Engine
from meltr.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/generators",
    tags=["generators"],
    dependencies=[Depends(require_api_key)],
)


def get_engine(request: Request) -> Engine:
    """Dependency to get engine from app state."""
    if not hasattr(request.app.state, 'engine'):
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return request.app.state.engine


@router.get("")
async def list_generators(
    engine: Annotated[Engine, Depends(get_engine)]
) -> dict:
    """List all generators.
    
    Returns:
        List of generators with basic info including vendor, product, and data_source
    """
    generators = engine.get_all_generators()
    
    generator_list = []
    for gen in generators:
        gen_data = {
            "name": gen.name,
            "enabled": gen.config.enabled,
            "state": gen.state.value,
            "template": gen.config.template,
        }
        
        # Add template metadata if available
        if gen._template_info:
            gen_data["vendor"] = gen._template_info.vendor
            gen_data["product"] = gen._template_info.product
            gen_data["data_source"] = gen._template_info.data_source
        else:
            # Fallback: try to parse from template ID
            template_parts = gen.config.template.split("/")
            if len(template_parts) >= 3:
                gen_data["vendor"] = template_parts[0]
                gen_data["product"] = template_parts[1]
                gen_data["data_source"] = template_parts[2]
            else:
                gen_data["vendor"] = None
                gen_data["product"] = None
                gen_data["data_source"] = None
        
        generator_list.append(gen_data)
    
    return {
        "generators": generator_list
    }


@router.get("/{name}")
async def get_generator(
    name: str,
    engine: Annotated[Engine, Depends(get_engine)]
) -> dict:
    """Get detailed generator information.
    
    Args:
        name: Generator name
        
    Returns:
        Detailed generator status
    """
    try:
        status = engine.get_generator_status(name)
        return status
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Generator not found: {name}")


@router.post("/{name}/start")
async def start_generator(
    name: str,
    engine: Annotated[Engine, Depends(get_engine)]
) -> dict:
    """Start a generator.
    
    Args:
        name: Generator name
        
    Returns:
        Generator state after start
    """
    try:
        engine.start_generator(name)
        status = engine.get_generator_status(name)
        return {
            "name": name,
            "state": status["state"],
            "message": "Generator starting" if status["state"] == "STARTING" else "Generator started",
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Generator not found: {name}")
    except Exception as e:
        detail = log_api_exception(logger, "Start generator", e)
        raise HTTPException(status_code=500, detail=detail)


@router.post("/{name}/stop")
async def stop_generator(
    name: str,
    engine: Annotated[Engine, Depends(get_engine)]
) -> dict:
    """Stop a generator.
    
    Args:
        name: Generator name
        
    Returns:
        Generator state after stop
    """
    try:
        engine.stop_generator(name)
        status = engine.get_generator_status(name)
        return {
            "name": name,
            "state": status["state"],
            "message": "Generator stopping" if status["state"] == "STOPPING" else "Generator stopped",
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Generator not found: {name}")
    except Exception as e:
        detail = log_api_exception(logger, "Stop generator", e)
        raise HTTPException(status_code=500, detail=detail)


@router.post("/{name}/restart")
async def restart_generator(
    name: str,
    engine: Annotated[Engine, Depends(get_engine)]
) -> dict:
    """Restart a generator.
    
    Args:
        name: Generator name
        
    Returns:
        Generator state after restart
    """
    try:
        engine.restart_generator(name)
        status = engine.get_generator_status(name)
        return {
            "name": name,
            "state": status["state"],
            "message": "Generator restarting",
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Generator not found: {name}")
    except Exception as e:
        detail = log_api_exception(logger, "Restart generator", e)
        raise HTTPException(status_code=500, detail=detail)


@router.post("/restart-all")
async def restart_all_generators(
    engine: Annotated[Engine, Depends(get_engine)]
) -> dict:
    """Restart all generators.
    
    Returns:
        Summary of restart operations
    """
    generators = engine.get_all_generators()
    results = []
    success_count = 0
    
    for generator in generators:
        try:
            engine.restart_generator(generator.name)
            status = engine.get_generator_status(generator.name)
            results.append({
                "name": generator.name,
                "success": True,
                "state": status["state"],
            })
            success_count += 1
        except Exception as e:
            results.append({
                "name": generator.name,
                "success": False,
                "error": log_api_exception(logger, f"Restart generator {generator.name}", e),
                "state": generator.state.value,
            })
    
    return {
        "message": f"Restarted {success_count} of {len(generators)} generator(s)",
        "count": success_count,
        "total": len(generators),
        "results": results,
    }
