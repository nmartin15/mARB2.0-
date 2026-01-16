"""Custom exception classes and error handling."""
from typing import Any, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.utils.logger import get_logger
from app.config.sentry import capture_exception, add_breadcrumb, settings

logger = get_logger(__name__)


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code or "APP_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppError):
    """Validation error."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            details=details or {},
        )


class NotFoundError(AppError):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message += f" (id: {identifier})"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
        )


class UnauthorizedError(AppError):
    """Unauthorized access error."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
        )


class ForbiddenError(AppError):
    """Forbidden access error."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle application errors."""
    # Add breadcrumb for context
    add_breadcrumb(
        message=f"Application error: {exc.code}",
        category="error",
        level="warning" if exc.status_code < 500 else "error",
        data={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
        },
    )
    
    logger.warning(
        "Application error",
        error=exc.code,
        message=exc.message,
        path=request.url.path,
        status_code=exc.status_code,
    )
    
    # Send to Sentry based on error severity and alert configuration
    # Always send server errors (>= 500) if alerts are enabled
    # Send client errors (400-499) only if alert_on_errors is enabled
    should_alert = settings.enable_alerts and (
        exc.status_code >= 500 or settings.alert_on_errors
    )
    if should_alert:
        capture_exception(
            exc,
            level="error" if exc.status_code >= 500 else "warning",
            context={
                "request": {
                    "path": request.url.path,
                    "method": request.method,
                    "query_params": dict(request.query_params),
                },
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "status_code": exc.status_code,
                },
            },
            tags={
                "error_type": exc.code,
                "status_code": str(exc.status_code),
                "path": request.url.path,
            },
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors."""
    # Add breadcrumb for context
    add_breadcrumb(
        message="Request validation failed",
        category="validation",
        level="warning",
        data={
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors(),
        },
    )
    
    logger.warning(
        "Validation error",
        path=request.url.path,
        errors=exc.errors(),
    )
    
    # Send to Sentry only if alerts are enabled and alert_on_warnings is True
    # Validation errors are typically not critical, so they require explicit opt-in
    should_alert = settings.enable_alerts and settings.alert_on_warnings
    if should_alert:
        capture_exception(
            exc,
            level="warning",
            context={
                "request": {
                    "path": request.url.path,
                    "method": request.method,
                    "query_params": dict(request.query_params),
                },
                "validation_errors": exc.errors(),
            },
            tags={
                "error_type": "VALIDATION_ERROR",
                "path": request.url.path,
            },
        )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    # Add breadcrumb for context
    add_breadcrumb(
        message=f"Unexpected error: {type(exc).__name__}",
        category="exception",
        level="error",
        data={
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
        },
    )
    
    logger.error(
        "Unexpected error",
        error=str(exc),
        path=request.url.path,
        exc_info=True,
    )
    
    # Always send unexpected exceptions to Sentry if alerts are enabled
    # Unexpected exceptions are always considered errors and should be monitored
    if settings.enable_alerts:
        capture_exception(
            exc,
            level="error",
            context={
                "request": {
                    "path": request.url.path,
                    "method": request.method,
                    "query_params": dict(request.query_params),
                    "url": str(request.url),
                },
            },
            tags={
                "error_type": type(exc).__name__,
                "path": request.url.path,
            },
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )

