"""
Root and utility endpoints.

This module provides root-level endpoints including:
- Root endpoint with application information
- Debug endpoints for testing (e.g., Sentry integration)
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    """
    Root endpoint providing application information.
    
    Returns basic application metadata including name, version, and status.
    Useful for health checks and API discovery.
    
    **Returns:**
    - `name`: Application name
    - `version`: Application version
    - `status`: Current application status
    """
    return {
        "name": "mARB 2.0 - Real-Time Claim Risk Engine",
        "version": "2.0.0",
        "status": "running",
    }


@router.get("/sentry-debug")
async def trigger_error():
    """
    Sentry debug endpoint to verify error tracking is working.
    
    This endpoint intentionally triggers a division by zero error to test Sentry integration.
    Visit http://localhost:8000/sentry-debug to trigger an error that will be sent to Sentry.
    
    **Warning:** This endpoint should be disabled or protected in production environments.
    """
    division_by_zero = 1 / 0
