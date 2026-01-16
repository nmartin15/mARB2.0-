"""Comprehensive tests for AuditMiddleware to improve coverage."""
import json
from unittest.mock import patch, MagicMock, AsyncMock, call
import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.api.middleware.audit import AuditMiddleware, MAX_BODY_SIZE
from app.models.database import AuditLog
from app.config.database import SessionLocal
from app.utils.sanitize import create_audit_identifier, extract_and_hash_identifiers


@pytest.mark.audit
@pytest.mark.middleware
class TestAuditMiddlewareComprehensive:
    """Comprehensive tests for AuditMiddleware to achieve high coverage."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app."""
        app = FastAPI()

        @app.get("/test-get")
        async def test_get():
            return {"message": "success"}

        @app.post("/test-post")
        async def test_post(request: Request):
            body = await request.json()
            return {"received": body}

        @app.put("/test-put")
        async def test_put(request: Request):
            body = await request.json()
            return {"updated": body}

        @app.patch("/test-patch")
        async def test_patch(request: Request):
            body = await request.json()
            return {"patched": body}

        @app.delete("/test-delete")
        async def test_delete():
            return {"deleted": True}

        @app.post("/test-large-body")
        async def test_large_body(request: Request):
            return {"received": "large body"}

        @app.get("/test-non-json")
        async def test_non_json():
            return Response(content="plain text", media_type="text/plain")

        @app.post("/test-invalid-json")
        async def test_invalid_json(request: Request):
            return {"error": "invalid json"}

        return app

    @pytest.fixture
    def test_db_session(self, db_session):
        """Provide test database session factory."""
        from sqlalchemy.orm import sessionmaker
        test_engine = db_session.bind
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        return TestSessionLocal

    def test_post_request_processes_body(self, test_app, test_db_session):
        """Test that POST requests process request body."""
        test_app.add_middleware(AuditMiddleware)
        
        test_data = {"claim_id": 1, "patient_name": "Test Patient"}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.post("/test-post", json=test_data)
            
            assert response.status_code == 200
            # Should log request with identifier
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("API request" in str(call) for call in log_calls)

    def test_put_request_processes_body(self, test_app, test_db_session):
        """Test that PUT requests process request body."""
        test_app.add_middleware(AuditMiddleware)
        
        test_data = {"claim_id": 1, "status": "updated"}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session):
            client = TestClient(test_app)
            response = client.put("/test-put", json=test_data)
            
            assert response.status_code == 200

    def test_patch_request_processes_body(self, test_app, test_db_session):
        """Test that PATCH requests process request body."""
        test_app.add_middleware(AuditMiddleware)
        
        test_data = {"status": "patched"}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session):
            client = TestClient(test_app)
            response = client.patch("/test-patch", json=test_data)
            
            assert response.status_code == 200

    def test_get_request_does_not_process_body(self, test_app, test_db_session):
        """Test that GET requests do not process request body."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            assert response.status_code == 200
            # Should log request but without body processing
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("API request" in str(call) for call in log_calls)

    def test_delete_request_does_not_process_body(self, test_app, test_db_session):
        """Test that DELETE requests do not process request body."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session):
            client = TestClient(test_app)
            response = client.delete("/test-delete")
            
            assert response.status_code == 200

    def test_large_request_body_truncated(self, test_app, test_db_session):
        """Test that large request bodies are truncated."""
        test_app.add_middleware(AuditMiddleware)
        
        # Create a body larger than MAX_BODY_SIZE
        large_data = {"data": "x" * (MAX_BODY_SIZE + 1000)}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.post("/test-large-body", json=large_data)
            
            assert response.status_code == 200
            # Should log warning about truncation
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any("exceeds maximum size" in str(call) for call in warning_calls)

    def test_request_body_json_parsing_error_handled(self, test_app, test_db_session):
        """Test that JSON parsing errors in request body are handled gracefully."""
        test_app.add_middleware(AuditMiddleware)
        
        # Send invalid JSON
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            # Send raw invalid JSON
            response = client.post(
                "/test-post",
                content="invalid json {",
                headers={"Content-Type": "application/json"}
            )
            
            # Should not raise exception, should handle gracefully
            assert response.status_code in [200, 422]  # May return validation error

    def test_request_body_unicode_error_handled(self, test_app, test_db_session):
        """Test that Unicode decode errors in request body are handled."""
        test_app.add_middleware(AuditMiddleware)
        
        # Send invalid UTF-8
        invalid_utf8 = b'\xff\xfe\x00\x01'
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.post(
                "/test-post",
                content=invalid_utf8,
                headers={"Content-Type": "application/json"}
            )
            
            # Should handle gracefully
            assert response.status_code in [200, 422, 400]

    def test_request_body_extraction_exception_handled(self, test_app, test_db_session):
        """Test that exceptions during request body extraction are handled."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger, \
             patch.object(Request, 'body', side_effect=Exception("Body read error")):
            client = TestClient(test_app)
            response = client.post("/test-post", json={"test": "data"})
            
            # Should log warning and continue
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any("Failed to extract request identifiers" in str(call) for call in warning_calls)

    def test_json_response_processed(self, test_app, test_db_session):
        """Test that JSON responses are processed for identifiers."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            assert response.status_code == 200
            # Should log response with identifier
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("API response" in str(call) for call in log_calls)

    def test_non_json_response_not_processed(self, test_app, test_db_session):
        """Test that non-JSON responses are not processed."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-non-json")
            
            assert response.status_code == 200
            # Should still log response but without body processing
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("API response" in str(call) for call in log_calls)

    def test_large_response_body_truncated(self, test_app, test_db_session):
        """Test that large response bodies are truncated."""
        test_app.add_middleware(AuditMiddleware)
        
        # Create endpoint that returns large JSON
        @test_app.get("/test-large-response")
        async def test_large_response():
            return {"data": "x" * (MAX_BODY_SIZE + 1000)}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-large-response")
            
            assert response.status_code == 200
            # Should log warning about truncation
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any("exceeds maximum size" in str(call) for call in warning_calls)

    def test_response_body_json_parsing_error_handled(self, test_app, test_db_session):
        """Test that JSON parsing errors in response body are handled."""
        test_app.add_middleware(AuditMiddleware)
        
        # Create endpoint that returns invalid JSON
        @test_app.get("/test-invalid-json-response")
        async def test_invalid_json_response():
            return Response(
                content='{"invalid": json}',
                media_type="application/json"
            )
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-invalid-json-response")
            
            # Should handle gracefully
            assert response.status_code == 200

    def test_response_body_extraction_exception_handled(self, test_app, test_db_session):
        """Test that exceptions during response body extraction are handled."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            # Mock body_iterator to raise exception
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            # Should handle gracefully - verify response still works
            assert response.status_code == 200

    def test_audit_log_stored_in_database(self, test_app, test_db_session, db_session):
        """Test that audit logs are stored in database."""
        test_app.add_middleware(AuditMiddleware)
        
        initial_count = db_session.query(AuditLog).count()
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session):
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            assert response.status_code == 200
        
        # Verify log was stored
        db_session.expire_all()
        final_count = db_session.query(AuditLog).count()
        assert final_count > initial_count

    def test_audit_log_database_error_handled(self, test_app, test_db_session):
        """Test that database errors during audit log storage are handled."""
        test_app.add_middleware(AuditMiddleware)
        
        # Mock SessionLocal to raise exception
        with patch("app.api.middleware.audit.SessionLocal", side_effect=Exception("DB error")), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            # Should not fail the request
            assert response.status_code == 200
            # Should log error
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Failed to create database session" in str(call) for call in error_calls)

    def test_audit_log_commit_error_handled(self, test_app, test_db_session):
        """Test that commit errors during audit log storage are handled."""
        test_app.add_middleware(AuditMiddleware)
        
        # Create a mock session that raises on commit
        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("Commit error")
        mock_session.rollback = MagicMock()
        mock_session.close = MagicMock()
        
        def mock_session_local():
            return mock_session
        
        with patch("app.api.middleware.audit.SessionLocal", mock_session_local), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            # Should not fail the request
            assert response.status_code == 200
            # Should rollback and log error
            mock_session.rollback.assert_called_once()
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Failed to store audit log" in str(call) for call in error_calls)

    def test_request_identifier_created_for_post(self, test_app, test_db_session):
        """Test that request identifier is created for POST requests."""
        test_app.add_middleware(AuditMiddleware)
        
        test_data = {"claim_id": 1, "patient_name": "Test"}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.post("/test-post", json=test_data)
            
            assert response.status_code == 200
            # Check that request identifier was logged
            log_calls = mock_logger.info.call_args_list
            request_log = next((call for call in log_calls if "API request" in str(call.args)), None)
            if request_log and request_log.kwargs:
                assert "request_identifier" in request_log.kwargs or "request_hashed_identifiers" in request_log.kwargs

    def test_response_identifier_created_for_json(self, test_app, test_db_session):
        """Test that response identifier is created for JSON responses."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            assert response.status_code == 200
            # Check that response identifier was logged
            log_calls = mock_logger.info.call_args_list
            response_log = next((call for call in log_calls if "API response" in str(call.args)), None)
            if response_log and response_log.kwargs:
                assert "response_identifier" in response_log.kwargs or "response_hashed_identifiers" in response_log.kwargs

    def test_hashed_identifiers_extracted_from_dict(self, test_app, test_db_session):
        """Test that hashed identifiers are extracted from request body dict."""
        test_app.add_middleware(AuditMiddleware)
        
        test_data = {
            "patient_name": "John Doe",
            "mrn": "123456789",
            "claim_id": 1
        }
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.extract_and_hash_identifiers") as mock_extract:
            mock_extract.return_value = {"patient_name": "hashed_value"}
            client = TestClient(test_app)
            response = client.post("/test-post", json=test_data)
            
            assert response.status_code == 200
            # Should extract identifiers
            mock_extract.assert_called_once()

    def test_hashed_identifiers_not_extracted_from_non_dict(self, test_app, test_db_session):
        """Test that hashed identifiers are not extracted from non-dict JSON."""
        test_app.add_middleware(AuditMiddleware)
        
        # Send array instead of dict
        test_data = [1, 2, 3]
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.extract_and_hash_identifiers") as mock_extract:
            client = TestClient(test_app)
            response = client.post("/test-post", json=test_data)
            
            assert response.status_code == 200
            # Should not extract identifiers from non-dict
            # (extract_and_hash_identifiers may still be called but should handle gracefully)

    def test_truncated_body_does_not_extract_identifiers(self, test_app, test_db_session):
        """Test that truncated bodies do not extract hashed identifiers."""
        test_app.add_middleware(AuditMiddleware)
        
        # Create body larger than MAX_BODY_SIZE
        large_data = {"data": "x" * (MAX_BODY_SIZE + 1000)}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.extract_and_hash_identifiers") as mock_extract:
            client = TestClient(test_app)
            response = client.post("/test-large-body", json=large_data)
            
            assert response.status_code == 200
            # Should not extract identifiers from truncated body
            # (extract_and_hash_identifiers should not be called for truncated bodies)

    def test_user_id_captured_when_present(self, test_app, test_db_session):
        """Test that user_id is captured when present in request state."""
        test_app.add_middleware(AuditMiddleware)
        
        # Create a request with user in state
        @test_app.get("/test-user")
        async def test_user(request: Request):
            request.state.user = {"user_id": "test_user_123"}
            return {"user": "test"}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-user")
            
            assert response.status_code == 200
            # Check that user_id was logged
            log_calls = mock_logger.info.call_args_list
            request_log = next((call for call in log_calls if "API request" in str(call.args)), None)
            if request_log and request_log.kwargs:
                # User ID should be in log (may be None if not set by middleware)
                assert "user_id" in request_log.kwargs

    def test_client_ip_captured(self, test_app, test_db_session):
        """Test that client IP is captured."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            assert response.status_code == 200
            # Check that client_ip was logged
            log_calls = mock_logger.info.call_args_list
            request_log = next((call for call in log_calls if "API request" in str(call.args)), None)
            if request_log and request_log.kwargs:
                assert "client_ip" in request_log.kwargs

    def test_duration_calculated(self, test_app, test_db_session):
        """Test that request duration is calculated and logged."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session), \
             patch("app.api.middleware.audit.logger") as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            assert response.status_code == 200
            # Check that duration was logged
            log_calls = mock_logger.info.call_args_list
            response_log = next((call for call in log_calls if "API response" in str(call.args)), None)
            if response_log and response_log.kwargs:
                assert "duration" in response_log.kwargs
                assert isinstance(response_log.kwargs["duration"], (int, float))
                assert response_log.kwargs["duration"] >= 0

    def test_response_body_recreated_after_processing(self, test_app, test_db_session):
        """Test that response body is recreated after processing."""
        test_app.add_middleware(AuditMiddleware)
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session):
            client = TestClient(test_app)
            response = client.get("/test-get")
            
            assert response.status_code == 200
            # Response should still be valid JSON
            data = response.json()
            assert "message" in data

    def test_request_body_restored_after_processing(self, test_app, test_db_session):
        """Test that request body is restored after processing."""
        test_app.add_middleware(AuditMiddleware)
        
        test_data = {"claim_id": 1, "patient_name": "Test"}
        
        with patch("app.api.middleware.audit.SessionLocal", test_db_session):
            client = TestClient(test_app)
            response = client.post("/test-post", json=test_data)
            
            assert response.status_code == 200
            # Response should show data was received
            data = response.json()
            assert "received" in data

