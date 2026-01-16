"""Comprehensive tests for error handling utilities."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.utils.errors import (
    AppError,
    ValidationError as AppValidationError,
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    app_error_handler,
    validation_error_handler,
    general_exception_handler,
)


@pytest.mark.unit
class TestAppError:
    """Tests for AppError base class."""

    def test_app_error_basic(self):
        """Test basic AppError creation."""
        error = AppError("Test error message")
        assert error.message == "Test error message"
        assert error.status_code == 500
        assert error.code == "APP_ERROR"
        assert error.details == {}
        assert str(error) == "Test error message"

    def test_app_error_with_status_code(self):
        """Test AppError with custom status code."""
        error = AppError("Test error", status_code=400)
        assert error.status_code == 400
        assert error.message == "Test error"

    def test_app_error_with_code(self):
        """Test AppError with custom code."""
        error = AppError("Test error", code="CUSTOM_ERROR")
        assert error.code == "CUSTOM_ERROR"

    def test_app_error_with_details(self):
        """Test AppError with details."""
        details = {"field": "value", "error_type": "validation"}
        error = AppError("Test error", details=details)
        assert error.details == details

    def test_app_error_inheritance(self):
        """Test that AppError is an Exception."""
        error = AppError("Test error")
        assert isinstance(error, Exception)


@pytest.mark.unit
class TestValidationError:
    """Tests for ValidationError class."""

    def test_validation_error_basic(self):
        """Test basic ValidationError creation."""
        error = AppValidationError("Validation failed")
        assert error.message == "Validation failed"
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.code == "VALIDATION_ERROR"
        assert error.details == {}

    def test_validation_error_with_details(self):
        """Test ValidationError with details."""
        details = {"field": "email", "reason": "invalid format"}
        error = AppValidationError("Validation failed", details=details)
        assert error.details == details
        assert error.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.unit
class TestNotFoundError:
    """Tests for NotFoundError class."""

    def test_not_found_error_basic(self):
        """Test basic NotFoundError creation."""
        error = NotFoundError("Resource")
        assert error.message == "Resource not found"
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.code == "NOT_FOUND"

    def test_not_found_error_with_identifier(self):
        """Test NotFoundError with identifier."""
        error = NotFoundError("Resource", identifier="123")
        assert error.message == "Resource not found (id: 123)"
        assert error.status_code == status.HTTP_404_NOT_FOUND

    def test_not_found_error_with_none_identifier(self):
        """Test NotFoundError with None identifier."""
        error = NotFoundError("Resource", identifier=None)
        assert error.message == "Resource not found"
        assert error.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.unit
class TestUnauthorizedError:
    """Tests for UnauthorizedError class."""

    def test_unauthorized_error_default(self):
        """Test UnauthorizedError with default message."""
        error = UnauthorizedError()
        assert error.message == "Unauthorized"
        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.code == "UNAUTHORIZED"

    def test_unauthorized_error_custom_message(self):
        """Test UnauthorizedError with custom message."""
        error = UnauthorizedError("Custom unauthorized message")
        assert error.message == "Custom unauthorized message"
        assert error.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
class TestForbiddenError:
    """Tests for ForbiddenError class."""

    def test_forbidden_error_default(self):
        """Test ForbiddenError with default message."""
        error = ForbiddenError()
        assert error.message == "Forbidden"
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.code == "FORBIDDEN"

    def test_forbidden_error_custom_message(self):
        """Test ForbiddenError with custom message."""
        error = ForbiddenError("Custom forbidden message")
        assert error.message == "Custom forbidden message"
        assert error.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.unit
class TestAppErrorHandler:
    """Tests for app_error_handler function."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.query_params = {}
        return request

    @pytest.mark.asyncio
    async def test_app_error_handler_basic(self, mock_request):
        """Test app_error_handler with basic AppError."""
        error = AppError("Test error", status_code=400)
        
        with patch("app.utils.errors.add_breadcrumb") as mock_breadcrumb, \
             patch("app.utils.errors.logger") as mock_logger, \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            mock_settings.alert_on_errors = False
            
            response = await app_error_handler(mock_request, error)
            
            assert response.status_code == 400
            content = response.body.decode()
            assert "APP_ERROR" in content
            assert "Test error" in content
            mock_breadcrumb.assert_called_once()
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_app_error_handler_server_error(self, mock_request):
        """Test app_error_handler with server error (500+)."""
        error = AppError("Server error", status_code=500)
        
        with patch("app.utils.errors.add_breadcrumb") as mock_breadcrumb, \
             patch("app.utils.errors.logger") as mock_logger, \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            mock_settings.alert_on_errors = False
            
            response = await app_error_handler(mock_request, error)
            
            assert response.status_code == 500
            # Should send to Sentry for server errors
            mock_capture.assert_called_once()
            assert mock_capture.call_args[1]["level"] == "error"

    @pytest.mark.asyncio
    async def test_app_error_handler_with_alert_on_errors(self, mock_request):
        """Test app_error_handler with alert_on_errors enabled."""
        error = AppError("Client error", status_code=400)
        
        with patch("app.utils.errors.add_breadcrumb") as mock_breadcrumb, \
             patch("app.utils.errors.logger") as mock_logger, \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            mock_settings.alert_on_errors = True
            
            response = await app_error_handler(mock_request, error)
            
            assert response.status_code == 400
            # Should send to Sentry when alert_on_errors is True
            mock_capture.assert_called_once()
            assert mock_capture.call_args[1]["level"] == "warning"

    @pytest.mark.asyncio
    async def test_app_error_handler_alerts_disabled(self, mock_request):
        """Test app_error_handler with alerts disabled."""
        error = AppError("Test error", status_code=500)
        
        with patch("app.utils.errors.add_breadcrumb") as mock_breadcrumb, \
             patch("app.utils.errors.logger") as mock_logger, \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = False
            
            response = await app_error_handler(mock_request, error)
            
            assert response.status_code == 500
            # Should not send to Sentry when alerts are disabled
            mock_capture.assert_not_called()

    @pytest.mark.asyncio
    async def test_app_error_handler_with_details(self, mock_request):
        """Test app_error_handler with error details."""
        details = {"field": "email", "reason": "invalid"}
        error = AppError("Test error", status_code=400, details=details)
        
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger"), \
             patch("app.utils.errors.capture_exception"), \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = False
            
            response = await app_error_handler(mock_request, error)
            
            content = response.body.decode()
            assert "details" in content
            assert "email" in content

    @pytest.mark.asyncio
    async def test_app_error_handler_with_query_params(self, mock_request):
        """Test app_error_handler includes query params in context."""
        mock_request.query_params = {"param1": "value1", "param2": "value2"}
        error = AppError("Test error", status_code=500)
        
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger"), \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            mock_settings.alert_on_errors = False
            
            await app_error_handler(mock_request, error)
            
            # Verify query params are included in context
            call_kwargs = mock_capture.call_args[1]
            assert "context" in call_kwargs
            assert "param1" in str(call_kwargs["context"])


@pytest.mark.unit
class TestValidationErrorHandler:
    """Tests for validation_error_handler function."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "POST"
        request.query_params = {}
        return request

    @pytest.fixture
    def mock_validation_error(self):
        """Create a mock RequestValidationError."""
        error = MagicMock(spec=RequestValidationError)
        error.errors.return_value = [
            {"loc": ["body", "field"], "msg": "field required", "type": "value_error.missing"}
        ]
        return error

    @pytest.mark.asyncio
    async def test_validation_error_handler_basic(self, mock_request, mock_validation_error):
        """Test validation_error_handler with basic validation error."""
        with patch("app.utils.errors.add_breadcrumb") as mock_breadcrumb, \
             patch("app.utils.errors.logger") as mock_logger, \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = False
            mock_settings.alert_on_warnings = False
            
            response = await validation_error_handler(mock_request, mock_validation_error)
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            content = response.body.decode()
            assert "VALIDATION_ERROR" in content
            assert "Request validation failed" in content
            mock_breadcrumb.assert_called_once()
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_error_handler_with_alert_on_warnings(self, mock_request, mock_validation_error):
        """Test validation_error_handler with alert_on_warnings enabled."""
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger"), \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            mock_settings.alert_on_warnings = True
            
            response = await validation_error_handler(mock_request, mock_validation_error)
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            # Should send to Sentry when alert_on_warnings is True
            mock_capture.assert_called_once()
            assert mock_capture.call_args[1]["level"] == "warning"

    @pytest.mark.asyncio
    async def test_validation_error_handler_alerts_disabled(self, mock_request, mock_validation_error):
        """Test validation_error_handler with alerts disabled."""
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger"), \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = False
            
            response = await validation_error_handler(mock_request, mock_validation_error)
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            # Should not send to Sentry when alerts are disabled
            mock_capture.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_error_handler_includes_errors(self, mock_request, mock_validation_error):
        """Test validation_error_handler includes validation errors in response."""
        error_details = [
            {"loc": ["body", "email"], "msg": "invalid email", "type": "value_error"},
            {"loc": ["body", "age"], "msg": "must be positive", "type": "value_error"},
        ]
        mock_validation_error.errors.return_value = error_details
        
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger"), \
             patch("app.utils.errors.capture_exception"), \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = False
            
            response = await validation_error_handler(mock_request, mock_validation_error)
            
            content = response.body.decode()
            assert "details" in content
            assert "email" in content


@pytest.mark.unit
class TestGeneralExceptionHandler:
    """Tests for general_exception_handler function."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.query_params = {}
        request.url = MagicMock()
        request.url.__str__ = lambda x: "http://test/api/v1/test"
        return request

    @pytest.mark.asyncio
    async def test_general_exception_handler_basic(self, mock_request):
        """Test general_exception_handler with basic exception."""
        exception = ValueError("Unexpected error occurred")
        
        with patch("app.utils.errors.add_breadcrumb") as mock_breadcrumb, \
             patch("app.utils.errors.logger") as mock_logger, \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            
            response = await general_exception_handler(mock_request, exception)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            content = response.body.decode()
            assert "INTERNAL_ERROR" in content
            assert "An unexpected error occurred" in content
            mock_breadcrumb.assert_called_once()
            mock_logger.error.assert_called_once()
            # Should always send unexpected exceptions to Sentry if alerts enabled
            mock_capture.assert_called_once()
            assert mock_capture.call_args[1]["level"] == "error"

    @pytest.mark.asyncio
    async def test_general_exception_handler_alerts_disabled(self, mock_request):
        """Test general_exception_handler with alerts disabled."""
        exception = ValueError("Unexpected error")
        
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger"), \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = False
            
            response = await general_exception_handler(mock_request, exception)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            # Should not send to Sentry when alerts are disabled
            mock_capture.assert_not_called()

    @pytest.mark.asyncio
    async def test_general_exception_handler_different_exception_types(self, mock_request):
        """Test general_exception_handler with different exception types."""
        exception_types = [
            ValueError("Value error"),
            TypeError("Type error"),
            KeyError("Key error"),
            AttributeError("Attribute error"),
        ]
        
        for exc in exception_types:
            with patch("app.utils.errors.add_breadcrumb"), \
                 patch("app.utils.errors.logger"), \
                 patch("app.utils.errors.capture_exception") as mock_capture, \
                 patch("app.utils.errors.settings") as mock_settings:
                mock_settings.enable_alerts = True
                
                response = await general_exception_handler(mock_request, exc)
                
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                # Should capture exception type in tags
                call_kwargs = mock_capture.call_args[1]
                assert "tags" in call_kwargs
                assert "error_type" in call_kwargs["tags"]
                assert call_kwargs["tags"]["error_type"] == type(exc).__name__

    @pytest.mark.asyncio
    async def test_general_exception_handler_includes_context(self, mock_request):
        """Test general_exception_handler includes request context."""
        from collections.abc import Mapping
        mock_query_params = MagicMock(spec=Mapping)
        mock_query_params.__iter__ = lambda x: iter(["param"])
        mock_query_params.__getitem__ = lambda x, k: "value" if k == "param" else None
        mock_query_params.get = lambda k, d=None: "value" if k == "param" else d
        mock_request.query_params = mock_query_params
        exception = ValueError("Unexpected error")
        
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger"), \
             patch("app.utils.errors.capture_exception") as mock_capture, \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            
            await general_exception_handler(mock_request, exception)
            
            # Verify context includes request details
            call_kwargs = mock_capture.call_args[1]
            assert "context" in call_kwargs
            assert "request" in call_kwargs["context"]
            assert call_kwargs["context"]["request"]["path"] == "/api/v1/test"
            assert call_kwargs["context"]["request"]["method"] == "GET"
            # Query params should be converted to dict
            query_params = call_kwargs["context"]["request"]["query_params"]
            assert isinstance(query_params, dict) or "param" in str(query_params)

    @pytest.mark.asyncio
    async def test_general_exception_handler_with_exc_info(self, mock_request):
        """Test general_exception_handler logs with exc_info."""
        exception = ValueError("Unexpected error")
        
        with patch("app.utils.errors.add_breadcrumb"), \
             patch("app.utils.errors.logger") as mock_logger, \
             patch("app.utils.errors.capture_exception"), \
             patch("app.utils.errors.settings") as mock_settings:
            mock_settings.enable_alerts = True
            
            await general_exception_handler(mock_request, exception)
            
            # Verify logger.error was called with exc_info=True
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs.get("exc_info") is True

