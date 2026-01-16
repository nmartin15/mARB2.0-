"""Rate limiting middleware."""
from typing import Callable, Tuple, Dict, List, Optional, TYPE_CHECKING
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
from collections import defaultdict
import time
import os
import bisect

from app.utils.logger import get_logger

if TYPE_CHECKING:
    import redis

logger = get_logger(__name__)

# Skip rate limiting in test mode
TESTING = os.getenv("TESTING", "false").lower() == "true"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    
    Uses Redis for shared state in production (multi-worker safe).
    Falls back to in-memory storage for testing or when Redis is unavailable.
    
    WARNING: In-memory storage is NOT safe for multi-worker/multi-process deployments.
    Each worker maintains its own separate rate limit counters, which can lead to:
    - Inconsistent rate limiting across workers
    - Race conditions where rate limits are bypassed
    - Inaccurate rate limit headers
    
    For production deployments with multiple workers, Redis MUST be configured and available.
    """

    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        """
        Initialize rate limiter.
        
        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests per minute per IP
            requests_per_hour: Maximum requests per hour per IP
            
        Raises:
            RuntimeError: If Redis is not available in production environment
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        # Try to use Redis for shared state (production)
        self.redis_client: Optional["redis.Redis"] = None
        try:
            from app.config.redis import get_redis_client
            self.redis_client = get_redis_client()
            # Test Redis connection to ensure it's actually working
            self.redis_client.ping()
            logger.info("Rate limiting using Redis for shared state (multi-worker safe)")
        except Exception as e:
            # Check if we're in production
            environment = os.getenv("ENVIRONMENT", "development").lower()
            is_production = environment in ("production", "prod")
            
            # Check if Redis is required (default: required in production)
            require_redis = os.getenv("RATE_LIMIT_REQUIRE_REDIS", "true" if is_production else "false").lower() == "true"
            
            if is_production and require_redis:
                # In production with Redis required, fail fast to prevent race conditions
                error_msg = (
                    "CRITICAL: Redis is required for rate limiting in production but is not available. "
                    "This will cause race conditions in multi-worker deployments where each worker "
                    "maintains separate rate limit counters, allowing rate limits to be bypassed. "
                    "Please configure Redis immediately.\n\n"
                    f"Error: {str(e)}\n\n"
                    "To fix:\n"
                    "  1. Ensure Redis is running and accessible\n"
                    "  2. Set REDIS_HOST and REDIS_PORT environment variables\n"
                    "  3. If using Redis password, set REDIS_PASSWORD\n"
                    "  4. For single-worker deployments only, set RATE_LIMIT_REQUIRE_REDIS=false "
                    "(NOT recommended for production)"
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)
            elif is_production:
                # Production but Redis not required (single-worker deployment)
                logger.warning(
                    "Redis not available for rate limiting in production. "
                    "Using in-memory storage (single-worker only). "
                    "This is only safe if you have exactly ONE worker process. "
                    "For multi-worker deployments, Redis is REQUIRED to prevent race conditions.",
                    error=str(e),
                )
            else:
                # Development/testing - allow in-memory fallback
                logger.warning(
                    "Redis not available for rate limiting, using in-memory storage "
                    "(single-worker only - NOT safe for production)",
                    error=str(e),
                )
            self.redis_client = None
        
        # Fallback: Store request timestamps per IP (in-memory, single-worker only)
        # WARNING: This is NOT safe for multi-worker deployments!
        self.request_times: Dict[str, List[float]] = defaultdict(list)
        # Cleanup old entries periodically
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded IP (from proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"

    def _cleanup_old_entries(self):
        """Remove old request timestamps to prevent memory leaks."""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        cutoff_minute = current_time - 60
        cutoff_hour = current_time - 3600
        
        # Clean up old entries
        for ip in list(self.request_times.keys()):
            # Keep only recent requests (within last hour)
            self.request_times[ip] = [
                t for t in self.request_times[ip] if t > cutoff_hour
            ]
            # Remove empty entries
            if not self.request_times[ip]:
                del self.request_times[ip]
        
        self.last_cleanup = current_time

    def _check_rate_limit_redis(self, ip: str) -> Tuple[bool, str, int, int]:
        """
        Check rate limit using Redis (shared state, multi-worker safe).
        
        Returns:
            (is_allowed, error_message, requests_last_minute, requests_last_hour)
        """
        minute_key = f"rl:{ip}:minute"
        hour_key = f"rl:{ip}:hour"
        
        pipe = self.redis_client.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)
        minute_count, _, hour_count, _ = pipe.execute()
        
        if minute_count > self.requests_per_minute:
            return (
                False,
                f"Rate limit exceeded: {minute_count}/{self.requests_per_minute} requests per minute",
                minute_count,
                hour_count,
            )
        
        if hour_count > self.requests_per_hour:
            return (
                False,
                f"Rate limit exceeded: {hour_count}/{self.requests_per_hour} requests per hour",
                minute_count,
                hour_count,
            )
        
        return True, "", minute_count, hour_count

    def _check_rate_limit_memory(self, ip: str) -> Tuple[bool, str, int, int]:
        """
        Check rate limit using in-memory storage (single-worker only).
        
        WARNING: This method is NOT safe for multi-worker/multi-process deployments.
        Each worker process maintains its own separate `self.request_times` dictionary,
        which means rate limits are not shared across workers. This can lead to:
        - Rate limits being bypassed (each worker has its own counter)
        - Inconsistent rate limiting behavior
        - Race conditions in high-traffic scenarios
        
        This method should ONLY be used for:
        - Single-worker deployments
        - Development/testing environments
        - Fallback when Redis is temporarily unavailable (with warnings)
        
        Optimized to use reverse iteration with early break to avoid O(n) scans
        of the entire request history. Since timestamps are appended chronologically,
        iterating in reverse allows us to break early when we encounter requests
        outside the time windows.
        
        Args:
            ip: Client IP address to check rate limit for
            
        Returns:
            (is_allowed, error_message, requests_last_minute, requests_last_hour)
        """
        current_time = time.time()
        cutoff_minute = current_time - 60
        cutoff_hour = current_time - 3600
        
        # Get recent requests (sorted chronologically)
        recent_requests = self.request_times[ip]
        
        if not recent_requests:
            return True, "", 0, 0
        
        # Optimized: Use binary search to find cutoff points (O(log n) instead of O(n))
        # Since timestamps are appended chronologically, we can use bisect to find
        # the index where requests transition from valid to expired, then count from there.
        # This is much more efficient than iterating through all requests.
        
        # Find the index where requests become older than the cutoff windows
        # bisect_left returns the insertion point, which is the first index where
        # the value would be >= cutoff (i.e., still valid)
        minute_start_idx = bisect.bisect_left(recent_requests, cutoff_minute)
        hour_start_idx = bisect.bisect_left(recent_requests, cutoff_hour)
        
        # Count requests within each window (from cutoff index to end)
        requests_last_minute = len(recent_requests) - minute_start_idx
        requests_last_hour = len(recent_requests) - hour_start_idx
        
        if requests_last_minute >= self.requests_per_minute:
            return (
                False,
                f"Rate limit exceeded: {requests_last_minute}/{self.requests_per_minute} requests per minute",
                requests_last_minute,
                requests_last_hour,
            )
        
        if requests_last_hour >= self.requests_per_hour:
            return (
                False,
                f"Rate limit exceeded: {requests_last_hour}/{self.requests_per_hour} requests per hour",
                requests_last_minute,
                requests_last_hour,
            )
        
        return True, "", requests_last_minute, requests_last_hour

    def _check_rate_limit(self, ip: str) -> Tuple[bool, str, int, int]:
        """
        Check if IP has exceeded rate limits.
        
        Returns:
            (is_allowed, error_message, requests_last_minute, requests_last_hour)
        """
        if self.redis_client:
            try:
                return self._check_rate_limit_redis(ip)
            except Exception as e:
                logger.warning(
                    "Redis rate limit check failed, falling back to memory",
                    error=str(e),
                    ip=ip,
                )
                # Fall back to memory-based check
                return self._check_rate_limit_memory(ip)
        else:
            return self._check_rate_limit_memory(ip)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to requests."""
        # Skip rate limiting in test mode
        if TESTING:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path in ["/api/v1/health", "/"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Cleanup old entries periodically (only for in-memory storage)
        # NOTE: In-memory storage is NOT safe for multi-worker deployments
        if not self.redis_client:
            self._cleanup_old_entries()
        
        # Check rate limit
        is_allowed, error_message, requests_last_minute, requests_last_hour = self._check_rate_limit(client_ip)
        
        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                ip=client_ip,
                path=request.url.path,
                method=request.method,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_message,
                headers={"Retry-After": "60"},
            )
        
        # Record this request (only for in-memory storage, Redis is updated in _check_rate_limit_redis)
        # For in-memory: counts from _check_rate_limit_memory are BEFORE this request
        # For Redis: counts from _check_rate_limit_redis already include this request (via incr)
        # So we need to add 1 to in-memory counts for consistency in headers
        if not self.redis_client:
            current_time = time.time()
            self.request_times[client_ip].append(current_time)
            # Increment counts to include current request (for consistent header values)
            requests_last_minute += 1
            requests_last_hour += 1
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers (counts include current request for both Redis and in-memory)
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, self.requests_per_minute - requests_last_minute)
        )
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            max(0, self.requests_per_hour - requests_last_hour)
        )
        
        return response

