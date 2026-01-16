"""Tests for security configuration."""
import os
from unittest.mock import patch
import pytest

from app.config.security import (
    SecuritySettings,
    settings,
    validate_security_settings,
    validate_production_security,
    get_cors_origins,
    get_jwt_secret,
    get_jwt_algorithm,
    get_jwt_access_token_expire_minutes,
    get_bcrypt_rounds,
    get_rate_limit_per_minute,
    get_rate_limit_per_hour,
    is_auth_required,
    get_auth_exempt_paths,
    DEFAULT_JWT_SECRET,
    DEFAULT_ENCRYPTION_KEY,
    calculate_entropy,
    MIN_ENTROPY_JWT_SECRET,
    MIN_ENTROPY_ENCRYPTION_KEY,
    check_weak_patterns,
)


@pytest.mark.unit
class TestSecuritySettings:
    """Tests for SecuritySettings class."""

    def test_security_settings_defaults(self):
        """Test SecuritySettings with default values."""
        # Note: SecuritySettings reads from .env file, so we test with proper env vars
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test-secret-key-min-32-characters-long-for-testing",
            "ENCRYPTION_KEY": "test-encryption-key-32-characters-long",
        }, clear=False):
            # Create new instance to test defaults
            test_settings = SecuritySettings()
            assert test_settings.jwt_algorithm == "HS256"
            assert test_settings.jwt_access_token_expire_minutes == 1440
            assert test_settings.jwt_refresh_token_expire_days == 7
            assert test_settings.bcrypt_rounds == 12
            assert test_settings.cors_origins == "http://localhost:3000"
            assert test_settings.rate_limit_per_minute == 60
            assert test_settings.rate_limit_per_hour == 1000
            # require_auth may be True if set in .env, so we just check it's a boolean
            assert isinstance(test_settings.require_auth, bool)

    def test_security_settings_from_env(self):
        """Test SecuritySettings reading from environment variables."""
        env_vars = {
            "JWT_SECRET_KEY": "test-secret-key-min-32-characters-long",
            "ENCRYPTION_KEY": "test-encryption-key-32-characters",
            "JWT_ALGORITHM": "RS256",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "720",
            "CORS_ORIGINS": "http://localhost:3000,https://example.com",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            test_settings = SecuritySettings()
            assert test_settings.jwt_secret_key == "test-secret-key-min-32-characters-long"
            assert test_settings.encryption_key == "test-encryption-key-32-characters"
            assert test_settings.cors_origins == "http://localhost:3000,https://example.com"


@pytest.mark.unit
class TestValidateSecuritySettings:
    """Tests for validate_security_settings function."""

    def test_validate_security_settings_default_jwt_secret_fails(self):
        """Test that validation fails with default JWT secret."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_secret_key = DEFAULT_JWT_SECRET
            mock_settings.encryption_key = "test-encryption-key-32-characters-long"
            
            with pytest.raises(Exception):  # AppError
                validate_security_settings()

    def test_validate_security_settings_default_encryption_key_fails(self):
        """Test that validation fails with default encryption key."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-min-32-characters-long"
            mock_settings.encryption_key = DEFAULT_ENCRYPTION_KEY
            
            with pytest.raises(Exception):  # AppError
                validate_security_settings()

    def test_validate_security_settings_short_jwt_secret_fails(self):
        """Test that validation fails with short JWT secret."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_secret_key = "short"
            mock_settings.encryption_key = "test-encryption-key-32-characters-long"
            
            with pytest.raises(Exception):  # AppError
                validate_security_settings()

    def test_validate_security_settings_short_encryption_key_fails(self):
        """Test that validation fails with short encryption key."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-min-32-characters-long"
            mock_settings.encryption_key = "short"
            
            with pytest.raises(Exception):  # AppError
                validate_security_settings()

    def test_validate_security_settings_production_debug_fails(self):
        """Test that validation fails with DEBUG=true in production."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-min-32-characters-long"
            mock_settings.encryption_key = "test-encryption-key-32-characters-long"
            mock_settings.cors_origins = "https://example.com"
            
            with patch.dict(os.environ, {"ENVIRONMENT": "production", "DEBUG": "true"}):
                with pytest.raises(Exception):  # AppError
                    validate_security_settings()

    def test_validate_security_settings_production_wildcard_cors_fails(self):
        """Test that validation fails with wildcard CORS in production."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-min-32-characters-long"
            mock_settings.encryption_key = "test-encryption-key-32-characters-long"
            mock_settings.cors_origins = "*"
            
            with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
                with pytest.raises(Exception):  # AppError
                    validate_security_settings()

    def test_validate_production_security_calls_validate_security_settings(self):
        """Test that validate_production_security calls validate_security_settings."""
        with patch("app.config.security.validate_security_settings") as mock_validate:
            validate_production_security()
            mock_validate.assert_called_once()


@pytest.mark.unit
class TestSecurityHelperFunctions:
    """Tests for security helper functions."""

    def test_get_cors_origins(self):
        """Test get_cors_origins function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.cors_origins = "http://localhost:3000,https://example.com"
            origins = get_cors_origins()
            assert origins == ["http://localhost:3000", "https://example.com"]

    def test_get_cors_origins_with_spaces(self):
        """Test get_cors_origins handles spaces correctly."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.cors_origins = "http://localhost:3000, https://example.com"
            origins = get_cors_origins()
            assert origins == ["http://localhost:3000", "https://example.com"]

    def test_get_jwt_secret(self):
        """Test get_jwt_secret function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret"
            assert get_jwt_secret() == "test-secret"

    def test_get_jwt_algorithm(self):
        """Test get_jwt_algorithm function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_algorithm = "RS256"
            assert get_jwt_algorithm() == "RS256"

    def test_get_jwt_access_token_expire_minutes(self):
        """Test get_jwt_access_token_expire_minutes function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.jwt_access_token_expire_minutes = 720
            assert get_jwt_access_token_expire_minutes() == 720

    def test_get_bcrypt_rounds(self):
        """Test get_bcrypt_rounds function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.bcrypt_rounds = 14
            assert get_bcrypt_rounds() == 14

    def test_get_rate_limit_per_minute(self):
        """Test get_rate_limit_per_minute function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.rate_limit_per_minute = 120
            assert get_rate_limit_per_minute() == 120

    def test_get_rate_limit_per_hour(self):
        """Test get_rate_limit_per_hour function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.rate_limit_per_hour = 2000
            assert get_rate_limit_per_hour() == 2000

    def test_is_auth_required(self):
        """Test is_auth_required function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.require_auth = True
            assert is_auth_required() is True
            
            mock_settings.require_auth = False
            assert is_auth_required() is False

    def test_get_auth_exempt_paths(self):
        """Test get_auth_exempt_paths function."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.auth_exempt_paths = "/api/v1/health,/api/v1/docs"
            paths = get_auth_exempt_paths()
            assert paths == ["/api/v1/health", "/api/v1/docs"]

    def test_get_auth_exempt_paths_with_spaces(self):
        """Test get_auth_exempt_paths handles spaces correctly."""
        with patch("app.config.security.settings") as mock_settings:
            mock_settings.auth_exempt_paths = "/api/v1/health, /api/v1/docs"
            paths = get_auth_exempt_paths()
            assert paths == ["/api/v1/health", "/api/v1/docs"]


@pytest.mark.unit
class TestEntropyCalculation:
    """Tests for entropy calculation using Shannon entropy."""

    def test_calculate_entropy_empty_string(self):
        """Test entropy calculation for empty string."""
        assert calculate_entropy("") == 0.0

    def test_calculate_entropy_single_character(self):
        """Test entropy calculation for single character."""
        # Single character has 0 entropy (no randomness)
        assert calculate_entropy("a") == 0.0

    def test_calculate_entropy_repeated_characters(self):
        """Test entropy calculation for repeated characters (low entropy)."""
        # All same characters = 0 entropy
        assert calculate_entropy("aaaa") == 0.0
        assert calculate_entropy("1111") == 0.0

    def test_calculate_entropy_two_characters_equal(self):
        """Test entropy calculation for two equal characters."""
        # Two equal characters: p(a) = 1.0, entropy = -1.0 * log2(1.0) = 0
        assert calculate_entropy("aa") == 0.0

    def test_calculate_entropy_two_characters_different(self):
        """Test entropy calculation for two different characters."""
        # Two different characters: p(a) = 0.5, p(b) = 0.5
        # entropy = -0.5 * log2(0.5) - 0.5 * log2(0.5) = 1.0
        entropy = calculate_entropy("ab")
        assert abs(entropy - 1.0) < 0.01

    def test_calculate_entropy_four_different_characters(self):
        """Test entropy calculation for four different characters."""
        # Four different characters: each p = 0.25
        # entropy = -4 * (0.25 * log2(0.25)) = -4 * (0.25 * -2) = 2.0
        entropy = calculate_entropy("abcd")
        assert abs(entropy - 2.0) < 0.01

    def test_calculate_entropy_high_entropy_string(self):
        """Test entropy calculation for high entropy string (random characters)."""
        # Random string with many different characters should have high entropy
        random_string = "REMOVED_SECRET_FROM_HISTORY"
        entropy = calculate_entropy(random_string)
        # Should be well above minimum threshold of 4.0
        assert entropy >= MIN_ENTROPY_JWT_SECRET
        assert entropy >= MIN_ENTROPY_ENCRYPTION_KEY

    def test_calculate_entropy_low_entropy_string(self):
        """Test entropy calculation for low entropy string (predictable pattern)."""
        # Repeated pattern has low entropy
        low_entropy = calculate_entropy("abcabcabcabc")
        # Should be below minimum threshold
        assert low_entropy < MIN_ENTROPY_JWT_SECRET

    def test_calculate_entropy_base64_like_string(self):
        """Test entropy calculation for Base64-like string."""
        # Base64 URL-safe characters should have high entropy (~6 bits/char for truly random)
        base64_string = "REMOVED_SECRET_FROM_HISTORY"
        entropy = calculate_entropy(base64_string)
        # Should be well above 4.0 bits/char
        assert entropy >= MIN_ENTROPY_JWT_SECRET

    def test_entropy_thresholds_are_correct(self):
        """Test that entropy thresholds are set to 4.0 bits/character."""
        assert MIN_ENTROPY_JWT_SECRET == 4.0
        assert MIN_ENTROPY_ENCRYPTION_KEY == 4.0

    def test_jwt_secret_validation_with_low_entropy(self):
        """Test that JWT secret validation rejects low entropy keys."""
        # Create a low entropy key (repeated pattern)
        low_entropy_key = "abcabcabcabcabcabcabcabcabcabcab"  # 32 chars but low entropy
        
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": low_entropy_key,
            "ENCRYPTION_KEY": "test-encryption-key-32-characters-long",
        }, clear=False):
            with pytest.raises(ValueError, match="insufficient entropy"):
                SecuritySettings()

    def test_encryption_key_validation_with_low_entropy(self):
        """Test that encryption key validation rejects low entropy keys."""
        # Create a low entropy key (repeated pattern)
        low_entropy_key = "abcabcabcabcabcabcabcabcab"  # 32 chars but low entropy
        
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test-secret-key-min-32-characters-long",
            "ENCRYPTION_KEY": low_entropy_key,
        }, clear=False):
            with pytest.raises(ValueError, match="insufficient entropy"):
                SecuritySettings()

    def test_jwt_secret_validation_with_high_entropy(self):
        """Test that JWT secret validation accepts high entropy keys."""
        # Create a high entropy key (random characters)
        high_entropy_key = "REMOVED_SECRET_FROM_HISTORY"
        
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": high_entropy_key,
            "ENCRYPTION_KEY": "test-encryption-key-32-characters-long",
        }, clear=False):
            # Should not raise an exception
            test_settings = SecuritySettings()
            assert test_settings.jwt_secret_key == high_entropy_key

    def test_encryption_key_validation_with_high_entropy(self):
        """Test that encryption key validation accepts high entropy keys."""
        # Create a high entropy key (random characters, exactly 32 chars)
        high_entropy_key = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1v"
        
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test-secret-key-min-32-characters-long",
            "ENCRYPTION_KEY": high_entropy_key,
        }, clear=False):
            # Should not raise an exception
            test_settings = SecuritySettings()
            assert test_settings.encryption_key == high_entropy_key

    def test_check_weak_patterns_detects_low_entropy(self):
        """Test that check_weak_patterns detects low entropy."""
        low_entropy_key = "abcabcabcabcabcabcabcabcabcabcab"
        patterns = check_weak_patterns(low_entropy_key, min_entropy=MIN_ENTROPY_JWT_SECRET)
        # Should detect low entropy
        assert any("entropy" in p.lower() for p in patterns)

    def test_check_weak_patterns_accepts_high_entropy(self):
        """Test that check_weak_patterns accepts high entropy keys."""
        high_entropy_key = "REMOVED_SECRET_FROM_HISTORY"
        patterns = check_weak_patterns(high_entropy_key, min_entropy=MIN_ENTROPY_JWT_SECRET)
        # Should not detect entropy issues
        assert not any("entropy" in p.lower() for p in patterns)


@pytest.mark.unit
class TestCheckWeakPatterns:
    """Tests for enhanced check_weak_patterns function."""

    def test_all_lowercase_detection(self):
        """Test detection of all lowercase letters."""
        patterns = check_weak_patterns("abcdefghijklmnopqrstuvwxyz")
        assert any("lowercase" in p.lower() for p in patterns)
        
        # Mixed case should not trigger
        patterns = check_weak_patterns("AbCdEfGhIjKlMnOpQrStUvWxYz")
        assert not any("lowercase" in p.lower() for p in patterns)

    def test_all_uppercase_detection(self):
        """Test detection of all uppercase letters."""
        patterns = check_weak_patterns("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        assert any("uppercase" in p.lower() for p in patterns)
        
        # Mixed case should not trigger
        patterns = check_weak_patterns("AbCdEfGhIjKlMnOpQrStUvWxYz")
        assert not any("uppercase" in p.lower() for p in patterns)

    def test_repeated_characters_detection(self):
        """Test detection of repeated characters (<30% unique)."""
        # String with <30% unique characters
        patterns = check_weak_patterns("aaaaabbbbbcccccdddddeeeee")
        assert any("repeated characters" in p.lower() for p in patterns)
        assert any("30" in p or "0.3" in p for p in patterns)
        
        # String with >30% unique characters should not trigger
        patterns = check_weak_patterns("abcdefghijklmnopqrstuvwxyz1234567890")
        assert not any("repeated characters" in p.lower() for p in patterns)

    def test_sequential_numbers_forward(self):
        """Test detection of sequential numbers (forward)."""
        patterns = check_weak_patterns("test123456test")
        assert any("sequential" in p.lower() and "123" in p for p in patterns)
        
        patterns = check_weak_patterns("key789key")
        assert any("sequential" in p.lower() and "789" in p for p in patterns)

    def test_sequential_numbers_reverse(self):
        """Test detection of sequential numbers (reverse)."""
        patterns = check_weak_patterns("test987654test")
        assert any("sequential" in p.lower() for p in patterns)
        
        patterns = check_weak_patterns("key321key")
        assert any("sequential" in p.lower() for p in patterns)

    def test_sequential_letters_forward(self):
        """Test detection of sequential letters (forward)."""
        patterns = check_weak_patterns("testabctest")
        assert any("sequential" in p.lower() and "abc" in p.lower() for p in patterns)
        
        patterns = check_weak_patterns("keyxyztest")
        assert any("sequential" in p.lower() for p in patterns)

    def test_sequential_letters_reverse(self):
        """Test detection of sequential letters (reverse)."""
        patterns = check_weak_patterns("testzyxtest")
        assert any("sequential" in p.lower() for p in patterns)
        
        patterns = check_weak_patterns("keycbatest")
        assert any("sequential" in p.lower() for p in patterns)

    def test_repeated_substrings_4plus_chars(self):
        """Test detection of repeated 4+ character substrings."""
        patterns = check_weak_patterns("test1234test1234test")
        assert any("repeated substring" in p.lower() and "1234" in p for p in patterns)
        
        patterns = check_weak_patterns("abcdxyzabcdxyz")
        assert any("repeated substring" in p.lower() for p in patterns)

    def test_frequent_short_repeats_3chars(self):
        """Test detection of 3-char substrings appearing 3+ times."""
        patterns = check_weak_patterns("abc123abc456abc789abc")
        assert any("frequently repeated" in p.lower() and "abc" in p.lower() for p in patterns)
        
        patterns = check_weak_patterns("xyz1xyz2xyz3xyz4")
        assert any("frequently repeated" in p.lower() for p in patterns)

    def test_predictable_substrings_password(self):
        """Test detection of predictable substrings like 'password'."""
        patterns = check_weak_patterns("mypassword123")
        assert any("predictable substring" in p.lower() and "password" in p.lower() for p in patterns)

    def test_predictable_substrings_secret(self):
        """Test detection of predictable substrings like 'secret'."""
        patterns = check_weak_patterns("mysecretkey")
        assert any("predictable substring" in p.lower() and "secret" in p.lower() for p in patterns)

    def test_predictable_substrings_years(self):
        """Test detection of year patterns."""
        patterns = check_weak_patterns("key2024key")
        assert any("predictable substring" in p.lower() and "2024" in p for p in patterns)
        
        patterns = check_weak_patterns("key2025key")
        assert any("predictable substring" in p.lower() and "2025" in p for p in patterns)

    def test_predictable_substrings_common_words(self):
        """Test detection of common words."""
        patterns = check_weak_patterns("adminkey123")
        assert any("predictable substring" in p.lower() and "admin" in p.lower() for p in patterns)
        
        patterns = check_weak_patterns("testkey123")
        assert any("predictable substring" in p.lower() and "test" in p.lower() for p in patterns)

    def test_predictable_substrings_keyboard_patterns(self):
        """Test detection of keyboard patterns."""
        patterns = check_weak_patterns("qwerty123")
        assert any("predictable substring" in p.lower() and "qwerty" in p.lower() for p in patterns)
        
        patterns = check_weak_patterns("asdf123")
        assert any("predictable substring" in p.lower() and "asdf" in p.lower() for p in patterns)

    def test_date_patterns(self):
        """Test detection of date patterns."""
        patterns = check_weak_patterns("key20240101key")
        assert any("date pattern" in p.lower() for p in patterns)
        
        patterns = check_weak_patterns("key12/31/2024key")
        assert any("date pattern" in p.lower() for p in patterns)

    def test_strong_key_no_patterns(self):
        """Test that a strong key doesn't trigger false positives."""
        # This is a strong random-looking key
        strong_key = "Kj8#mP2$vL9@nQ5&wR7!xT3*yU6^zV4"
        patterns = check_weak_patterns(strong_key, min_entropy=2.0)  # Lower threshold for test
        # Should only have entropy warning if entropy is low, not pattern warnings
        pattern_warnings = [p for p in patterns if "pattern" in p.lower() or "sequential" in p.lower() 
                           or "repeated" in p.lower() or "predictable" in p.lower()]
        assert len(pattern_warnings) == 0

    def test_empty_string(self):
        """Test that empty string returns no patterns."""
        patterns = check_weak_patterns("")
        assert len(patterns) == 0

    def test_entropy_check(self):
        """Test that low entropy is detected."""
        # Very low entropy string (all same character)
        patterns = check_weak_patterns("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", min_entropy=4.0)
        assert any("entropy" in p.lower() for p in patterns)

