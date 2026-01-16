"""Tests for audit log API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.models.database import AuditLog
from app.main import app


@pytest.mark.security
@pytest.mark.audit
@pytest.mark.hipaa
class TestAuditLogAPI:
    """Test audit log API endpoints."""

    def test_get_audit_logs_returns_paginated_results(self, client, db_session):
        """Test that audit log endpoint returns paginated results."""
        from app.config.database import SessionLocal
        
        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        # Create some audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")
            client.get("/api/v1/claims")
            client.get("/api/v1/remits")
        
        # Query audit logs via API
        response = client.get("/api/v1/audit-logs?skip=0&limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert isinstance(data["logs"], list)
        assert len(data["logs"]) <= 10

    def test_get_audit_logs_filters_by_method(self, client, db_session):
        """Test filtering audit logs by HTTP method."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker
        
        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        # Create audit logs with different methods
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")
            client.post("/api/v1/claims", json={"test": "data"})
        
        # Filter by GET method
        response = client.get("/api/v1/audit-logs?method=GET")
        
        assert response.status_code == 200
        data = response.json()
        assert all(log["method"] == "GET" for log in data["logs"])

    def test_get_audit_logs_filters_by_path(self, client, db_session):
        """Test filtering audit logs by path."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker
        
        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        # Create audit logs with different paths
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")
            client.get("/api/v1/claims")
        
        # Filter by path
        response = client.get("/api/v1/audit-logs?path=/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert all("/api/v1/health" in log["path"] for log in data["logs"])

    def test_get_audit_logs_filters_by_status_code(self, client, db_session):
        """Test filtering audit logs by status code."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker
        
        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        # Create audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")  # Should return 200
            client.get("/api/v1/nonexistent")  # Should return 404
        
        # Filter by status code 200
        response = client.get("/api/v1/audit-logs?status_code=200")
        
        assert response.status_code == 200
        data = response.json()
        assert all(log["status_code"] == 200 for log in data["logs"])

    def test_get_audit_log_stats_returns_statistics(self, client, db_session):
        """Test that audit log statistics endpoint returns aggregated data."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker
        
        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        # Create some audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")
            client.get("/api/v1/claims")
            client.post("/api/v1/claims", json={"test": "data"})
        
        # Get statistics
        response = client.get("/api/v1/audit-logs/stats?days=7")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "requests_by_method" in data
        assert "requests_by_status" in data
        assert "unique_users" in data
        assert "unique_ip_addresses" in data
        assert "period_days" in data
        assert data["period_days"] == 7
        assert data["total_requests"] >= 3

    def test_audit_log_response_includes_required_fields(self, client, db_session):
        """Test that audit log response includes all required fields."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker
        
        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        # Create an audit log
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")
        
        # Get audit logs
        response = client.get("/api/v1/audit-logs?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) > 0
        
        log = data["logs"][0]
        required_fields = [
            "id", "method", "path", "status_code", "duration",
            "user_id", "client_ip", "request_identifier", "response_identifier", "created_at"
        ]
        for field in required_fields:
            assert field in log, f"Missing required field: {field}"

    def test_get_audit_logs_filters_by_user_id(self, client, db_session):
        """Test filtering audit logs by user ID."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker

        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        # Create audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")

        # Filter by user_id (may be None in test environment)
        response = client.get("/api/v1/audit-logs?user_id=test_user")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data

    def test_get_audit_logs_filters_by_client_ip(self, client, db_session):
        """Test filtering audit logs by client IP."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker

        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        # Create audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")

        # Filter by client IP
        response = client.get("/api/v1/audit-logs?client_ip=127.0.0.1")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_get_audit_logs_filters_by_date_range(self, client, db_session):
        """Test filtering audit logs by date range."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker
        from datetime import datetime, timedelta

        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        # Create audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")

        # Filter by date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)
        response = client.get(
            f"/api/v1/audit-logs?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_get_audit_logs_multiple_filters(self, client, db_session):
        """Test filtering audit logs with multiple filters."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker

        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        # Create audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")
            client.get("/api/v1/claims")

        # Filter by multiple criteria
        response = client.get("/api/v1/audit-logs?method=GET&status_code=200&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert all(log["method"] == "GET" for log in data["logs"])
        assert all(log["status_code"] == 200 for log in data["logs"])

    def test_get_audit_logs_pagination(self, client, db_session):
        """Test pagination for audit logs."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker

        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        # Create multiple audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            for _ in range(5):
                client.get("/api/v1/health")

        # Test pagination
        response = client.get("/api/v1/audit-logs?skip=0&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) <= 2
        assert data["skip"] == 0
        assert data["limit"] == 2

    def test_get_audit_logs_max_limit(self, client, db_session):
        """Test that limit parameter respects maximum (1000)."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker

        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        # Create audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")

        # Test with limit > 1000 (should return 422 or cap at 1000)
        response = client.get("/api/v1/audit-logs?limit=2000")

        # Should either accept (capped) or return 422
        assert response.status_code in [200, 422]

    def test_get_audit_log_stats_different_periods(self, client, db_session):
        """Test audit log statistics with different time periods."""
        from app.config.database import SessionLocal
        from sqlalchemy.orm import sessionmaker

        # Patch SessionLocal to use the test database session
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        # Create audit logs
        with patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client.get("/api/v1/health")
            client.get("/api/v1/claims")

        # Test with different periods
        for days in [1, 7, 30, 90]:
            response = client.get(f"/api/v1/audit-logs/stats?days={days}")

            assert response.status_code == 200
            data = response.json()
            assert data["period_days"] == days
            assert "total_requests" in data
            assert "requests_by_method" in data
            assert "requests_by_status" in data

    def test_get_audit_log_stats_invalid_days(self, client, db_session):
        """Test audit log statistics with invalid days parameter."""
        # Test with days > 365 (max)
        response = client.get("/api/v1/audit-logs/stats?days=500")
        assert response.status_code == 422

        # Test with days < 1 (min)
        response = client.get("/api/v1/audit-logs/stats?days=0")
        assert response.status_code == 422

    def test_get_audit_logs_invalid_skip(self, client, db_session):
        """Test audit logs endpoint with invalid skip parameter."""
        response = client.get("/api/v1/audit-logs?skip=-1")
        # Should return 422 for negative skip
        assert response.status_code == 422

    def test_get_audit_logs_invalid_limit(self, client, db_session):
        """Test audit logs endpoint with invalid limit parameter."""
        response = client.get("/api/v1/audit-logs?limit=0")
        # Should return 422 for limit < 1
        assert response.status_code == 422

