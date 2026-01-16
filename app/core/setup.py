"""
Application setup and initialization.

This module handles early application initialization tasks that must be performed
before the FastAPI application is created, including:
- Environment variable loading
- Sentry initialization
- Logging configuration
- Security validation

**Documentation References:**
- Main Entry Point: `app/main.py` calls `setup_application()` before creating app
- Configuration: See `app/config/` for configuration modules
- Security: See `app/config/security.py` for security validation
"""
import os

from dotenv import load_dotenv

from app.config.sentry import init_sentry
from app.utils.logger import get_logger, configure_logging
from app.config.security import validate_security_settings


def setup_application() -> None:
    """
    Initialize application environment and configuration.
    
    This function must be called before creating the FastAPI application instance.
    It performs critical initialization tasks in the correct order:
    1. Load environment variables from .env file
    2. Initialize Sentry error tracking (must be early to catch import errors)
    3. Configure logging system
    4. Validate security settings (prevents insecure startup)
    
    The order is critical:
    - Environment variables must be loaded first (needed by all other components)
    - Sentry must be initialized early (before other imports that might error)
    - Logging must be configured before validation (for error messages)
    - Security validation must pass before app creation (prevents insecure config)
    
    Raises:
        AppError: If security validation fails (prevents app from starting)
    """
    # Step 1: Load .env file FIRST
    # This ensures environment variables are available to all modules
    load_dotenv()
    
    # Step 2: Initialize Sentry SECOND, before any other imports (including FastAPI)
    # This ensures all errors are captured, including import-time errors
    init_sentry()
    
    # Step 3: Configure logging
    # Must be done after environment variables are loaded but before validation
    configure_logging(
        log_level=os.getenv("LOG_LEVEL", "info"),
        log_format=os.getenv("LOG_FORMAT", "json"),
        log_file=os.getenv(
            "LOG_FILE",
            "app.log" if os.getenv("ENVIRONMENT") == "production" else None,
        ),
        log_dir=os.getenv("LOG_DIR", "logs"),
    )
    
    # Get logger after configuration
    logger = get_logger(__name__)
    
    # Step 4: Validate security settings at startup
    # This MUST be called before the app starts to ensure no defaults are used in production
    try:
        validate_security_settings()
        logger.info("Security settings validated successfully")
    except Exception as e:
        logger.critical(
            "Security validation failed - application cannot start", error=str(e)
        )
        raise
