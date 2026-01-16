"""HIPAA-compliant audit logging middleware."""
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import json

from app.models.database import AuditLog
from app.config.database import SessionLocal
from app.utils.logger import get_logger
from app.utils.sanitize import create_audit_identifier, extract_and_hash_identifiers

logger = get_logger(__name__)

# Maximum body size to process (1MB) - larger bodies are truncated
MAX_BODY_SIZE = 1024 * 1024  # 1MB


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for HIPAA audit logging.
    
    This middleware logs all API requests and responses for audit purposes.
    To maintain HIPAA compliance, request and response bodies are NOT logged
    in plain text as they may contain Protected Health Information (PHI).
    
    Instead, this middleware:
    - Extracts PHI identifiers from request/response bodies
    - Creates deterministic hashes of these identifiers
    - Logs the hashed identifiers for audit trail purposes
    - Allows tracking unique requests/entities without exposing PHI
    
    The hashed identifiers are:
    - One-way (cannot be reversed to reveal PHI)
    - Deterministic (same PHI = same hash, allowing record matching)
    - Salted (prevents rainbow table attacks)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log all PHI access with hashed identifiers.
        
        Creates unique, non-reversible identifiers from request/response bodies
        to enable audit trails while maintaining HIPAA compliance.
        """
        start_time = datetime.now()
        
        # Get user info if available
        user_id = None
        if hasattr(request.state, "user"):
            user_id = request.state.user.get("user_id")
        
        # Extract and hash identifiers from request body
        request_identifier: Optional[str] = None
        request_hashed_identifiers: dict = {}
        
        # Skip body processing for multipart/form-data (file uploads)
        # FastAPI needs the raw body stream for multipart parsing
        content_type = request.headers.get("content-type", "").lower()
        is_multipart = "multipart/form-data" in content_type
        
        if request.method in ("POST", "PUT", "PATCH") and not is_multipart:
            try:
                # Read request body
                body = await request.body()
                
                # Truncate body if too large to prevent PHI exposure and memory issues
                body_size = len(body)
                body_truncated = False
                if body_size > MAX_BODY_SIZE:
                    logger.warning(
                        "Request body exceeds maximum size, truncating",
                        body_size=body_size,
                        max_size=MAX_BODY_SIZE,
                        path=request.url.path,
                    )
                    body = body[:MAX_BODY_SIZE]
                    body_truncated = True
                
                # Create unique identifier from truncated body
                request_identifier = create_audit_identifier(body)
                
                # Extract hashed PHI identifiers for detailed audit trail
                # Only process if body is small enough to safely parse (not truncated)
                if not body_truncated:
                    try:
                        body_dict = json.loads(body.decode("utf-8"))
                        if isinstance(body_dict, dict):
                            request_hashed_identifiers = extract_and_hash_identifiers(body_dict)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                
                # Restore body for downstream processing
                # FastAPI/Starlette allows re-reading the body if we store it
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception as e:
                logger.warning("Failed to extract request identifiers", error=str(e))
        elif is_multipart:
            # For multipart uploads, create identifier from headers only
            # This avoids breaking the multipart stream
            request_identifier = create_audit_identifier(
                f"{request.method}:{request.url.path}".encode()
            )
        
        # Log request with hashed identifiers
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "user_id": user_id,
            "client_ip": request.client.host if request.client else None,
        }
        
        if request_identifier:
            log_data["request_identifier"] = request_identifier
        if request_hashed_identifiers:
            log_data["request_hashed_identifiers"] = request_hashed_identifiers
        
        logger.info("API request", **log_data)
        
        # Process request
        response = await call_next(request)
        
        # Extract and hash identifiers from response body
        # Note: We only process response bodies for JSON responses to avoid
        # issues with streaming responses or binary data
        response_identifier: Optional[str] = None
        response_hashed_identifiers: dict = {}
        
        # Only process JSON responses (check content-type)
        content_type = response.headers.get("content-type", "").lower()
        is_json_response = "application/json" in content_type
        
        if is_json_response:
            try:
                # Read response body
                response_body = b""
                response_truncated = False
                async for chunk in response.body_iterator:
                    response_body += chunk
                    # Stop reading if body exceeds maximum size
                    if len(response_body) > MAX_BODY_SIZE:
                        logger.warning(
                            "Response body exceeds maximum size, truncating",
                            body_size=len(response_body),
                            max_size=MAX_BODY_SIZE,
                            path=request.url.path,
                        )
                        response_body = response_body[:MAX_BODY_SIZE]
                        response_truncated = True
                        break
                
                # Create unique identifier from truncated body
                response_identifier = create_audit_identifier(response_body)
                
                # Extract hashed PHI identifiers
                # Only process if body is small enough to safely parse (not truncated)
                if not response_truncated:
                    try:
                        body_dict = json.loads(response_body.decode("utf-8"))
                        if isinstance(body_dict, dict):
                            response_hashed_identifiers = extract_and_hash_identifiers(body_dict)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                
                # Recreate response with body for downstream processing
                from starlette.responses import Response as StarletteResponse
                response = StarletteResponse(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            except Exception as e:
                logger.warning("Failed to extract response identifiers", error=str(e))
        
        # Log response with hashed identifiers
        duration = (datetime.now() - start_time).total_seconds()
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration": duration,
            "user_id": user_id,
        }
        
        if response_identifier:
            log_data["response_identifier"] = response_identifier
        if response_hashed_identifiers:
            log_data["response_hashed_identifiers"] = response_hashed_identifiers
        
        logger.info("API response", **log_data)
        
        # Store audit log in database for HIPAA compliance
        # This provides queryable audit trail for compliance reporting
        # Note: We do NOT store raw request/response bodies (HIPAA compliance)
        # Only hashed identifiers are stored to maintain privacy
        try:
            db = SessionLocal()
            try:
                audit_log = AuditLog(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration=duration,
                    user_id=str(user_id) if user_id else None,
                    client_ip=request.client.host if request.client else None,
                    request_identifier=request_identifier,
                    response_identifier=response_identifier,
                    request_hashed_identifiers=request_hashed_identifiers if request_hashed_identifiers else None,
                    response_hashed_identifiers=response_hashed_identifiers if response_hashed_identifiers else None,
                )
                db.add(audit_log)
                db.commit()
            except Exception as e:
                logger.error(
                    "Failed to store audit log in database",
                    error=str(e),
                    method=request.method,
                    path=request.url.path,
                )
                db.rollback()
            finally:
                db.close()
        except Exception as e:
            # Log error but don't fail the request if audit logging fails
            logger.error(
                "Failed to create database session for audit log",
                error=str(e),
                method=request.method,
                path=request.url.path,
            )
        
        return response

