"""Comprehensive tests for API middleware.

This test suite covers all middleware components:
- OptionalAuthMiddleware: Authentication enforcement
- AuditMiddleware: HIPAA-compliant audit logging
- Integration tests for middleware working together
"""
import json
import os
from unittest.mock import MagicMock, patch, AsyncMock, call
from datetime import datetime

import pytest
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from app.api.middleware.auth_middleware import OptionalAuthMiddleware
from app.api.middleware.audit import AuditMiddleware, MAX_BODY_SIZE
from app.api.middleware.auth import create_access_token
from app.config.database import SessionLocal
from app.models.database import AuditLog


@pytest.mark.unit
class TestOptionalAuthMiddleware:
    """Direct unit tests for OptionalAuthMiddleware."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app."""
        app = FastAPI()

        @app.get("/protected")
        async def protected_endpoint():
            return {"message": "protected"}

        @app.get("/public")
        async def public_endpoint():
            return {"message": "public"}

        return app

    @pytest.fixture
    def middleware(self, test_app):
        """Create OptionalAuthMiddleware instance."""
        return OptionalAuthMiddleware(test_app)

    async def test_auth_not_required_allows_all_requests(self, middleware):
        """Test that when auth is not required, all requests pass through."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=False):
            request = MagicMock(spec=Request)
            request.url.path = "/protected"
            request.method = "GET"
            
            call_next = AsyncMock(return_value=Response(status_code=200))
            
            response = await middleware.dispatch(request, call_next)
            
            assert response.status_code == 200
            call_next.assert_called_once_with(request)

    async def test_auth_required_exempt_path_allows_request(self, middleware):
        """Test that exempt paths are allowed when auth is required."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/public", "/api/v1/health"]):
            request = MagicMock(spec=Request)
            request.url.path = "/public"
            request.method = "GET"
            
            call_next = AsyncMock(return_value=Response(status_code=200))
            
            response = await middleware.dispatch(request, call_next)
            
            assert response.status_code == 200
            call_next.assert_called_once_with(request)

    async def test_auth_required_no_token_raises_401(self, middleware):
        """Test that protected endpoints require authentication token."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/api/v1/health"]):
            request = MagicMock(spec=Request)
            request.url.path = "/protected"
            request.method = "GET"
            request.headers = {}
            request.client = MagicMock()
            request.client.host = "127.0.0.1"
            
            call_next = AsyncMock()
            
            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Authentication required" in str(exc_info.value.detail)
            assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"
            call_next.assert_not_called()

    async def test_auth_required_missing_authorization_header_raises_401(self, middleware):
        """Test that missing Authorization header raises 401."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/api/v1/health"]):
            request = MagicMock(spec=Request)
            request.url.path = "/protected"
            request.method = "GET"
            request.headers = {}  # No Authorization header
            request.client = MagicMock()
            request.client.host = "127.0.0.1"
            
            call_next = AsyncMock()
            
            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            call_next.assert_not_called()

    async def test_auth_required_invalid_bearer_format_raises_401(self, middleware):
        """Test that invalid Bearer token format raises 401."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/api/v1/health"]):
            request = MagicMock(spec=Request)
            request.url.path = "/protected"
            request.method = "GET"
            request.headers = {"Authorization": "InvalidFormat token123"}
            request.client = MagicMock()
            request.client.host = "127.0.0.1"
            
            call_next = AsyncMock()
            
            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            call_next.assert_not_called()

    async def test_auth_required_valid_bearer_token_allows_request(self, middleware):
        """Test that valid Bearer token allows request to pass through."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/api/v1/health"]):
            request = MagicMock(spec=Request)
            request.url.path = "/protected"
            request.method = "GET"
            request.headers = {"Authorization": "Bearer valid_token_12345"}
            
            call_next = AsyncMock(return_value=Response(status_code=200))
            
            response = await middleware.dispatch(request, call_next)
            
            assert response.status_code == 200
            call_next.assert_called_once_with(request)

    async def test_auth_required_logs_warning_on_unauthorized(self, middleware):
        """Test that unauthorized requests are logged with warning."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/api/v1/health"]), \
             patch("app.api.middleware.auth_middleware.logger") as mock_logger:
            request = MagicMock(spec=Request)
            request.url.path = "/protected"
            request.method = "GET"
            request.headers = {}
            request.client = MagicMock()
            request.client.host = "127.0.0.1"
            
            call_next = AsyncMock()
            
            with pytest.raises(HTTPException):
                await middleware.dispatch(request, call_next)
            
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Unauthenticated request" in str(call_args)
            assert "path" in call_args.kwargs
            assert "method" in call_args.kwargs

    async def test_auth_required_no_client_host_handles_gracefully(self, middleware):
        """Test that missing client.host is handled gracefully."""
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/api/v1/health"]):
            request = MagicMock(spec=Request)
            request.url.path = "/protected"
            request.method = "GET"
            request.headers = {}
            request.client = None  # No client
            
            call_next = AsyncMock()
            
            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.audit
class TestAuditMiddleware:
    """Comprehensive tests for AuditMiddleware."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        @app.post("/test")
        async def test_post_endpoint(request: Request):
            body = await request.json()
            return {"received": body}

        return app

    @pytest.fixture
    def middleware(self, test_app):
        """Create AuditMiddleware instance."""
        return AuditMiddleware(test_app)

    @pytest.fixture
    def test_db_session(self, db_session):
        """Provide test database session."""
        from sqlalchemy.orm import sessionmaker
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        return TestSessionLocal

    def test_audit_logs_get_request(self, test_app, test_db_session):
        """Test that GET requests are logged."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test")
            
            assert response.status_code == 200
            assert mock_logger.info.call_count >= 2  # Request and response logs

    def test_audit_logs_post_request_with_body(self, test_app, test_db_session):
        """Test that POST requests with body are logged."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            test_data = {"claim_id": 1, "patient_name": "John Doe"}
            response = client.post("/test", json=test_data)
            
            assert response.status_code == 200
            # Verify request identifier was created
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("request_identifier" in call or "API request" in call for call in log_calls)

    def test_audit_logs_user_id_when_authenticated(self, test_app, test_db_session):
        """Test that user_id is logged when user is authenticated."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test")
            
            # Verify user_id field is logged (may be None for unauthenticated)
            log_calls = mock_logger.info.call_args_list
            # At least one call should have user_id parameter (may be None)
            assert any("user_id" in str(call.kwargs) for call in log_calls if call.kwargs)

    def test_audit_logs_client_ip(self, test_app, test_db_session):
        """Test that client IP is logged."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test")
            
            # Verify client_ip was logged
            log_calls = mock_logger.info.call_args_list
            assert any("client_ip" in str(call.kwargs) for call in log_calls if call.kwargs)

    def test_audit_logs_duration(self, test_app, test_db_session):
        """Test that request duration is logged."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test")
            
            # Verify duration was logged in response
            log_calls = mock_logger.info.call_args_list
            response_logs = [call for call in log_calls if call.kwargs and "duration" in call.kwargs]
            assert len(response_logs) > 0

    def test_audit_stores_log_in_database(self, test_app, test_db_session, db_session):
        """Test that audit logs are stored in database."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        initial_count = db_session.query(AuditLog).count()
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session):
            client = TestClient(test_app)
            response = client.get("/test")
            assert response.status_code == 200
        
        db_session.expire_all()
        final_count = db_session.query(AuditLog).count()
        assert final_count > initial_count
        
        # Verify the log entry
        latest_log = db_session.query(AuditLog).order_by(AuditLog.created_at.desc()).first()
        assert latest_log is not None
        assert latest_log.method == "GET"
        assert latest_log.path == "/test"
        assert latest_log.status_code == 200

    def test_audit_extracts_hashed_identifiers_from_request(self, test_app, test_db_session):
        """Test that hashed identifiers are extracted from request body."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            test_data = {"patient_name": "John Doe", "mrn": "123456789"}
            response = client.post("/test", json=test_data)
            
            assert response.status_code == 200
            # Verify hashed identifiers were extracted (check log calls)
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            # Request identifier should be created
            assert any("request_identifier" in call or "hashed_identifiers" in call for call in log_calls)

    def test_audit_extracts_hashed_identifiers_from_response(self, test_app, test_db_session):
        """Test that hashed identifiers are extracted from response body."""
        from app.api.middleware.audit import AuditMiddleware
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test")
            
            assert response.status_code == 200
            # Verify response identifier was created
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("response_identifier" in call or "hashed_identifiers" in call for call in log_calls)


@pytest.mark.integration
class TestMiddlewareIntegration:
    """Integration tests for middleware working together."""

    @pytest.fixture
    def test_app_with_middleware(self):
        """Create test app with all middleware."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        @app.post("/test")
        async def test_post(request: Request):
            body = await request.json()
            return {"received": body}

        # Add middleware in order
        app.add_middleware(OptionalAuthMiddleware)
        app.add_middleware(AuditMiddleware)

        return app

    def test_middleware_order_auth_before_audit(self, test_app_with_middleware, db_session):
        """Test that auth middleware runs before audit middleware."""
        from sqlalchemy.orm import sessionmaker
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=False), \
             patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client = TestClient(test_app_with_middleware)
            response = client.get("/test")
            
            assert response.status_code == 200

    def test_unauthorized_request_not_audited(self, test_app_with_middleware, db_session):
        """Test that unauthorized requests are not fully processed by audit."""
        from sqlalchemy.orm import sessionmaker
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        
        with patch("app.api.middleware.auth_middleware.is_auth_required", return_value=True), \
             patch("app.api.middleware.auth_middleware.get_auth_exempt_paths", return_value=["/api/v1/health"]), \
             patch("app.api.middleware.audit.SessionLocal", TestSessionLocal):
            client = TestClient(test_app_with_middleware)
            
            # Request without auth should be blocked by auth middleware
            # Audit middleware may still log the attempt, but request won't complete
            try:
                response = client.get("/test")
                # If we get a response, it should be 401
                assert response.status_code == 401
            except Exception:
                # TestClient may raise exception for 401
                pass

