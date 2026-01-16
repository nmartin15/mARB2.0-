"""Optional authentication enforcement middleware."""
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.security import is_auth_required, get_auth_exempt_paths
from app.api.middleware.auth import get_current_user
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OptionalAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to optionally enforce authentication.
    
    When REQUIRE_AUTH=true, all endpoints except exempt paths require authentication.
    When REQUIRE_AUTH=false (development), authentication is optional.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check authentication if required."""
        # Check if auth is required
        if not is_auth_required():
            return await call_next(request)
        
        # Check if path is exempt
        exempt_paths = get_auth_exempt_paths()
        if request.url.path in exempt_paths:
            return await call_next(request)
        
        # Check for authentication token
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(
                "Unauthenticated request to protected endpoint",
                path=request.url.path,
                method=request.method,
                ip=request.client.host if request.client else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Token is present, let the endpoint handler validate it
        # (get_current_user dependency will handle validation)
        return await call_next(request)

