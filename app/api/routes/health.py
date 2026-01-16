"""Health check endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import time

from app.config.database import get_db
from app.config.redis import get_redis_client
from app.config.celery import celery_app
from app.utils.cache import cache
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns a simple status indicating the API is running.
    Use `/api/v1/health/detailed` for comprehensive health checks including
    database, Redis, and Celery status.
    
    **Returns:**
    - `status`: "healthy" if API is running
    - `version`: Current API version
    """
    return HealthResponse(status="healthy", version="2.0.0")


@router.get("/cache/stats")
async def get_cache_stats(key: str = None):
    """
    Get cache statistics.
    
    Returns cache performance metrics including hit rate, misses, and usage statistics.
    
    **Parameters:**
    - `key` (query, optional): Specific cache key to get stats for. If not provided,
      returns aggregate statistics for all keys.
    
    **Returns:**
    - Cache statistics including:
      - `hits`: Number of cache hits
      - `misses`: Number of cache misses
      - `hit_rate`: Cache hit rate as a percentage
      - `size`: Current cache size
      - Additional key-specific metrics if `key` is provided
    """
    try:
        stats = cache.get_stats(key=key)
        return stats
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e), exc_info=True)
        return {
            "error": "Failed to retrieve cache statistics",
            "details": str(e)
        }


@router.post("/cache/stats/reset")
async def reset_cache_stats(key: str = None):
    """
    Reset cache statistics.
    
    Resets cache performance metrics. Useful for testing or after cache configuration changes.
    
    **Parameters:**
    - `key` (query, optional): Specific cache key to reset statistics for.
      If not provided, resets all cache statistics.
    
    **Returns:**
    - Confirmation message indicating which statistics were reset
    """
    try:
        cache.reset_stats(key=key)
        return {
            "message": f"Cache statistics reset for {'key: ' + key if key else 'all keys'}"
        }
    except Exception as e:
        logger.error("Failed to reset cache stats", error=str(e), exc_info=True)
        return {
            "error": "Failed to reset cache statistics",
            "details": str(e)
        }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check including all dependencies.
    
    Returns:
        Health status for API, database, Redis, and Celery
    """
    health_status = {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        start = time.time()
        db.execute(text("SELECT 1"))
        response_time = (time.time() - start) * 1000
        health_status["components"]["database"] = {
            "status": "healthy",
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        logger.error("Database health check failed", error=str(e))
    
    # Check Redis
    try:
        redis_client = get_redis_client()
        start = time.time()
        redis_client.ping()
        response_time = (time.time() - start) * 1000
        health_status["components"]["redis"] = {
            "status": "healthy",
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        logger.error("Redis health check failed", error=str(e))
    
    # Check Celery
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        if active_workers:
            health_status["components"]["celery"] = {
                "status": "healthy",
                "active_workers": len(active_workers),
                "worker_names": list(active_workers.keys())
            }
        else:
            health_status["status"] = "degraded"
            health_status["components"]["celery"] = {
                "status": "unhealthy",
                "error": "No active workers found"
            }
            logger.warning("Celery health check: No active workers")
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["celery"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        logger.error("Celery health check failed", error=str(e))
    
    return health_status

