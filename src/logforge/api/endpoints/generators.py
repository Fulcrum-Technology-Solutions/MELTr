"""Generator management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from logforge.core.engine import Engine

router = APIRouter(prefix="/api/generators", tags=["generators"])


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
        List of generators with basic info
    """
    generators = engine.get_all_generators()
    
    return {
        "generators": [
            {
                "name": gen.name,
                "enabled": gen.config.enabled,
                "state": gen.state.value,
                "template": gen.config.template,
            }
            for gen in generators
        ]
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
        raise HTTPException(status_code=500, detail=f"Failed to start generator: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to stop generator: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to restart generator: {str(e)}")


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
                "error": str(e),
                "state": generator.state.value,
            })
    
    return {
        "message": f"Restarted {success_count} of {len(generators)} generator(s)",
        "count": success_count,
        "total": len(generators),
        "results": results,
    }
