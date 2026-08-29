"""Health and status endpoints."""

from typing import Annotated, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from meltr.api.auth import require_api_key
from meltr.api.errors import log_api_exception
from meltr.api.server import APIServer
from meltr.core.engine import Engine
from meltr.utils.logging import get_logger

router = APIRouter(prefix="/api", tags=["health"])


def _collect_output_handlers(engine: Engine) -> List:
    """Collect unique output handlers from all generators (by name)."""
    seen: Dict[str, object] = {}
    for gen in engine.get_all_generators():
        for h in getattr(gen, "output_handlers", []):
            if hasattr(h, "name") and h.name not in seen:
                seen[h.name] = h
    return list(seen.values())


def get_server(request: Request) -> APIServer:
    """Dependency to get API server instance from app state."""
    return request.app.state.server


def get_engine(request: Request) -> Engine:
    """Dependency to get engine from app state."""
    if not hasattr(request.app.state, 'engine'):
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return request.app.state.engine


@router.get("/health")
async def health(server: Annotated[APIServer, Depends(get_server)]) -> dict:
    """Health check endpoint.
    
    Returns:
        Health status with component states
    """
    from meltr.core.generator import GeneratorState
    
    # Get engine if available
    engine = None
    if hasattr(server.app.state, 'engine'):
        engine = server.app.state.engine
    
    # Count generator states
    generator_counts = {
        "total": 0,
        "running": 0,
        "degraded": 0,
        "error": 0,
    }
    
    if engine:
        generators = engine.get_all_generators()
        generator_counts["total"] = len(generators)
        for gen in generators:
            state = gen.state
            if state == GeneratorState.RUNNING:
                generator_counts["running"] += 1
            elif state == GeneratorState.DEGRADED:
                generator_counts["degraded"] += 1
            elif state == GeneratorState.ERROR:
                generator_counts["error"] += 1
    
    # Determine overall status
    if generator_counts["error"] > 0:
        overall_status = "unhealthy"
    elif generator_counts["degraded"] > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    outputs_summary = None
    if engine:
        try:
            handlers = _collect_output_handlers(engine)
            outputs_summary = []
            for h in handlers:
                if hasattr(h, "get_statistics"):
                    st = h.get_statistics()
                    outputs_summary.append({
                        "name": st.get("name", getattr(h, "name", "?")),
                        "backlog_size": st.get("backlog_size", 0),
                        "dropped_count": st.get("dropped_count", 0),
                        "healthy": st.get("healthy", True),
                    })
        except Exception:
            pass

    result = {
        "status": overall_status,
        "uptime": server.get_uptime(),
        "generators": generator_counts,
        "entity_registry": "healthy",
        "template_cache": "healthy",
    }
    if outputs_summary is not None:
        result["outputs"] = outputs_summary
    return result


@router.get("/status", dependencies=[Depends(require_api_key)])
async def status(server: Annotated[APIServer, Depends(get_server)]) -> dict:
    """Detailed status endpoint.
    
    Returns:
        Detailed system status with generator information
    """
    import psutil
    import os
    
    # Get engine if available
    engine = None
    if hasattr(server.app.state, 'engine'):
        engine = server.app.state.engine
    
    # Get generator details
    # CRITICAL: Use get_generator_status() which handles locks properly
    # Don't call get_status() directly to avoid deadlock
    generators_list = []
    if engine:
        try:
            # Use engine's safe method that handles locks correctly
            all_status = engine.get_generator_status(name=None)
            if "generators" in all_status:
                for gen_status in all_status["generators"]:
                    generators_list.append({
                        "name": gen_status["name"],
                        "state": gen_status["state"],
                        "template": gen_status["template"],
                        "events_generated": gen_status["statistics"]["events_generated"],
                        "errors": gen_status["statistics"]["errors"],
                        "uptime": gen_status["statistics"]["uptime"],
                    })
        except Exception as e:
            # If status fails, return basic info without detailed stats
            generators = engine.get_all_generators()
            for gen in generators:
                generators_list.append({
                    "name": gen.name,
                    "state": gen.state.value,
                    "template": gen.config.template,
                    "events_generated": 0,
                    "errors": 0,
                    "uptime": 0,
                })
    
    # Get system metrics
    try:
        process = psutil.Process(os.getpid())
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        thread_count = process.num_threads()
    except Exception:
        cpu_percent = 0.0
        memory_mb = 0
        thread_count = 0
    
    outputs_list = []
    if engine:
        try:
            for h in _collect_output_handlers(engine):
                if hasattr(h, "get_statistics"):
                    st = h.get_statistics()
                    outputs_list.append({
                        "name": st.get("name", getattr(h, "name", "?")),
                        "backlog_size": st.get("backlog_size", 0),
                        "dropped_count": st.get("dropped_count", 0),
                        "healthy": st.get("healthy", True),
                        "buffer_size": st.get("buffer_size"),
                    })
        except Exception:
            pass

    return {
        "uptime": server.get_uptime(),
        "version": "1.0.0",
        "generators": generators_list,
        "outputs": outputs_list,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_mb": int(memory_mb),
            "threads": thread_count,
        },
    }


@router.post("/config/reload", dependencies=[Depends(require_api_key)])
async def reload_config(
    server: Annotated[APIServer, Depends(get_server)],
    engine: Annotated[Engine, Depends(get_engine)]
) -> dict:
    """Reload configuration from disk and apply changes.
    
    Detects and applies:
    - Added generators (starts if enabled)
    - Removed generators (stops and removes)
    - Updated generators (restarts if was running)
    
    Returns:
        Reload results with added/removed/updated generators
    """
    from meltr.core.config import load_config
    
    try:
        # Load new config from disk
        new_config = load_config(create_if_missing=False)
        
        # Reload and apply changes
        results = engine.reload_config(new_config)
        
        return {
            "status": "success",
            "message": "Configuration reloaded successfully",
            "results": results,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Config file not found")
    except Exception as e:
        detail = log_api_exception(get_logger(__name__), "Reload config", e)
        raise HTTPException(status_code=500, detail=detail)

