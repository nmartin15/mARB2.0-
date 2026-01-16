"""
Application factory and setup functions.

This module provides functions to build and configure the FastAPI application,
including middleware setup, route registration, error handlers, and static file mounting.

**Documentation References:**
- Main Entry Point: `app/main.py` uses functions from this module
- Middleware: See `app/api/middleware/` for middleware implementations
- Routes: See `app/api/routes/` for route implementations
- Configuration: See `app/config/` for configuration modules
"""
from contextlib import asynccontextmanager
from typing import Callable
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from app.config.database import init_db
from app.api.middleware.audit import AuditMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.auth_middleware import OptionalAuthMiddleware
from app.utils.logger import get_logger
from app.utils.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
    general_exception_handler,
)
from app.config.security import (
    get_cors_origins,
    get_cors_methods,
    get_cors_headers,
    get_rate_limit_per_minute,
    get_rate_limit_per_hour,
)

logger = get_logger(__name__)


def create_lifespan() -> Callable:
    """
    Create application lifespan context manager.
    
    Returns:
        Async context manager for application startup and shutdown events.
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan events."""
        # Startup
        logger.info("Starting application...")
        await init_db()
        logger.info("Application started successfully")
        yield
        # Shutdown
        logger.info("Shutting down application...")
    
    return lifespan


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all application middleware.
    
    Middleware order matters - they are executed in reverse order of registration:
    1. CORS (last registered, first executed)
    2. Optional Authentication
    3. Rate Limiting
    4. Audit Logging (first registered, last executed)
    
    Args:
        app: FastAPI application instance
    """
    # CORS middleware (last registered, first executed)
    # Use environment-aware CORS configuration for better security
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=get_cors_methods(),
        allow_headers=get_cors_headers(),
    )
    
    # Optional authentication middleware (enforces auth if REQUIRE_AUTH=true)
    app.add_middleware(OptionalAuthMiddleware)
    
    # Rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=get_rate_limit_per_minute(),
        requests_per_hour=get_rate_limit_per_hour(),
    )
    
    # Audit logging middleware (first registered, last executed)
    app.add_middleware(AuditMiddleware)
    
    logger.info("Middleware configured successfully")


def setup_error_handlers(app: FastAPI) -> None:
    """
    Register all application error handlers.
    
    Error handlers are registered in order of specificity:
    1. AppError (most specific application errors)
    2. RequestValidationError (FastAPI validation errors)
    3. Exception (catch-all for unexpected errors)
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Error handlers registered successfully")


def register_routes(app: FastAPI) -> None:
    """
    Register all API route routers.
    
    Routes are organized by domain:
    - Root endpoints (application info, debug)
    - Health checks
    - Claims processing
    - Remits processing
    - Episodes management
    - Risk scoring
    - Learning/ML
    - Audit logging
    - Integrations
    - WebSocket connections
    
    Args:
        app: FastAPI application instance
    """
    from app.api.routes import (
        root,
        health,
        claims,
        remits,
        episodes,
        risk,
        learning,
        audit,
        integrations,
        websocket,
    )
    
    # Root endpoints (no prefix)
    app.include_router(root.router, tags=["root"])
    
    # API v1 routes
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(claims.router, prefix="/api/v1", tags=["claims"])
    app.include_router(remits.router, prefix="/api/v1", tags=["remits"])
    app.include_router(episodes.router, prefix="/api/v1", tags=["episodes"])
    app.include_router(risk.router, prefix="/api/v1", tags=["risk"])
    app.include_router(learning.router, prefix="/api/v1", tags=["learning"])
    app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
    
    # Routes without /api/v1 prefix
    app.include_router(integrations.router, tags=["integrations"])
    app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
    
    logger.info("Routes registered successfully")


def mount_static_files(app: FastAPI) -> None:
    """
    Mount static file directories (e.g., monitoring dashboard).
    
    This allows static files to be served directly by FastAPI, avoiding CORS issues
    since dashboard and API are on the same origin.
    
    Args:
        app: FastAPI application instance
    """
    # Serve monitoring dashboard as static files
    # This allows the dashboard to be accessed at http://localhost:8000/monitoring/dashboard.html
    # and avoids CORS issues since dashboard and API are on the same origin
    try:
        monitoring_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "monitoring"
        )
        if os.path.exists(monitoring_dir):
            app.mount(
                "/monitoring", StaticFiles(directory=monitoring_dir), name="monitoring"
            )
            logger.info("Monitoring dashboard available at /monitoring/dashboard.html")
    except Exception as e:
        logger.warning("Could not mount monitoring dashboard", error=str(e))


def create_application() -> FastAPI:
    """
    Create and configure FastAPI application instance.
    
    This function builds a complete FastAPI application with:
    - Application metadata (title, description, version)
    - Lifespan events (startup/shutdown)
    - Middleware (CORS, auth, rate limiting, audit)
    - Error handlers
    - Route registration
    - Static file mounting
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="mARB 2.0 - Real-Time Claim Risk Engine",
        description="Real-time claim risk engine for healthcare practices",
        version="2.0.0",
        lifespan=create_lifespan(),
    )
    
    # Configure application components
    setup_middleware(app)
    setup_error_handlers(app)
    register_routes(app)
    mount_static_files(app)
    
    return app
