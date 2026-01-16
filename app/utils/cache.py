"""Redis caching utilities."""
import json
import hashlib
from typing import Any, Callable, Optional, TypeVar, cast
from functools import wraps
from threading import Lock
from collections import defaultdict

from app.config.redis import get_redis_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Cache statistics tracking
_cache_stats = defaultdict(lambda: {"hits": 0, "misses": 0})
_stats_lock = Lock()


class Cache:
    """Redis cache wrapper with helper methods."""

    def __init__(self, namespace: str = "marb"):
        """
        Initialize cache with namespace.
        
        Args:
            namespace: Prefix for all cache keys
        """
        self.namespace = namespace
        self.redis = get_redis_client()

    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        return f"{self.namespace}:{key}"

    def get(self, key: str, track_stats: bool = True) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            track_stats: Whether to track statistics for this operation
            
        Returns:
            Cached value or None if not found
        """
        try:
            full_key = self._make_key(key)
            value = self.redis.get(full_key)
            if value is None:
                if track_stats:
                    self._record_miss(key)
                return None
            if track_stats:
                self._record_hit(key)
            return json.loads(value)
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            if track_stats:
                self._record_miss(key)
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key (can include namespace prefix like "claim:123")
            value: Value to cache (must be JSON serializable)
            ttl_seconds: Time to live in seconds. If None, attempts to infer from key pattern.
                        If 0 or negative, key is set without TTL (persistent).
                        If pattern inference fails, key is set without TTL.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            full_key = self._make_key(key)
            serialized = json.dumps(value, default=str)
            
            # If TTL not provided, try to infer from key pattern
            if ttl_seconds is None:
                ttl_seconds = self._infer_ttl_from_key(key)
            
            # Set with TTL if provided and positive, otherwise set without TTL (persistent)
            if ttl_seconds and ttl_seconds > 0:
                self.redis.setex(full_key, ttl_seconds, serialized)
            else:
                self.redis.set(full_key, serialized)
            
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    def _infer_ttl_from_key(self, key: str) -> Optional[int]:
        """
        Infer TTL from cache key pattern.
        
        Args:
            key: Cache key (e.g., "claim:123", "risk_score:456")
            
        Returns:
            TTL in seconds, or None if pattern not recognized
        """
        try:
            from app.config.cache_ttl import get_ttl
            
            # Extract cache type from key pattern
            if key.startswith("claim:"):
                return get_ttl("claim")
            elif key.startswith("risk_score:"):
                return get_ttl("risk_score")
            elif key.startswith("payer:"):
                return get_ttl("payer")
            elif key.startswith("remittance:"):
                return get_ttl("remittance")
            elif key.startswith("episode:"):
                return get_ttl("episode")
            elif key.startswith("provider:"):
                return get_ttl("provider")
            elif key.startswith("practice_config:"):
                return get_ttl("practice_config")
            elif key.startswith("count:"):
                return get_ttl("count")
            
            return None
        except Exception:
            # If config import fails, return None (no TTL)
            return None

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            full_key = self._make_key(key)
            self.redis.delete(full_key)
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern. Uses SCAN for better performance with large datasets.
        
        This method uses Redis SCAN instead of KEYS to avoid blocking operations.
        Keys are deleted in batches for efficiency.
        
        Args:
            pattern: Key pattern (e.g., "claim:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            full_pattern = self._make_key(pattern)
            deleted_count = 0
            cursor = 0
            # Use SCAN with count=100 to batch operations and avoid blocking
            while True:
                cursor, keys = self.redis.scan(cursor=cursor, match=full_pattern, count=100)
                if keys:
                    # Batch delete all keys found in this scan iteration
                    deleted_count += self.redis.delete(*keys)
                # SCAN returns cursor 0 when done
                if cursor == 0:
                    break
            return deleted_count
        except Exception as e:
            logger.warning("Cache delete pattern failed", pattern=pattern, error=str(e))
            return 0

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            full_key = self._make_key(key)
            return bool(self.redis.exists(full_key))
        except Exception as e:
            logger.warning("Cache exists check failed", key=key, error=str(e))
            return False

    def clear_namespace(self) -> int:
        """
        Clear all keys in this namespace.
        
        Returns:
            Number of keys deleted
        """
        return self.delete_pattern("*")

    def _record_hit(self, key: str) -> None:
        """Record a cache hit."""
        with _stats_lock:
            _cache_stats[key]["hits"] += 1

    def _record_miss(self, key: str) -> None:
        """Record a cache miss."""
        with _stats_lock:
            _cache_stats[key]["misses"] += 1

    def get_stats(self, key: Optional[str] = None) -> dict:
        """
        Get cache statistics.
        
        Args:
            key: Optional specific key to get stats for. If None, returns all stats.
            
        Returns:
            Dictionary with cache statistics
        """
        with _stats_lock:
            if key:
                stats = _cache_stats.get(key, {"hits": 0, "misses": 0})
                total = stats["hits"] + stats["misses"]
                hit_rate = (stats["hits"] / total * 100) if total > 0 else 0.0
                return {
                    "key": key,
                    "hits": stats["hits"],
                    "misses": stats["misses"],
                    "total": total,
                    "hit_rate": round(hit_rate, 2),
                }
            else:
                # Aggregate stats
                total_hits = sum(s["hits"] for s in _cache_stats.values())
                total_misses = sum(s["misses"] for s in _cache_stats.values())
                total_requests = total_hits + total_misses
                overall_hit_rate = (
                    (total_hits / total_requests * 100) if total_requests > 0 else 0.0
                )
                
                # Per-key stats
                key_stats = {}
                for k, stats in _cache_stats.items():
                    key_total = stats["hits"] + stats["misses"]
                    key_hit_rate = (
                        (stats["hits"] / key_total * 100) if key_total > 0 else 0.0
                    )
                    key_stats[k] = {
                        "hits": stats["hits"],
                        "misses": stats["misses"],
                        "total": key_total,
                        "hit_rate": round(key_hit_rate, 2),
                    }
                
                return {
                    "overall": {
                        "hits": total_hits,
                        "misses": total_misses,
                        "total": total_requests,
                        "hit_rate": round(overall_hit_rate, 2),
                    },
                    "by_key": key_stats,
                }

    def reset_stats(self, key: Optional[str] = None) -> None:
        """
        Reset cache statistics.
        
        Args:
            key: Optional specific key to reset. If None, resets all stats.
        """
        with _stats_lock:
            if key:
                _cache_stats.pop(key, None)
            else:
                _cache_stats.clear()

    def get_many(self, keys: list[str], track_stats: bool = True) -> dict[str, Any]:
        """
        Get multiple values from cache in a single operation.
        
        Args:
            keys: List of cache keys to retrieve
            track_stats: Whether to track statistics for this operation
            
        Returns:
            Dictionary mapping keys to their cached values (only includes found keys)
        """
        if not keys:
            return {}
        
        try:
            full_keys = [self._make_key(key) for key in keys]
            values = self.redis.mget(full_keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                        if track_stats:
                            self._record_hit(key)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Cache get_many JSON decode failed", key=key, error=str(e))
                        if track_stats:
                            self._record_miss(key)
                else:
                    if track_stats:
                        self._record_miss(key)
            
            return result
        except Exception as e:
            logger.warning("Cache get_many failed", keys=keys, error=str(e))
            if track_stats:
                for key in keys:
                    self._record_miss(key)
            return {}

    def set_many(
        self,
        mapping: dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> int:
        """
        Set multiple values in cache in a single operation.
        
        Args:
            mapping: Dictionary mapping keys to values
            ttl_seconds: Time to live in seconds. If None, attempts to infer from key patterns,
                        otherwise uses default TTL from config.
            
        Returns:
            Number of keys successfully set
        """
        if not mapping:
            return 0
        
        try:
            # Use pipeline for better performance
            pipe = self.redis.pipeline()
            success_count = 0
            
            for key, value in mapping.items():
                try:
                    full_key = self._make_key(key)
                    serialized = json.dumps(value, default=str)
                    
                    # Infer TTL if not provided
                    key_ttl = ttl_seconds
                    if key_ttl is None:
                        key_ttl = self._infer_ttl_from_key(key)
                    
                    if key_ttl:
                        pipe.setex(full_key, key_ttl, serialized)
                    else:
                        pipe.set(full_key, serialized)
                    success_count += 1
                except Exception as e:
                    logger.warning("Cache set_many item failed", key=key, error=str(e))
            
            if success_count > 0:
                pipe.execute()
            
            return success_count
        except Exception as e:
            logger.warning("Cache set_many failed", error=str(e))
            return 0

    def delete_many(self, keys: list[str]) -> int:
        """
        Delete multiple keys from cache in a single operation.
        
        Args:
            keys: List of cache keys to delete
            
        Returns:
            Number of keys successfully deleted
        """
        if not keys:
            return 0
        
        try:
            full_keys = [self._make_key(key) for key in keys]
            deleted_count = self.redis.delete(*full_keys)
            return deleted_count
        except Exception as e:
            logger.warning("Cache delete_many failed", keys=keys, error=str(e))
            return 0

    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds, or None if key doesn't exist or has no TTL
        """
        try:
            full_key = self._make_key(key)
            ttl = self.redis.ttl(full_key)
            # Redis returns -1 if key exists but has no TTL, -2 if key doesn't exist
            if ttl >= 0:
                return ttl
            return None
        except Exception as e:
            logger.warning("Cache get_ttl failed", key=key, error=str(e))
            return None

    def expire(self, key: str, ttl_seconds: int) -> bool:
        """
        Set TTL for an existing key.
        
        Args:
            key: Cache key
            ttl_seconds: Time to live in seconds
            
        Returns:
            True if TTL was set, False if key doesn't exist
        """
        try:
            full_key = self._make_key(key)
            return bool(self.redis.expire(full_key, ttl_seconds))
        except Exception as e:
            logger.warning("Cache expire failed", key=key, error=str(e))
            return False

    def persist(self, key: str) -> bool:
        """
        Remove TTL from a key, making it persistent.
        
        Args:
            key: Cache key
            
        Returns:
            True if TTL was removed, False if key doesn't exist
        """
        try:
            full_key = self._make_key(key)
            return bool(self.redis.persist(full_key))
        except Exception as e:
            logger.warning("Cache persist failed", key=key, error=str(e))
            return False

    def keys(self, pattern: str = "*") -> list[str]:
        """
        Get all keys matching a pattern. Use with caution on large datasets.
        Prefer delete_pattern() for deletion operations.
        
        Args:
            pattern: Key pattern (e.g., "claim:*")
            
        Returns:
            List of matching keys (without namespace prefix)
        """
        try:
            full_pattern = self._make_key(pattern)
            # Use SCAN instead of KEYS for better performance
            matching_keys = []
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor=cursor, match=full_pattern, count=100)
                matching_keys.extend(keys)
                if cursor == 0:
                    break
            
            # Remove namespace prefix from keys
            namespace_prefix = f"{self.namespace}:"
            result_keys = []
            for key in matching_keys:
                # Decode bytes to string if needed
                key_str = key.decode() if isinstance(key, bytes) else key
                # Remove namespace prefix if present
                if key_str.startswith(namespace_prefix):
                    key_str = key_str[len(namespace_prefix):]
                result_keys.append(key_str)
            return result_keys
        except Exception as e:
            logger.warning("Cache keys failed", pattern=pattern, error=str(e))
            return []


# Global cache instance
cache = Cache()


def cached(
    ttl_seconds: Optional[int] = None,
    key_prefix: str = "",
    key_func: Optional[Callable[..., str]] = None,
    invalidate_on: Optional[list[str]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to cache function results.
    
    Args:
        ttl_seconds: Time to live in seconds (default: 3600 = 1 hour)
        key_prefix: Prefix for cache key
        key_func: Function to generate cache key from arguments
        invalidate_on: List of cache key patterns (e.g., ["claim:*", "risk_score:*"]) to invalidate
                       when this function is called. Patterns support Redis wildcards:
                       - "*" matches any number of characters
                       - "?" matches a single character
                       - "[abc]" matches any character in brackets
                       Patterns are used with Redis SCAN command to find matching keys for deletion.
                       This is useful for cache invalidation when related data changes.
                       Example: If a function updates claim data, it can invalidate "claim:*" to
                       clear all claim-related caches.
        
    Example:
        @cached(ttl_seconds=3600, key_prefix="risk_score", invalidate_on=["claim:*"])
        def calculate_risk_score(claim_id: int):
            # Expensive calculation
            return score
            # When this function is called, all keys matching "claim:*" will be deleted
    """
    if ttl_seconds is None:
        ttl_seconds = 3600  # Default 1 hour

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name + arguments hash
                # Use SHA256 for consistent hashing across different Python sessions
                key_parts = [key_prefix, func.__name__]
                cache_key_string = ":".join(filter(None, key_parts))
                
                # Serialize args and kwargs to JSON for consistent hashing
                # Use sort_keys=True to ensure deterministic ordering for dicts
                # For tuples/lists, order is already deterministic
                # Convert args tuple to list for JSON serialization, then sort if it contains dicts
                args_serializable = list(args)
                arg_string = json.dumps(args_serializable, sort_keys=True, default=str)
                kwargs_string = json.dumps(kwargs, sort_keys=True, default=str)
                
                combined_string = cache_key_string + arg_string + kwargs_string
                cache_key = hashlib.sha256(combined_string.encode('utf-8')).hexdigest()
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache hit", key=cache_key, function=func.__name__)
                return cast(T, cached_value)
            
            # Cache miss - execute function
            logger.debug("Cache miss", key=cache_key, function=func.__name__)
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl_seconds=ttl_seconds)
            
            # Invalidate related caches if specified
            if invalidate_on:
                for pattern in invalidate_on:
                    cache.delete_pattern(pattern)
            
            return result

        return wrapper

    return decorator


def cache_key(*parts: Any) -> str:
    """
    Create a cache key from parts.
    
    Args:
        *parts: Key parts to join
        
    Returns:
        Cache key string
    """
    return ":".join(str(part) for part in parts if part is not None)


# Common cache key generators
def claim_cache_key(claim_id: int) -> str:
    """Generate cache key for claim."""
    return cache_key("claim", claim_id)


def risk_score_cache_key(claim_id: int) -> str:
    """Generate cache key for risk score."""
    return cache_key("risk_score", claim_id)


def payer_cache_key(payer_id: int) -> str:
    """Generate cache key for payer."""
    return cache_key("payer", payer_id)


def remittance_cache_key(remittance_id: int) -> str:
    """Generate cache key for remittance."""
    return cache_key("remittance", remittance_id)


def episode_cache_key(episode_id: int) -> str:
    """Generate cache key for episode."""
    return cache_key("episode", episode_id)


def count_cache_key(model_name: str, **filters: Any) -> str:
    """
    Generate cache key for count queries.
    
    Args:
        model_name: Name of the model (e.g., "claim", "remittance", "episode")
        **filters: Filter parameters to include in cache key
        
    Returns:
        Cache key string
    """
    key_parts = ["count", model_name]
    if filters:
        # Sort filters for consistent key generation
        sorted_filters = sorted(filters.items())
        filter_str = ":".join(f"{k}={v}" for k, v in sorted_filters)
        key_parts.append(filter_str)
    return cache_key(*key_parts)

