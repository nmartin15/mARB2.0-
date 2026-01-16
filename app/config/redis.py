"""Redis configuration."""
import redis
from typing import Optional
import os

from app.utils.logger import get_logger

logger = get_logger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD") or None,
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
            socket_connect_timeout=5,
        )
        try:
            _redis_client.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    return _redis_client

