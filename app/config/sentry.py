"""Sentry error tracking configuration."""
import os
from typing import Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings

from app.utils.logger import get_logger

logger = get_logger(__name__)


class SentrySettings(BaseSettings):
    """Sentry configuration settings."""

    dsn: Optional[str] = Field(None, alias="SENTRY_DSN")
    environment: str = Field("development", alias="SENTRY_ENVIRONMENT")
    release: Optional[str] = Field(None, alias="SENTRY_RELEASE")
    traces_sample_rate: float = Field(0.1, alias="SENTRY_TRACES_SAMPLE_RATE")  # 10% of transactions
    profiles_sample_rate: float = Field(0.1, alias="SENTRY_PROFILES_SAMPLE_RATE")  # 10% of profiles
    send_default_pii: bool = Field(False, alias="SENTRY_SEND_DEFAULT_PII")  # Don't send PII by default (HIPAA compliance)
    enable_before_send_filter: bool = Field(True, alias="SENTRY_ENABLE_BEFORE_SEND_FILTER")  # Enable sensitive data filtering
    
    # Configurable sensitive keys (comma-separated list from environment)
    sensitive_headers: str = Field(
        "authorization,cookie,x-api-key,x-auth-token,x-access-token",
        alias="SENTRY_SENSITIVE_HEADERS"
    )
    sensitive_keys: str = Field(
        "password,token,secret,key,ssn,credit_card,phi",
        alias="SENTRY_SENSITIVE_KEYS"
    )
    
    # Alert configuration
    enable_alerts: bool = Field(True, alias="SENTRY_ENABLE_ALERTS")
    alert_on_errors: bool = Field(True, alias="SENTRY_ALERT_ON_ERRORS")
    alert_on_warnings: bool = Field(False, alias="SENTRY_ALERT_ON_WARNINGS")
    
    # Performance monitoring
    enable_tracing: bool = Field(True, alias="SENTRY_ENABLE_TRACING")
    enable_profiling: bool = Field(False, alias="SENTRY_ENABLE_PROFILING")  # Can be expensive, disable by default
    
    # Integration settings
    enable_fastapi_integration: bool = Field(True, alias="SENTRY_ENABLE_FASTAPI_INTEGRATION")
    enable_celery_integration: bool = Field(True, alias="SENTRY_ENABLE_CELERY_INTEGRATION")
    enable_sqlalchemy_integration: bool = Field(True, alias="SENTRY_ENABLE_SQLALCHEMY_INTEGRATION")
    enable_redis_integration: bool = Field(True, alias="SENTRY_ENABLE_REDIS_INTEGRATION")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
        populate_by_name = True  # Allow both field name and alias


settings = SentrySettings()


def init_sentry() -> None:
    """
    Initialize Sentry error tracking.
    
    This should be called early in application startup, before any other imports
    that might generate errors. In `main.py`, this is called immediately after
    loading environment variables and before importing application modules.
    
    **Initialization Order:**
    1. Load environment variables (via `load_dotenv()`)
    2. Call `init_sentry()` (this function)
    3. Import and initialize other application components
    
    **Configuration:**
    - Requires `SENTRY_DSN` environment variable to be set
    - If DSN is not set, Sentry is disabled and errors are only logged locally
    - Integrations are automatically enabled based on configuration
    
    **Note:**
    The function handles ImportError gracefully if sentry-sdk is not installed,
    allowing the application to run without Sentry in development environments.
    """
    if not settings.dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return
    
    # Warn if using default sensitive keys in production
    if settings.environment.lower() in ("production", "prod") and settings.enable_before_send_filter:
        default_headers = "authorization,cookie,x-api-key,x-auth-token,x-access-token"
        default_keys = "password,token,secret,key,ssn,credit_card,phi"
        if settings.sensitive_headers == default_headers or settings.sensitive_keys == default_keys:
            logger.warning(
                "Using default sensitive key patterns in production. "
                "Consider customizing SENTRY_SENSITIVE_HEADERS and SENTRY_SENSITIVE_KEYS "
                "for your specific use case.",
                environment=settings.environment,
            )
    
    # Skip Sentry initialization during tests
    if os.getenv("TESTING") == "true":
        logger.info("Skipping Sentry initialization in test environment")
        return
    
    try:
        # Suppress urllib3 warnings for LibreSSL compatibility (macOS)
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
            import sentry_sdk
            from sentry_sdk.integrations.celery import CeleryIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration
        
        integrations = []
        
        # FastAPI integration is automatically enabled when fastapi is installed
        # No need to explicitly add FastApiIntegration() - Sentry SDK detects it automatically
        
        if settings.enable_celery_integration:
            integrations.append(CeleryIntegration())
        
        if settings.enable_sqlalchemy_integration:
            integrations.append(SqlalchemyIntegration())
        
        if settings.enable_redis_integration:
            integrations.append(RedisIntegration())
        
        # Logging integration to capture log messages as breadcrumbs
        logging_integration = LoggingIntegration(
            level=None,  # Capture all logs as breadcrumbs
            event_level=None,  # Don't send log events (we handle errors explicitly)
        )
        integrations.append(logging_integration)
        
        sentry_sdk.init(
            dsn=settings.dsn,
            environment=settings.environment,
            release=settings.release,
            traces_sample_rate=settings.traces_sample_rate if settings.enable_tracing else 0.0,
            profiles_sample_rate=settings.profiles_sample_rate if settings.enable_profiling else 0.0,
            send_default_pii=settings.send_default_pii,
            integrations=integrations,
            before_send=filter_sensitive_data if settings.enable_before_send_filter else None,
        )
        
        logger.info(
            "Sentry initialized",
            environment=settings.environment,
            release=settings.release,
            tracing_enabled=settings.enable_tracing,
            filter_enabled=settings.enable_before_send_filter,
        )
    except ImportError:
        logger.warning("sentry-sdk not installed, error tracking disabled")
    except Exception as e:
        logger.error("Failed to initialize Sentry", error=str(e), exc_info=True)
        # Don't re-raise in test environment - allow tests to run even if Sentry fails
        if os.getenv("TESTING") != "true":
            raise


def filter_sensitive_data(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Filter sensitive data from Sentry events for HIPAA compliance.
    
    This function removes or sanitizes sensitive information before sending
    to Sentry, which is critical for HIPAA compliance. It filters:
    
    **Filtered Information:**
    - **Headers**: Authorization tokens, API keys, cookies, and other authentication headers
      (configurable via `SENTRY_SENSITIVE_HEADERS`)
    - **User Data**: Keeps only safe identifiers (id, username), removes sensitive fields
    - **Extra Context**: Removes keys matching sensitive patterns like passwords, tokens,
      secrets, SSNs, credit cards, PHI (configurable via `SENTRY_SENSITIVE_KEYS`)
    
    **How It Works:**
    1. Removes sensitive headers from request data
    2. Sanitizes user context to only include safe identifiers
    3. Scans extra context for sensitive key patterns and removes them
    4. Uses case-insensitive matching for comprehensive filtering
    
    **Configuration:**
    - `SENTRY_SENSITIVE_HEADERS`: Comma-separated list of header names to filter
    - `SENTRY_SENSITIVE_KEYS`: Comma-separated list of key patterns to filter from extra context
    
    **Args:**
        event: The Sentry event dictionary containing error/exception data
        hint: Additional context about the event (exception type, etc.)
        
    **Returns:**
        Modified event dictionary with sensitive data removed, or None to drop the event entirely
    """
    # Get configurable sensitive keys from settings
    sensitive_headers_list = [
        header.strip().lower()
        for header in settings.sensitive_headers.split(",")
        if header.strip()
    ]
    sensitive_keys_list = [
        key.strip().lower()
        for key in settings.sensitive_keys.split(",")
        if key.strip()
    ]
    
    # Remove sensitive headers
    if "request" in event and "headers" in event["request"]:
        for header in sensitive_headers_list:
            # Check both exact match and case-insensitive match
            headers_to_remove = [
                h for h in event["request"]["headers"].keys()
                if h.lower() == header
            ]
            for header_key in headers_to_remove:
                event["request"]["headers"].pop(header_key, None)
    
    # Remove sensitive data from user context
    if "user" in event:
        # Keep only safe user identifiers
        safe_user = {
            "id": event["user"].get("id"),
            "username": event["user"].get("username"),
        }
        event["user"] = safe_user
    
    # Remove sensitive data from extra context
    if "extra" in event:
        for key in sensitive_keys_list:
            # Check both exact match and case-insensitive match
            keys_to_remove = [
                k for k in event["extra"].keys()
                if k.lower() == key or key in k.lower()
            ]
            for key_to_remove in keys_to_remove:
                event["extra"].pop(key_to_remove, None)
    
    return event


def _configure_sentry_scope(
    scope,
    context: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
) -> None:
    """
    Configure a Sentry scope with context, user, and tags.
    
    This is a helper function to reduce code duplication between
    capture_exception and capture_message.
    
    Args:
        scope: Sentry scope object to configure
        context: Additional context dictionary
        user: User information dictionary
        tags: Tags to attach to the event
    """
    if context:
        for key, value in context.items():
            scope.set_context(key, value if isinstance(value, dict) else {"value": value})
    
    if user:
        scope.user = user
    
    if tags:
        for key, value in tags.items():
            scope.set_tag(key, value)


def capture_exception(
    exception: Exception,
    level: str = "error",
    context: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Capture an exception to Sentry with additional context.
    
    Args:
        exception: The exception to capture
        level: Severity level (debug, info, warning, error, fatal)
        context: Additional context dictionary
        user: User information dictionary
        tags: Tags to attach to the event
        
    Returns:
        Event ID if Sentry is configured, None otherwise
        
    Raises:
        Exception: Re-raises any exception that occurs during Sentry capture
            (except ImportError, which is expected if sentry-sdk is not installed)
    """
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            _configure_sentry_scope(scope, context, user, tags)
            return sentry_sdk.capture_exception(exception)
    except ImportError:
        # Expected if sentry-sdk is not installed - return None silently
        return None
    except Exception as e:
        # Log the error but re-raise to prevent silent failures
        logger.error("Failed to capture exception to Sentry", error=str(e), exc_info=True)
        raise


def capture_message(
    message: str,
    level: str = "info",
    context: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Capture a message to Sentry.
    
    Args:
        message: The message to capture
        level: Severity level (debug, info, warning, error, fatal)
        context: Additional context dictionary
        user: User information dictionary
        tags: Tags to attach to the event
        
    Returns:
        Event ID if Sentry is configured, None otherwise
        
    Raises:
        Exception: Re-raises any exception that occurs during Sentry capture
            (except ImportError, which is expected if sentry-sdk is not installed)
    """
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            _configure_sentry_scope(scope, context, user, tags)
            
            # Map string level to Sentry Severity
            level_map = {
                "debug": "debug",
                "info": "info",
                "warning": "warning",
                "error": "error",
                "fatal": "fatal",
            }
            sentry_level = level_map.get(level.lower(), "info")
            return sentry_sdk.capture_message(message, level=sentry_level)
    except ImportError:
        # Expected if sentry-sdk is not installed - return None silently
        return None
    except Exception as e:
        # Log the error but re-raise to prevent silent failures
        logger.error("Failed to capture message to Sentry", error=str(e), exc_info=True)
        raise


def set_user_context(user_id: Optional[str] = None, username: Optional[str] = None, **kwargs) -> None:
    """
    Set user context for Sentry events.
    
    Args:
        user_id: User ID
        username: Username
        **kwargs: Additional user attributes
    """
    try:
        import sentry_sdk
        
        sentry_sdk.set_user({
            "id": user_id,
            "username": username,
            **kwargs,
        })
    except ImportError:
        pass
    except Exception as e:
        logger.error("Failed to set user context in Sentry", error=str(e), exc_info=True)
        # Re-raise to prevent silent failures
        raise


def clear_user_context() -> None:
    """Clear user context from Sentry."""
    try:
        import sentry_sdk
        sentry_sdk.set_user(None)
    except ImportError:
        pass
    except Exception as e:
        logger.error("Failed to clear user context in Sentry", error=str(e), exc_info=True)
        # Re-raise to prevent silent failures
        raise


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Add a breadcrumb to Sentry.
    
    Breadcrumbs help provide context about what happened before an error.
    
    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Severity level (debug, info, warning, error, fatal)
        data: Additional data dictionary
    """
    try:
        import sentry_sdk
        
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {},
        )
    except ImportError:
        pass
    except Exception as e:
        logger.error("Failed to add breadcrumb to Sentry", error=str(e))

