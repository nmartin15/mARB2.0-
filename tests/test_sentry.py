"""Tests for Sentry configuration - Fixed version."""
import os
from unittest.mock import MagicMock, patch
import pytest

from app.config.sentry import (
    SentrySettings,
    init_sentry,
    filter_sensitive_data,
    capture_exception,
    capture_message,
    set_user_context,
    clear_user_context,
    add_breadcrumb,
)


def create_mock_sentry_sdk():
    """Helper to create a mock sentry_sdk module."""
    mock_sdk = MagicMock()
    mock_scope = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_scope)
    mock_context_manager.__exit__ = MagicMock(return_value=None)
    mock_sdk.push_scope.return_value = mock_context_manager
    mock_sdk.capture_exception.return_value = "event-id-123"
    mock_sdk.capture_message.return_value = "event-id-123"
    mock_sdk.set_user = MagicMock()
    mock_sdk.add_breadcrumb = MagicMock()
    return mock_sdk, mock_scope


@pytest.mark.unit
class TestSentrySettings:
    """Tests for SentrySettings class."""

    def test_sentry_settings_defaults(self):
        """Test SentrySettings with default values."""
        # Note: Settings may read from .env file, so we test with cleared env
        with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            settings = SentrySettings()
            # DSN may be None or empty string depending on .env
            assert settings.dsn is None or settings.dsn == ""
            assert settings.environment == "development"
            assert settings.traces_sample_rate == 0.1
            assert settings.profiles_sample_rate == 0.1
            assert settings.send_default_pii is False
            assert settings.enable_alerts is True
            assert settings.alert_on_errors is True
            assert settings.alert_on_warnings is False
            assert settings.enable_tracing is True
            assert settings.enable_profiling is False

    def test_sentry_settings_from_env(self):
        """Test SentrySettings reading from environment variables."""
        env_vars = {
            "SENTRY_DSN": "https://test@sentry.io/123",
            "SENTRY_ENVIRONMENT": "production",
            "SENTRY_RELEASE": "v1.0.0",
            "SENTRY_TRACES_SAMPLE_RATE": "0.5",
            "SENTRY_PROFILES_SAMPLE_RATE": "0.2",
            "SENTRY_SEND_DEFAULT_PII": "true",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            settings = SentrySettings()
            assert settings.dsn == "https://test@sentry.io/123"
            assert settings.environment == "production"
            assert settings.release == "v1.0.0"
            assert settings.traces_sample_rate == 0.5
            assert settings.profiles_sample_rate == 0.2
            assert settings.send_default_pii is True


@pytest.mark.unit
class TestInitSentry:
    """Tests for init_sentry function."""

    def test_init_sentry_no_dsn(self):
        """Test init_sentry when DSN is not configured."""
        with patch("app.config.sentry.settings") as mock_settings:
            mock_settings.dsn = None
            # Should not raise and should log info
            init_sentry()

    def test_init_sentry_import_error(self):
        """Test init_sentry when sentry_sdk is not installed."""
        with patch("app.config.sentry.settings") as mock_settings:
            mock_settings.dsn = "https://test@sentry.io/123"

            with patch("builtins.__import__", side_effect=ImportError("No module named 'sentry_sdk'")):
                # Should not raise, should log warning
                init_sentry()


@pytest.mark.unit
class TestFilterSensitiveData:
    """Tests for filter_sensitive_data function."""

    def test_filter_sensitive_data_removes_headers(self):
        """Test that filter_sensitive_data removes sensitive headers."""
        event = {
            "request": {
                "headers": {
                    "authorization": "Bearer token123",
                    "cookie": "session=abc",
                    "x-api-key": "secret-key",
                    "x-auth-token": "auth-token",
                    "x-access-token": "access-token",
                    "content-type": "application/json",
                }
            }
        }

        result = filter_sensitive_data(event, {})

        assert "authorization" not in result["request"]["headers"]
        assert "cookie" not in result["request"]["headers"]
        assert "x-api-key" not in result["request"]["headers"]
        assert "x-auth-token" not in result["request"]["headers"]
        assert "x-access-token" not in result["request"]["headers"]
        assert "content-type" in result["request"]["headers"]

    def test_filter_sensitive_data_sanitizes_user(self):
        """Test that filter_sensitive_data sanitizes user context."""
        event = {
            "user": {
                "id": "user123",
                "username": "testuser",
                "email": "test@example.com",
                "password": "secret",
                "ssn": "123-45-6789",
            }
        }

        result = filter_sensitive_data(event, {})

        assert result["user"]["id"] == "user123"
        assert result["user"]["username"] == "testuser"
        assert "email" not in result["user"]
        assert "password" not in result["user"]
        assert "ssn" not in result["user"]

    def test_filter_sensitive_data_removes_extra_keys(self):
        """Test that filter_sensitive_data removes sensitive keys from extra."""
        event = {
            "extra": {
                "password": "secret",
                "token": "abc123",
                "secret": "my-secret",
                "key": "api-key",
                "ssn": "123-45-6789",
                "credit_card": "4111-1111-1111-1111",
                "phi": "protected health info",
                "safe_data": "this is safe",
            }
        }

        result = filter_sensitive_data(event, {})

        assert "password" not in result["extra"]
        assert "token" not in result["extra"]
        assert "secret" not in result["extra"]
        assert "key" not in result["extra"]
        assert "ssn" not in result["extra"]
        assert "credit_card" not in result["extra"]
        assert "phi" not in result["extra"]
        assert "safe_data" in result["extra"]

    def test_filter_sensitive_data_no_request(self):
        """Test filter_sensitive_data when event has no request."""
        event = {"message": "test error"}

        result = filter_sensitive_data(event, {})

        assert result == event

    def test_filter_sensitive_data_no_user(self):
        """Test filter_sensitive_data when event has no user."""
        event = {"request": {"headers": {}}}

        result = filter_sensitive_data(event, {})

        assert result == event

    def test_filter_sensitive_data_no_extra(self):
        """Test filter_sensitive_data when event has no extra."""
        event = {"message": "test error"}

        result = filter_sensitive_data(event, {})

        assert result == event


@pytest.mark.unit
class TestCaptureException:
    """Tests for capture_exception function."""

    def test_capture_exception_with_sentry(self):
        """Test capture_exception when Sentry is available."""
        mock_sdk, mock_scope = create_mock_sentry_sdk()
        exception = ValueError("Test error")

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = capture_exception(exception)

            assert result == "event-id-123"
            mock_sdk.capture_exception.assert_called_once_with(exception)

    def test_capture_exception_with_context(self):
        """Test capture_exception with additional context."""
        mock_sdk, mock_scope = create_mock_sentry_sdk()
        exception = ValueError("Test error")
        context = {"claim_id": 123, "payer_id": 456}

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = capture_exception(exception, context=context)

            assert result == "event-id-123"
            # Should set context
            assert mock_scope.set_context.called

    def test_capture_exception_with_user(self):
        """Test capture_exception with user information."""
        mock_sdk, mock_scope = create_mock_sentry_sdk()
        exception = ValueError("Test error")
        user = {"id": "user123", "username": "testuser"}

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = capture_exception(exception, user=user)

            assert result == "event-id-123"
            assert mock_scope.user == user

    def test_capture_exception_with_tags(self):
        """Test capture_exception with tags."""
        mock_sdk, mock_scope = create_mock_sentry_sdk()
        exception = ValueError("Test error")
        tags = {"environment": "test", "component": "api"}

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = capture_exception(exception, tags=tags)

            assert result == "event-id-123"
            # Should set tags
            assert mock_scope.set_tag.called

    def test_capture_exception_no_sentry(self):
        """Test capture_exception when Sentry is not available."""
        exception = ValueError("Test error")

        with patch("builtins.__import__", side_effect=ImportError("No module named 'sentry_sdk'")):
            result = capture_exception(exception)

            assert result is None

    def test_capture_exception_error(self):
        """Test capture_exception when exception occurs."""
        exception = ValueError("Test error")

        mock_sdk = MagicMock()
        mock_sdk.push_scope.side_effect = Exception("Sentry error")

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = capture_exception(exception)

            assert result is None


@pytest.mark.unit
class TestCaptureMessage:
    """Tests for capture_message function."""

    def test_capture_message_with_sentry(self):
        """Test capture_message when Sentry is available."""
        mock_sdk, mock_scope = create_mock_sentry_sdk()

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = capture_message("Test message")

            assert result == "event-id-123"
            mock_sdk.capture_message.assert_called_once()

    def test_capture_message_with_level(self):
        """Test capture_message with different levels."""
        mock_sdk, mock_scope = create_mock_sentry_sdk()

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = capture_message("Test message", level="error")

            assert result == "event-id-123"
            # Should map level correctly
            call_args = mock_sdk.capture_message.call_args
            assert call_args[0][0] == "Test message"

    def test_capture_message_no_sentry(self):
        """Test capture_message when Sentry is not available."""
        with patch("builtins.__import__", side_effect=ImportError("No module named 'sentry_sdk'")):
            result = capture_message("Test message")

            assert result is None


@pytest.mark.unit
class TestSetUserContext:
    """Tests for set_user_context function."""

    def test_set_user_context_with_sentry(self):
        """Test set_user_context when Sentry is available."""
        mock_sdk = MagicMock()

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            set_user_context(user_id="user123", username="testuser")

            mock_sdk.set_user.assert_called_once_with({
                "id": "user123",
                "username": "testuser",
            })

    def test_set_user_context_with_kwargs(self):
        """Test set_user_context with additional kwargs."""
        mock_sdk = MagicMock()

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            set_user_context(user_id="user123", email="test@example.com", role="admin")

            mock_sdk.set_user.assert_called_once()
            call_kwargs = mock_sdk.set_user.call_args[0][0]
            assert call_kwargs["id"] == "user123"
            assert call_kwargs["email"] == "test@example.com"
            assert call_kwargs["role"] == "admin"

    def test_set_user_context_no_sentry(self):
        """Test set_user_context when Sentry is not available."""
        with patch("builtins.__import__", side_effect=ImportError("No module named 'sentry_sdk'")):
            # Should not raise
            set_user_context(user_id="user123")

    def test_set_user_context_error(self):
        """Test set_user_context when exception occurs."""
        mock_sdk = MagicMock()
        mock_sdk.set_user.side_effect = Exception("Sentry error")

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            # Should not raise
            set_user_context(user_id="user123")


@pytest.mark.unit
class TestClearUserContext:
    """Tests for clear_user_context function."""

    def test_clear_user_context_with_sentry(self):
        """Test clear_user_context when Sentry is available."""
        mock_sdk = MagicMock()

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            clear_user_context()

            mock_sdk.set_user.assert_called_once_with(None)

    def test_clear_user_context_no_sentry(self):
        """Test clear_user_context when Sentry is not available."""
        with patch("builtins.__import__", side_effect=ImportError("No module named 'sentry_sdk'")):
            # Should not raise
            clear_user_context()

    def test_clear_user_context_error(self):
        """Test clear_user_context when exception occurs."""
        mock_sdk = MagicMock()
        mock_sdk.set_user.side_effect = Exception("Sentry error")

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            # Should not raise
            clear_user_context()


@pytest.mark.unit
class TestAddBreadcrumb:
    """Tests for add_breadcrumb function."""

    def test_add_breadcrumb_with_sentry(self):
        """Test add_breadcrumb when Sentry is available."""
        mock_sdk = MagicMock()

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            add_breadcrumb("Test breadcrumb", category="test", level="info")

            mock_sdk.add_breadcrumb.assert_called_once()
            call_kwargs = mock_sdk.add_breadcrumb.call_args[1]
            assert call_kwargs["message"] == "Test breadcrumb"
            assert call_kwargs["category"] == "test"
            assert call_kwargs["level"] == "info"

    def test_add_breadcrumb_with_data(self):
        """Test add_breadcrumb with additional data."""
        mock_sdk = MagicMock()

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            add_breadcrumb("Test breadcrumb", data={"key": "value"})

            mock_sdk.add_breadcrumb.assert_called_once()
            call_kwargs = mock_sdk.add_breadcrumb.call_args[1]
            assert call_kwargs["data"] == {"key": "value"}

    def test_add_breadcrumb_no_sentry(self):
        """Test add_breadcrumb when Sentry is not available."""
        with patch("builtins.__import__", side_effect=ImportError("No module named 'sentry_sdk'")):
            # Should not raise
            add_breadcrumb("Test breadcrumb")

    def test_add_breadcrumb_error(self):
        """Test add_breadcrumb when exception occurs."""
        mock_sdk = MagicMock()
        mock_sdk.add_breadcrumb.side_effect = Exception("Sentry error")

        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "sentry_sdk":
                    return mock_sdk
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            # Should not raise
            add_breadcrumb("Test breadcrumb")

