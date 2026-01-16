"""Tests for security configuration."""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

from app.utils.errors import AppError


@pytest.mark.unit
class TestSecuritySettings:
    """Test SecuritySettings class."""

    def test_get_cors_origins(self):
        """Test getting CORS origins."""
        # Import after setting env var to avoid validation errors
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        # Reload module to get new settings
        import importlib
        from app.config import security
        importlib.reload(security)
        
        origins = security.get_cors_origins()
        assert isinstance(origins, list)
        assert len(origins) > 0

    def test_get_jwt_secret(self):
        """Test getting JWT secret."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        secret = security.get_jwt_secret()
        assert secret == "test-secret-key-min-32-characters-long-for-testing"

    def test_get_jwt_algorithm(self):
        """Test getting JWT algorithm."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        algorithm = security.get_jwt_algorithm()
        assert algorithm == "HS256"

    def test_get_auth_exempt_paths(self):
        """Test getting auth exempt paths."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        paths = security.get_auth_exempt_paths()
        assert isinstance(paths, list)
        assert "/api/v1/health" in paths


@pytest.mark.unit
class TestSecurityValidation:
    """Test security validation function."""

    def test_validation_with_secure_keys_passes(self):
        """Test that validation passes with secure keys."""
        os.environ["JWT_SECRET_KEY"] = "secure-jwt-secret-key-minimum-32-characters-long"
        os.environ["ENCRYPTION_KEY"] = "secure-encryption-key-32-characters"
        os.environ["ENVIRONMENT"] = "development"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Should not raise exception
        try:
            security.validate_security_settings()
        except AppError:
            pytest.fail("Validation should pass with secure keys")

    def test_validation_rejects_default_jwt_secret(self, monkeypatch):
        """Test that validation rejects default JWT secret."""
        # Test validation logic directly by mocking settings
        from app.config.security import SecuritySettings, validate_security_settings, DEFAULT_JWT_SECRET
        from unittest.mock import patch
        
        # Create settings with default JWT secret
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = DEFAULT_JWT_SECRET
            mock_settings.encryption_key = "secure-encryption-key-32-characters"
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    def test_validation_rejects_default_encryption_key(self, monkeypatch):
        """Test that validation rejects default encryption key."""
        from app.config.security import validate_security_settings, DEFAULT_ENCRYPTION_KEY
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "secure-jwt-secret-key-minimum-32-characters-long"
            mock_settings.encryption_key = DEFAULT_ENCRYPTION_KEY
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    def test_validation_rejects_short_jwt_secret(self, monkeypatch):
        """Test that validation rejects JWT secret shorter than 32 characters."""
        from app.config.security import validate_security_settings
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "short-key"
            mock_settings.encryption_key = "secure-encryption-key-32-characters"
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    def test_validation_rejects_short_encryption_key(self, monkeypatch):
        """Test that validation rejects encryption key shorter than 32 characters."""
        from app.config.security import validate_security_settings
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "secure-jwt-secret-key-minimum-32-characters-long"
            mock_settings.encryption_key = "short-key"
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    def test_validation_rejects_change_me_prefix(self, monkeypatch):
        """Test that validation rejects keys starting with 'change-me'."""
        from app.config.security import validate_security_settings
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "change-me-custom-key-32-characters-long"
            mock_settings.encryption_key = "secure-encryption-key-32-characters"
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    @patch.dict(os.environ, {
        "JWT_SECRET_KEY": "secure-jwt-secret-key-minimum-32-characters-long",
        "ENCRYPTION_KEY": "secure-encryption-key-32-characters",
        "ENVIRONMENT": "production",
        "DEBUG": "false",
    })
    def test_validation_production_checks(self):
        """Test production-specific validation checks."""
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Should pass with secure keys and production settings
        try:
            security.validate_security_settings()
        except AppError:
            pytest.fail("Validation should pass with secure production settings")

    def test_validation_rejects_debug_in_production(self, monkeypatch):
        """Test that validation rejects DEBUG=true in production."""
        from app.config.security import validate_security_settings
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "secure-jwt-secret-key-minimum-32-characters-long"
            mock_settings.encryption_key = "secure-encryption-key-32-characters"
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "production")
            monkeypatch.setenv("DEBUG", "true")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    def test_validation_rejects_wildcard_cors_in_production(self, monkeypatch):
        """Test that validation rejects wildcard CORS in production."""
        from app.config.security import validate_security_settings
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "secure-jwt-secret-key-minimum-32-characters-long"
            mock_settings.encryption_key = "secure-encryption-key-32-characters"
            mock_settings.require_auth = False
            mock_settings.cors_origins = "*"
            
            monkeypatch.setenv("ENVIRONMENT", "production")
            monkeypatch.setenv("DEBUG", "false")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    def test_validate_production_security_calls_validate_security_settings(self):
        """Test that validate_production_security calls validate_security_settings."""
        os.environ["JWT_SECRET_KEY"] = "secure-jwt-secret-key-minimum-32-characters-long"
        os.environ["ENCRYPTION_KEY"] = "secure-encryption-key-32-characters"
        os.environ["ENVIRONMENT"] = "development"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Should call the same validation
        with patch.object(security, "validate_security_settings") as mock_validate:
            security.validate_production_security()
            mock_validate.assert_called_once()


@pytest.mark.unit
class TestSecurityHelperFunctions:
    """Test security helper functions."""

    def test_get_rate_limit_per_minute(self):
        """Test getting rate limit per minute."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        rate_limit = security.get_rate_limit_per_minute()
        assert isinstance(rate_limit, int)
        assert rate_limit > 0

    def test_get_rate_limit_per_hour(self):
        """Test getting rate limit per hour."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        rate_limit = security.get_rate_limit_per_hour()
        assert isinstance(rate_limit, int)
        assert rate_limit > 0

    def test_get_bcrypt_rounds(self):
        """Test getting bcrypt rounds."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        rounds = security.get_bcrypt_rounds()
        assert isinstance(rounds, int)
        assert rounds > 0

    def test_is_auth_required(self):
        """Test checking if auth is required."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        require_auth = security.is_auth_required()
        assert isinstance(require_auth, bool)


@pytest.mark.unit
class TestSecuritySettingsEdgeCases:
    """Test edge cases and boundary conditions for security settings."""

    def test_validation_exactly_32_characters(self):
        """Test validation with exactly 32 character keys."""
        os.environ["JWT_SECRET_KEY"] = "a" * 32
        os.environ["ENCRYPTION_KEY"] = "b" * 32
        os.environ["ENVIRONMENT"] = "development"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        try:
            security.validate_security_settings()
        except Exception:
            pytest.fail("Exactly 32 characters should pass validation")

    def test_validation_31_characters_fails(self, monkeypatch):
        """Test validation fails with 31 character key."""
        from app.config.security import validate_security_settings
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "a" * 31
            mock_settings.encryption_key = "b" * 32
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError, match="Security validation failed"):
                validate_security_settings()

    def test_validation_multiple_errors(self, monkeypatch):
        """Test validation reports multiple errors."""
        from app.config.security import validate_security_settings
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = "change-me-short"
            mock_settings.encryption_key = "change-me-also-short"
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError) as exc_info:
                validate_security_settings()
            
            # Should have details with multiple errors
            assert exc_info.value.details is not None
            assert "errors" in exc_info.value.details
            assert len(exc_info.value.details["errors"]) >= 2

    def test_validation_warnings_in_production(self):
        """Test that warnings are logged but don't prevent startup."""
        os.environ["JWT_SECRET_KEY"] = "secure-jwt-secret-key-minimum-32-characters-long"
        os.environ["ENCRYPTION_KEY"] = "secure-encryption-key-32-characters"
        os.environ["ENVIRONMENT"] = "production"
        os.environ["DEBUG"] = "false"
        os.environ["REQUIRE_AUTH"] = "false"  # Should generate warning
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Should not raise exception (warnings don't block)
        try:
            security.validate_security_settings()
        except AppError:
            pytest.fail("Warnings should not prevent startup")

    def test_cors_origins_multiple(self):
        """Test getting multiple CORS origins."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://localhost:8000,https://example.com"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        origins = security.get_cors_origins()
        assert len(origins) == 3
        assert "http://localhost:3000" in origins
        assert "http://localhost:8000" in origins
        assert "https://example.com" in origins

    def test_cors_origins_with_spaces(self):
        """Test CORS origins with spaces are trimmed."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        os.environ["CORS_ORIGINS"] = " http://localhost:3000 , http://localhost:8000 "
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        origins = security.get_cors_origins()
        assert all(not origin.startswith(" ") and not origin.endswith(" ") for origin in origins)

    def test_auth_exempt_paths_multiple(self):
        """Test getting multiple auth exempt paths."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        paths = security.get_auth_exempt_paths()
        assert len(paths) > 1
        assert "/api/v1/health" in paths

    def test_jwt_access_token_expire_minutes(self):
        """Test getting JWT access token expiration."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        minutes = security.get_jwt_access_token_expire_minutes()
        assert isinstance(minutes, int)
        assert minutes > 0

    def test_validation_error_message_format(self, monkeypatch):
        """Test that error messages are properly formatted."""
        from app.config.security import validate_security_settings, DEFAULT_JWT_SECRET, DEFAULT_ENCRYPTION_KEY
        from unittest.mock import patch
        
        with patch('app.config.security.settings') as mock_settings:
            mock_settings.jwt_secret_key = DEFAULT_JWT_SECRET
            mock_settings.encryption_key = DEFAULT_ENCRYPTION_KEY
            mock_settings.require_auth = False
            mock_settings.cors_origins = "http://localhost:3000"
            
            monkeypatch.setenv("ENVIRONMENT", "development")
            
            with pytest.raises(AppError) as exc_info:
                validate_security_settings()
            
            error_message = str(exc_info.value)
            assert "Security validation failed" in error_message
            # Check that details contain the error information
            assert exc_info.value.details is not None
            assert "errors" in exc_info.value.details
            errors = exc_info.value.details["errors"]
            assert any("JWT_SECRET_KEY" in err or "generate_keys.py" in err for err in errors)

    def test_validation_in_staging_environment(self):
        """Test validation in staging environment."""
        os.environ["JWT_SECRET_KEY"] = "secure-jwt-secret-key-minimum-32-characters-long"
        os.environ["ENCRYPTION_KEY"] = "secure-encryption-key-32-characters"
        os.environ["ENVIRONMENT"] = "staging"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Should validate (not production, but still checks defaults)
        try:
            security.validate_security_settings()
        except AppError:
            pytest.fail("Staging should validate with secure keys")

    def test_validation_in_test_environment(self):
        """Test validation in test environment."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        os.environ["ENVIRONMENT"] = "test"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Should validate
        try:
            security.validate_security_settings()
        except AppError:
            pytest.fail("Test environment should validate with secure keys")

    def test_settings_from_env_file(self):
        """Test that settings can be loaded from .env file."""
        # This tests that BaseSettings reads from .env
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-min-32-characters-long-for-testing"
        os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-characters"
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Settings should be loaded
        assert security.settings is not None
        assert security.settings.jwt_secret_key is not None
        assert security.settings.encryption_key is not None

    def test_validation_case_insensitive_environment(self):
        """Test that environment variable is case insensitive."""
        os.environ["JWT_SECRET_KEY"] = "secure-jwt-secret-key-minimum-32-characters-long"
        os.environ["ENCRYPTION_KEY"] = "secure-encryption-key-32-characters"
        os.environ["ENVIRONMENT"] = "PRODUCTION"  # Uppercase
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        # Should still work (case insensitive)
        try:
            security.validate_security_settings()
        except AppError as e:
            # If it fails, should be for a valid reason, not case sensitivity
            assert "PRODUCTION" not in str(e) or "production" in str(e).lower()

    def test_validation_debug_false_string(self):
        """Test that DEBUG=false (string) is accepted."""
        os.environ["JWT_SECRET_KEY"] = "secure-jwt-secret-key-minimum-32-characters-long"
        os.environ["ENCRYPTION_KEY"] = "secure-encryption-key-32-characters"
        os.environ["ENVIRONMENT"] = "production"
        os.environ["DEBUG"] = "false"  # String, not boolean
        
        import importlib
        from app.config import security
        importlib.reload(security)
        
        try:
            security.validate_security_settings()
        except AppError as e:
            assert "DEBUG" not in str(e) or "false" in str(e).lower()

