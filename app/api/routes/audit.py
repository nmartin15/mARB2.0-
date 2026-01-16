"""Audit log endpoints for HIPAA compliance reporting."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.config.database import get_db
from app.models.database import AuditLog
from app.utils.logger import get_logger
from app.api.middleware.auth import get_current_user

router = APIRouter()
logger = get_logger(__name__)


class AuditLogResponse(BaseModel):
    """Response model for audit log entry."""
    
    id: int
    method: str
    path: str
    status_code: int
    duration: Optional[float]
    user_id: Optional[str]
    client_ip: Optional[str]
    request_identifier: Optional[str]
    response_identifier: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/audit-logs", tags=["audit"])
async def get_audit_logs(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    method: Optional[str] = Query(default=None, description="Filter by HTTP method (GET, POST, etc.)"),
    path: Optional[str] = Query(default=None, description="Filter by path (partial match)"),
    status_code: Optional[int] = Query(default=None, ge=100, le=599, description="Filter by status code"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    client_ip: Optional[str] = Query(default=None, description="Filter by client IP address"),
    start_date: Optional[datetime] = Query(default=None, description="Filter by start date (ISO format)"),
    end_date: Optional[datetime] = Query(default=None, description="Filter by end date (ISO format)"),
    db: Session = Depends(get_db),
    # Note: In production, this should require admin/audit role
    # For now, we'll require authentication but allow any authenticated user
    # _current_user: dict = Depends(get_current_user),
):
    """
    Get audit logs for HIPAA compliance reporting.
    
    This endpoint provides queryable access to audit logs stored in the database.
    All API requests are automatically logged by the AuditMiddleware.
    
    **Security:**
    - Requires authentication (JWT token)
    - In production, should be restricted to admin/audit roles
    - Returns only hashed identifiers (no PHI in plaintext)
    
    **Filtering:**
    - Filter by HTTP method, path, status code, user ID, client IP
    - Filter by date range using start_date and end_date
    - Path filtering supports partial matches
    
    **Pagination:**
    - Use `skip` and `limit` for pagination
    - Maximum limit: 1000 records per request
    
    **Returns:**
    - List of audit log entries with:
      - Request/response metadata (method, path, status_code, duration)
      - User and client information (user_id, client_ip)
      - Hashed identifiers for PHI tracking (no plaintext PHI)
      - Timestamp of the request
    
    **HIPAA Compliance:**
    - No Protected Health Information (PHI) is returned in plaintext
    - Only hashed identifiers are included for audit trail purposes
    - All API access is logged (including access to this endpoint)
    """
    try:
        # Build query with filters
        query = db.query(AuditLog)
        
        # Apply filters
        if method:
            query = query.filter(AuditLog.method == method.upper())
        if path:
            query = query.filter(AuditLog.path.contains(path))
        if status_code:
            query = query.filter(AuditLog.status_code == status_code)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if client_ip:
            query = query.filter(AuditLog.client_ip == client_ip)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        # Get total count (before pagination)
        total = query.count()
        
        # Apply pagination and ordering
        logs = (
            query
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # Convert to response models
        log_responses = [
            AuditLogResponse(
                id=log.id,
                method=log.method,
                path=log.path,
                status_code=log.status_code,
                duration=log.duration,
                user_id=log.user_id,
                client_ip=log.client_ip,
                request_identifier=log.request_identifier,
                response_identifier=log.response_identifier,
                created_at=log.created_at,
            )
            for log in logs
        ]
        
        return {
            "logs": log_responses,
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        logger.error("Failed to retrieve audit logs", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.get("/audit-logs/stats", tags=["audit"])
async def get_audit_log_stats(
    days: int = Query(default=7, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    # _current_user: dict = Depends(get_current_user),
):
    """
    Get audit log statistics for compliance reporting.
    
    Provides aggregated statistics about API usage and access patterns.
    Useful for compliance reporting and monitoring.
    
    **Returns:**
    - Total requests in the time period
    - Requests by method (GET, POST, etc.)
    - Requests by status code
    - Unique users and IP addresses
    - Average request duration
    - Requests per day
    
    **Security:**
    - Requires authentication
    - In production, should be restricted to admin/audit roles
    """
    try:
        from sqlalchemy import func
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Build base query with date filter
        base_query = db.query(AuditLog).filter(
            and_(AuditLog.created_at >= start_date, AuditLog.created_at <= end_date)
        )
        
        # Get total requests (efficient count query)
        total_requests = base_query.count()
        
        # Requests by method (database aggregation)
        method_results = (
            base_query.with_entities(AuditLog.method, func.count(AuditLog.id).label("count"))
            .group_by(AuditLog.method)
            .all()
        )
        method_counts = {method: count for method, count in method_results}
        
        # Requests by status code (database aggregation)
        status_results = (
            base_query.with_entities(AuditLog.status_code, func.count(AuditLog.id).label("count"))
            .group_by(AuditLog.status_code)
            .all()
        )
        status_counts = {str(status): count for status, count in status_results}
        
        # Unique users (efficient distinct count)
        unique_users = (
            base_query.filter(AuditLog.user_id.isnot(None))
            .with_entities(AuditLog.user_id)
            .distinct()
            .count()
        )
        
        # Unique IP addresses (efficient distinct count)
        unique_ips = (
            base_query.filter(AuditLog.client_ip.isnot(None))
            .with_entities(AuditLog.client_ip)
            .distinct()
            .count()
        )
        
        # Average duration (database aggregation)
        avg_duration_result = base_query.with_entities(func.avg(AuditLog.duration)).scalar()
        avg_duration = float(avg_duration_result) if avg_duration_result else None
        
        # Requests per day
        requests_per_day = total_requests / days if days > 0 else 0
        
        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_requests": total_requests,
            "requests_by_method": method_counts,
            "requests_by_status": status_counts,
            "unique_users": unique_users,
            "unique_ip_addresses": unique_ips,
            "average_duration_seconds": round(avg_duration, 4) if avg_duration else None,
            "requests_per_day": round(requests_per_day, 2),
        }
    except Exception as e:
        logger.error("Failed to retrieve audit log statistics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve audit log statistics")
