"""Health and status endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from logforge.api.server import APIServer

router = APIRouter(prefix="/api", tags=["health"])


def get_server(request: Request) -> APIServer:
    """Dependency to get API server instance from app state."""
    return request.app.state.server


@router.get("/health")
async def health(server: Annotated[APIServer, Depends(get_server)]) -> dict:
    """Health check endpoint.
    
    Returns:
        Health status with component states
    """
    from logforge.core.generator import GeneratorState
    
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
    
    return {
        "status": overall_status,
        "uptime": server.get_uptime(),
        "generators": generator_counts,
        "entity_registry": "healthy",  # TODO: Check registry health
        "template_cache": "healthy",  # TODO: Check cache health
    }


@router.get("/status")
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
    # CRITICAL: get_all_generators() releases lock before returning list
    # So we can safely call get_status() on each generator
    generators_list = []
    if engine:
        generators = engine.get_all_generators()  # Returns list, lock released
        for gen in generators:
            gen_status = gen.get_status()  # Safe - no lock held
            generators_list.append({
                "name": gen_status["name"],
                "state": gen_status["state"],
                "template": gen_status["template"],
                "events_generated": gen_status["statistics"]["events_generated"],
                "errors": gen_status["statistics"]["errors"],
                "uptime": gen_status["statistics"]["uptime"],
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
    
    return {
        "uptime": server.get_uptime(),
        "version": "1.0.0",
        "generators": generators_list,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_mb": int(memory_mb),
            "threads": thread_count,
        },
    }

