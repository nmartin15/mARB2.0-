"""Security configuration and validation.

This module provides comprehensive security settings and validation for the mARB 2.0 application.
It enforces security best practices including secret key validation, CORS configuration,
authentication settings, and production security checks.

All security settings are validated on module import to prevent the application
from starting with insecure configurations.
"""
import os
import re
from typing import List, Set, Dict
from collections import Counter
from urllib.parse import urlparse
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from app.utils.logger import get_logger
from app.utils.errors import AppError

logger = get_logger(__name__)

# Default values that should NEVER be used in any environment
DEFAULT_JWT_SECRET = "change-me-in-production-min-32-characters-required"
DEFAULT_ENCRYPTION_KEY = "change-me-32-character-encryption-key"

# Allowed JWT algorithms (only strong algorithms)
ALLOWED_JWT_ALGORITHMS: Set[str] = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}

# Weak patterns that indicate insecure keys
WEAK_KEY_PATTERNS = [
    r"^(password|secret|key|token).*$",
    r"^.*(123|abc|test|demo|example).*$",
    r"^[a-z]+$",  # All lowercase
    r"^[A-Z]+$",  # All uppercase
    r"^[0-9]+$",  # All numbers
    r"^(.)\1+$",  # Repeated characters
]

# Minimum entropy thresholds (bits per character)
# For truly random keys, entropy should be close to log2(alphabet_size)
# Base64 URL-safe: ~6 bits/char, alphanumeric: ~5.95 bits/char
# We require at least 4.0 bits/char to ensure sufficient randomness
MIN_ENTROPY_JWT_SECRET = 4.0  # Minimum entropy for JWT secrets
MIN_ENTROPY_ENCRYPTION_KEY = 4.0  # Minimum entropy for encryption keys


def calculate_entropy(text: str) -> float:
    """
    Calculate Shannon entropy of a string.
    
    Higher entropy indicates more randomness. A truly random string should have
    entropy close to log2(alphabet_size).
    
    Args:
        text: The string to calculate entropy for
        
    Returns:
        Entropy value (bits per character)
    """
    import math
    
    if not text:
        return 0.0
    
    length = len(text)
    if length == 0:
        return 0.0
    
    # Count character frequencies
    char_counts = Counter(text)
    
    # Calculate entropy using Shannon entropy formula: H = -Σ p(x) * log2(p(x))
    entropy = 0.0
    for count in char_counts.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def check_weak_patterns(key: str, min_entropy: float = MIN_ENTROPY_JWT_SECRET) -> List[str]:
    """
    Check for weak patterns in a secret key.
    
    Enhanced pattern detection includes:
    - All lowercase/uppercase detection
    - Repeated characters (<30% unique)
    - Sequential patterns (numbers and letters, forward and reverse)
    - Repeated substrings (4+ chars appearing multiple times)
    - Frequent short repeats (3-char substrings appearing 3+ times)
    - Predictable substrings (common words, dates, etc.)
    
    Args:
        key: The secret key to check
        min_entropy: Minimum entropy threshold (bits per character)
        
    Returns:
        List of detected weak patterns (empty if key is strong)
    """
    detected_patterns: List[str] = []
    
    if not key:
        return detected_patterns
    
    # Check regex patterns
    for pattern in WEAK_KEY_PATTERNS:
        if re.match(pattern, key, re.IGNORECASE):
            detected_patterns.append(f"Matches weak pattern: {pattern}")
    
    # Enhanced all lowercase/uppercase detection
    # Check if all characters are lowercase letters (no digits, no special chars)
    if key.islower() and key.isalpha():
        detected_patterns.append("Key contains only lowercase letters (weak pattern)")
    
    # Check if all characters are uppercase letters (no digits, no special chars)
    if key.isupper() and key.isalpha():
        detected_patterns.append("Key contains only uppercase letters (weak pattern)")
    
    # Check for all digits
    if key.isdigit():
        detected_patterns.append("Key contains only digits (weak pattern)")
    
    # Check for repeated characters (flags if <30% unique characters)
    unique_chars = len(set(key))
    total_chars = len(key)
    unique_ratio = unique_chars / total_chars if total_chars > 0 else 0.0
    if unique_ratio < 0.3:  # Less than 30% unique characters
        detected_patterns.append(
            f"Key has too many repeated characters ({unique_chars} unique out of {total_chars} total, "
            f"{unique_ratio*100:.1f}% unique)"
        )
    
    # Enhanced sequential pattern detection (numbers and letters, forward and reverse)
    if len(key) >= 3:
        key_lower = key.lower()
        
        # Generate all possible 3-character sequential patterns dynamically
        # Sequential numbers: 012, 123, 234, ..., 789 (forward) and 987, 876, ..., 210 (reverse)
        sequential_numbers_forward = [f"{i}{i+1}{i+2}" for i in range(8)]
        sequential_numbers_reverse = [f"{i}{i-1}{i-2}" for i in range(9, 1, -1)]
        
        # Sequential letters: abc, bcd, cde, ..., xyz (forward) and zyx, yxw, ..., cba (reverse)
        sequential_letters_forward = [
            f"{chr(ord('a')+i)}{chr(ord('a')+i+1)}{chr(ord('a')+i+2)}"
            for i in range(24)
        ]
        sequential_letters_reverse = [
            f"{chr(ord('z')-i)}{chr(ord('z')-i-1)}{chr(ord('z')-i-2)}"
            for i in range(24)
        ]
        
        all_sequential_patterns = (
            sequential_numbers_forward + sequential_numbers_reverse +
            sequential_letters_forward + sequential_letters_reverse
        )
        
        # Check for any sequential pattern
        for pattern in all_sequential_patterns:
            if pattern in key_lower:
                detected_patterns.append(
                    f"Key contains sequential pattern: '{pattern}' (weak pattern)"
                )
                break  # Only report first match to avoid spam
    
    # Optimized repeated substring detection (4+ char substrings appearing multiple times)
    if len(key) >= 8:
        seen_substrings = set()
        for i in range(len(key) - 3):  # Check 4+ char substrings
            substring = key[i:i+4]
            if substring in seen_substrings:
                # Count occurrences to provide accurate message
                count = key.count(substring)
                detected_patterns.append(
                    f"Repeated substring detected: '{substring}' appears {count} times"
                )
                break
            seen_substrings.add(substring)
    
    # Frequent short repeats (3-char substrings appearing 3+ times)
    if len(key) >= 6:
        substring_counts: Dict[str, int] = {}
        for i in range(len(key) - 2):  # Check 3-char substrings
            substring = key[i:i+3]
            substring_counts[substring] = substring_counts.get(substring, 0) + 1
        
        # Find substrings that appear 3+ times
        for substring, count in substring_counts.items():
            if count >= 3:
                detected_patterns.append(
                    f"Frequently repeated substring: '{substring}' appears {count} times"
                )
                break  # Only report first match
    
    # Enhanced predictable substrings (common words, dates, "password", "secret", etc.)
    predictable_substrings = [
        # Common security-related words
        "password", "secret", "key", "token", "auth", "admin", "root", "user",
        "login", "pass", "pwd", "passwd", "credential", "api", "api_key",
        # Common test/demo words
        "test", "demo", "example", "sample", "default", "change", "temp", "tmp",
        "dev", "development", "staging", "prod", "production",
        # Common keyboard patterns
        "qwerty", "asdf", "zxcv", "1234", "abcd", "password123",
        # Years (current and near future/past)
        "2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028", "2029",
        # Common date patterns
        "0101", "1231", "01012024", "12312024", "01012025", "12312025",
        # Common number sequences
        "12345", "123456", "1234567", "12345678", "0000", "1111", "2222", "3333",
        "4444", "5555", "6666", "7777", "8888", "9999",
        # Common letter sequences
        "aaaa", "bbbb", "cccc", "dddd", "eeee", "ffff",
    ]
    
    key_lower = key.lower()
    for pred in predictable_substrings:
        if pred in key_lower:
            detected_patterns.append(f"Contains predictable substring: '{pred}'")
            break  # Only report first match
    
    # Enhanced date pattern detection
    # Detect common date formats: YYYY, MM/DD, DD/MM, YYYYMMDD, etc.
    date_patterns = [
        r'\d{4}[01]\d[0-3]\d',  # YYYYMMDD (year + month + day)
        r'[01]\d[0-3]\d\d{4}',  # MMDDYYYY
        r'[0-3]\d[01]\d\d{4}',  # DDMMYYYY
        r'\d{4}-[01]\d-[0-3]\d',  # YYYY-MM-DD
        r'[01]\d/[0-3]\d/\d{4}',  # MM/DD/YYYY
        r'[0-3]\d/[01]\d/\d{4}',  # DD/MM/YYYY
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, key):
            detected_patterns.append("Key contains date pattern (weak pattern)")
            break
    
    # Check entropy (this is the most important check)
    entropy = calculate_entropy(key)
    if entropy < min_entropy:
        detected_patterns.append(
            f"Low entropy detected ({entropy:.2f} bits/char, minimum {min_entropy:.1f} required). "
            "Key may not be sufficiently random. Use cryptographically secure random generation."
        )
    
    return detected_patterns


def validate_url_format(url: str) -> tuple[bool, str]:
    """
    Validate URL format and security.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    url = url.strip()
    if not url:
        return False, "Empty URL"
    
    try:
        parsed = urlparse(url)
        
        # Must have scheme
        if not parsed.scheme:
            return False, f"URL missing scheme: {url}"
        
        # Must have netloc (domain)
        if not parsed.netloc:
            return False, f"URL missing domain: {url}"
        
        # Scheme must be http or https
        if parsed.scheme not in ("http", "https"):
            return False, f"Invalid scheme '{parsed.scheme}'. Must be http or https"
        
        # Check for wildcards in domain
        if "*" in parsed.netloc:
            return False, f"Wildcards not allowed in domain: {url}"
        
        return True, ""
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


class SecuritySettings(BaseSettings):
    """Security settings with comprehensive validation.
    
    All settings are validated on initialization to ensure security best practices.
    Default values are provided for development but MUST be overridden in production.
    """

    jwt_secret_key: str = Field(
        default=os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET),
        description="JWT secret key for token signing. Must be set via JWT_SECRET_KEY environment variable. "
                    "Minimum 32 characters (enforced in field validator), must be cryptographically random. "
                    "Validated for length, entropy (minimum 4.0 bits/char), and weak patterns.",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm. Must be one of: HS256, HS384, HS512, RS256, RS384, RS512",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=1440,  # 24 hours
        ge=5,  # Minimum 5 minutes
        le=10080,  # Maximum 7 days
        description="JWT access token expiration time in minutes. Range: 5 minutes to 7 days.",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,  # Minimum 1 day
        le=90,  # Maximum 90 days
        description="JWT refresh token expiration time in days. Range: 1 to 90 days.",
    )

    encryption_key: str = Field(
        default=os.getenv("ENCRYPTION_KEY", DEFAULT_ENCRYPTION_KEY),
        description="Encryption key for data encryption. Must be set via ENCRYPTION_KEY environment variable. "
                    "Must be exactly 32 characters (enforced in field validator), cryptographically random. "
                    "Validated for length, entropy (minimum 4.0 bits/char), and weak patterns.",
    )
    bcrypt_rounds: int = Field(
        default=12,
        ge=10,  # Minimum 10 rounds (industry standard)
        le=15,  # Maximum 15 rounds (performance vs security tradeoff)
        description="Bcrypt hashing rounds. Range: 10-15. Higher is more secure but slower.",
    )

    cors_origins: str = Field(
        default=os.getenv("CORS_ORIGINS", "http://localhost:3000"),
        description=(
            "Comma-separated list of allowed CORS origins. "
            "\n\n"
            "**IMPORTANT SECURITY:** Wildcards ('*') are NEVER allowed in any environment. "
            "Always specify exact origins for security. "
            "\n\n"
            "**Development:** "
            "- Defaults to 'http://localhost:3000' if not set "
            "- Localhost origins (http://localhost:*, http://127.0.0.1:*) are allowed "
            "- HTTP (non-HTTPS) origins are allowed for local development "
            "- Wildcards are NOT allowed even in development (will cause warning) "
            "\n\n"
            "**Production:** "
            "- MUST be explicitly set to specific trusted domains (no defaults) "
            "- Wildcards ('*') are NOT allowed and will cause startup failure "
            "- Localhost/127.0.0.1 origins are NOT allowed and will cause startup failure "
            "- HTTP (non-HTTPS) origins are NOT allowed - all must use HTTPS "
            "- Validation occurs at startup via validate_security_settings() "
            "\n\n"
            "**Examples:** "
            "- Development: 'http://localhost:3000,http://localhost:8000' "
            "- Production: 'https://app.example.com,https://admin.example.com' "
            "\n\n"
            "**See Also:** get_cors_origins() function documentation and SECURITY.md"
        ),
    )
    
    # Rate limiting
    rate_limit_per_minute: int = Field(
        default=60,
        ge=10,  # Minimum 10 requests per minute
        le=1000,  # Maximum 1000 requests per minute
        description="Rate limit per minute. Range: 10-1000 requests.",
    )
    rate_limit_per_hour: int = Field(
        default=1000,
        ge=100,  # Minimum 100 requests per hour
        le=100000,  # Maximum 100,000 requests per hour
        description="Rate limit per hour. Range: 100-100,000 requests.",
    )
    
    # Authentication enforcement
    require_auth: bool = Field(
        default=False,
        description="Require authentication for all endpoints. Set to True in production.",
    )
    auth_exempt_paths: str = Field(
        default="/api/v1/health,/api/v1/docs,/api/v1/openapi.json,/",
        description="Comma-separated list of paths exempt from authentication.",
    )
    
    # Security headers
    enable_security_headers: bool = Field(
        default=True,
        description="Enable security headers (HSTS, X-Frame-Options, etc.)",
    )
    hsts_max_age: int = Field(
        default=31536000,  # 1 year
        ge=0,
        description="HSTS max-age in seconds. Set to 0 to disable.",
    )
    
    # Password policy
    password_min_length: int = Field(
        default=12,
        ge=8,
        le=128,
        description="Minimum password length. Range: 8-128 characters.",
    )
    password_require_uppercase: bool = Field(
        default=True,
        description="Require uppercase letters in passwords.",
    )
    password_require_lowercase: bool = Field(
        default=True,
        description="Require lowercase letters in passwords.",
    )
    password_require_numbers: bool = Field(
        default=True,
        description="Require numbers in passwords.",
    )
    password_require_special: bool = Field(
        default=True,
        description="Require special characters in passwords.",
    )

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        """Validate JWT algorithm is in allowed list."""
        if v not in ALLOWED_JWT_ALGORITHMS:
            raise ValueError(
                f"JWT algorithm '{v}' is not allowed. "
                f"Allowed algorithms: {', '.join(sorted(ALLOWED_JWT_ALGORITHMS))}"
            )
        return v

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        """
        Validate JWT secret key strength.
        
        Enforces strict validation:
        - Minimum length: 32 characters (enforced)
        - Entropy: Minimum 4.0 bits per character (enforced)
        - Weak patterns: No common weak patterns allowed (enforced)
        
        Raises:
            ValueError: If validation fails for any reason
        """
        # Skip validation for default value (will be caught in validate_security_settings)
        if v == DEFAULT_JWT_SECRET or v.startswith("change-me"):
            return v
        
        # Ensure non-empty and not whitespace-only
        if not v or not v.strip():
            raise ValueError(
                "JWT_SECRET_KEY cannot be empty or whitespace-only. "
                "Generate a secure key using: python generate_keys.py"
            )
        
        # Length validation (enforced: minimum 32 characters)
        if len(v) < 32:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least 32 characters, got {len(v)} characters. "
                "Generate a secure key using: python generate_keys.py"
            )
        
        # Entropy validation (enforced: minimum 4.0 bits per character)
        entropy = calculate_entropy(v)
        if entropy < MIN_ENTROPY_JWT_SECRET:
            raise ValueError(
                f"JWT_SECRET_KEY has insufficient entropy ({entropy:.2f} bits/char, "
                f"minimum {MIN_ENTROPY_JWT_SECRET:.1f} required). "
                "Key may not be sufficiently random. Use cryptographically secure random generation."
            )
        
        # Weak pattern detection (enforced: no weak patterns allowed)
        weak_patterns = check_weak_patterns(v, min_entropy=MIN_ENTROPY_JWT_SECRET)
        if weak_patterns:
            # Remove entropy message since we already checked it above
            patterns = [p for p in weak_patterns if "entropy" not in p.lower()]
            if patterns:
                raise ValueError(
                    f"JWT_SECRET_KEY contains weak patterns: {'; '.join(patterns)}. "
                    "Generate a secure key using: python generate_keys.py"
                )
        
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """
        Validate encryption key strength.
        
        Enforces strict validation:
        - Exact length: 32 characters (enforced)
        - Entropy: Minimum 4.0 bits per character (enforced)
        - Weak patterns: No common weak patterns allowed (enforced)
        
        Raises:
            ValueError: If validation fails for any reason
        """
        # Skip validation for default value (will be caught in validate_security_settings)
        if v == DEFAULT_ENCRYPTION_KEY or v.startswith("change-me"):
            return v
        
        # Ensure non-empty and not whitespace-only
        if not v or not v.strip():
            raise ValueError(
                "ENCRYPTION_KEY cannot be empty or whitespace-only. "
                "Generate a secure key using: python generate_keys.py"
            )
        
        # Length validation (enforced: exactly 32 characters)
        if len(v) != 32:
            raise ValueError(
                f"ENCRYPTION_KEY must be exactly 32 characters, got {len(v)} characters. "
                "Generate a secure key using: python generate_keys.py"
            )
        
        # Entropy validation (enforced: minimum 4.0 bits per character)
        entropy = calculate_entropy(v)
        if entropy < MIN_ENTROPY_ENCRYPTION_KEY:
            raise ValueError(
                f"ENCRYPTION_KEY has insufficient entropy ({entropy:.2f} bits/char, "
                f"minimum {MIN_ENTROPY_ENCRYPTION_KEY:.1f} required). "
                "Key may not be sufficiently random. Use cryptographically secure random generation."
            )
        
        # Weak pattern detection (enforced: no weak patterns allowed)
        weak_patterns = check_weak_patterns(v, min_entropy=MIN_ENTROPY_ENCRYPTION_KEY)
        if weak_patterns:
            # Remove entropy message since we already checked it above
            patterns = [p for p in weak_patterns if "entropy" not in p.lower()]
            if patterns:
                raise ValueError(
                    f"ENCRYPTION_KEY contains weak patterns: {'; '.join(patterns)}. "
                    "Generate a secure key using: python generate_keys.py"
                )
        
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment


settings = SecuritySettings()


def validate_security_settings() -> None:
    """
    Validate security settings in all environments.
    
    This function performs comprehensive security validation including:
    - Default secret detection (prevents use of insecure defaults)
    - Secret key strength validation (length, entropy, weak patterns)
    - JWT algorithm validation (only strong algorithms allowed)
    - Token expiration validation (reasonable limits)
    - CORS configuration validation (URL format, HTTPS enforcement)
    - Production-specific security checks (debug mode, authentication, etc.)
    
    The function raises exceptions for critical security issues to prevent
    the application from starting with insecure settings.
    
    Raises:
        AppError: If critical security issues are detected (default secrets, short keys, etc.)
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_production = environment == "production"
    
    errors: List[str] = []
    warnings: List[str] = []
    
    # Check for default secrets (CRITICAL - applies to all environments)
    if settings.jwt_secret_key == DEFAULT_JWT_SECRET or settings.jwt_secret_key.startswith("change-me"):
        errors.append(
            f"JWT_SECRET_KEY is using default value '{DEFAULT_JWT_SECRET}'. "
            "This is a CRITICAL security vulnerability. "
            "Set JWT_SECRET_KEY environment variable with a secure random value (minimum 32 characters)."
        )
    
    if settings.encryption_key == DEFAULT_ENCRYPTION_KEY or settings.encryption_key.startswith("change-me"):
        errors.append(
            f"ENCRYPTION_KEY is using default value '{DEFAULT_ENCRYPTION_KEY}'. "
            "This is a CRITICAL security vulnerability. "
            "Set ENCRYPTION_KEY environment variable with a secure random value (exactly 32 characters)."
        )
    
    # Check secret lengths
    if len(settings.jwt_secret_key) < 32:
        errors.append(
            f"JWT_SECRET_KEY is too short ({len(settings.jwt_secret_key)} characters, minimum 32). "
            "Generate a secure random key with at least 32 characters using: python generate_keys.py"
        )
    
    # Check encryption key length (must be exactly 32)
    if len(settings.encryption_key) != 32:
        errors.append(
            f"ENCRYPTION_KEY must be exactly 32 characters, got {len(settings.encryption_key)}. "
            "Generate a secure key using: python generate_keys.py"
        )
    
    # Check for weak patterns and entropy in secrets (only if not default)
    # Note: Field validators should catch these, but we double-check here for safety
    if settings.jwt_secret_key != DEFAULT_JWT_SECRET and not settings.jwt_secret_key.startswith("change-me"):
        # Check entropy
        entropy = calculate_entropy(settings.jwt_secret_key)
        if entropy < MIN_ENTROPY_JWT_SECRET:
            errors.append(
                f"JWT_SECRET_KEY has insufficient entropy ({entropy:.2f} bits/char, "
                f"minimum {MIN_ENTROPY_JWT_SECRET:.1f} required). "
                "Key may not be sufficiently random. Use cryptographically secure random generation."
            )
        
        # Check weak patterns
        weak_patterns = check_weak_patterns(settings.jwt_secret_key, min_entropy=MIN_ENTROPY_JWT_SECRET)
        if weak_patterns:
            # Filter out entropy messages since we check it separately above
            patterns = [p for p in weak_patterns if "entropy" not in p.lower()]
            if patterns:
                errors.append(
                    f"JWT_SECRET_KEY contains weak patterns: {'; '.join(patterns)}. "
                    "Generate a secure key using: python generate_keys.py"
                )
    
    if settings.encryption_key != DEFAULT_ENCRYPTION_KEY and not settings.encryption_key.startswith("change-me"):
        # Check entropy
        entropy = calculate_entropy(settings.encryption_key)
        if entropy < MIN_ENTROPY_ENCRYPTION_KEY:
            errors.append(
                f"ENCRYPTION_KEY has insufficient entropy ({entropy:.2f} bits/char, "
                f"minimum {MIN_ENTROPY_ENCRYPTION_KEY:.1f} required). "
                "Key may not be sufficiently random. Use cryptographically secure random generation."
            )
        
        # Check weak patterns
        weak_patterns = check_weak_patterns(settings.encryption_key, min_entropy=MIN_ENTROPY_ENCRYPTION_KEY)
        if weak_patterns:
            # Filter out entropy messages since we check it separately above
            patterns = [p for p in weak_patterns if "entropy" not in p.lower()]
            if patterns:
                errors.append(
                    f"ENCRYPTION_KEY contains weak patterns: {'; '.join(patterns)}. "
                    "Generate a secure key using: python generate_keys.py"
                )
    
    # Validate JWT algorithm
    if settings.jwt_algorithm not in ALLOWED_JWT_ALGORITHMS:
        errors.append(
            f"JWT algorithm '{settings.jwt_algorithm}' is not allowed. "
            f"Allowed algorithms: {', '.join(sorted(ALLOWED_JWT_ALGORITHMS))}"
        )
    
    # Validate token expiration times
    if settings.jwt_access_token_expire_minutes < 5:
        errors.append(
            f"JWT access token expiration ({settings.jwt_access_token_expire_minutes} minutes) is too short. "
            "Minimum is 5 minutes for security."
        )
    elif settings.jwt_access_token_expire_minutes > 10080:  # 7 days
        warnings.append(
            f"JWT access token expiration ({settings.jwt_access_token_expire_minutes} minutes) is very long. "
            "Consider shorter expiration times for better security."
        )
    
    if settings.jwt_refresh_token_expire_days > 90:
        warnings.append(
            f"JWT refresh token expiration ({settings.jwt_refresh_token_expire_days} days) is very long. "
            "Consider shorter expiration times for better security."
        )
    
    # Validate bcrypt rounds
    if settings.bcrypt_rounds < 10:
        errors.append(
            f"Bcrypt rounds ({settings.bcrypt_rounds}) is too low. "
            "Minimum is 10 rounds for security. Recommended: 12 rounds."
        )
    elif settings.bcrypt_rounds > 15:
        warnings.append(
            f"Bcrypt rounds ({settings.bcrypt_rounds}) is very high and may impact performance. "
            "Recommended: 12 rounds."
        )
    
    # Validate CORS origins
    cors_origins_list = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    
    if not cors_origins_list:
        errors.append("CORS_ORIGINS is empty. At least one origin must be specified.")
    else:
        # Check for wildcards - NEVER allowed in any environment (security risk)
        if "*" in settings.cors_origins:
            if is_production:
                errors.append("CORS_ORIGINS contains '*' - NEVER use wildcards in production")
            else:
                warnings.append(
                    "CORS_ORIGINS contains '*' - Wildcards are not recommended even in development. "
                    "Specify exact origins for better security (e.g., 'http://localhost:3000')."
                )
        
        # Validate each origin format
        for origin in cors_origins_list:
            is_valid, error_msg = validate_url_format(origin)
            if not is_valid:
                errors.append(f"CORS origin validation failed: {error_msg}")
    
    # Production-specific checks
    if is_production:
        # Check debug mode
        debug = os.getenv("DEBUG", "false").lower()
        if debug == "true":
            errors.append("DEBUG is set to true - MUST be false in production")
        
        # Check authentication
        if not settings.require_auth:
            errors.append(
                "REQUIRE_AUTH is false - MUST be true in production. "
                "Set REQUIRE_AUTH=true in your .env file."
            )
        
        # Check for localhost in production (security risk)
        # Note: Wildcard check is done above for all environments
        cors_list = [origin.strip().lower() for origin in settings.cors_origins.split(",")]
        if any("localhost" in origin or "127.0.0.1" in origin for origin in cors_list):
            errors.append(
                "CORS_ORIGINS contains localhost/127.0.0.1 - NOT allowed in production. "
                "Set CORS_ORIGINS to your production domain(s) only (e.g., https://app.example.com)."
            )
        
        # Check for HTTP (non-HTTPS) in production
        if any(origin.strip().startswith("http://") for origin in settings.cors_origins.split(",")):
            errors.append(
                "CORS_ORIGINS contains HTTP (non-HTTPS) origins - HTTPS is REQUIRED in production. "
                "All production origins must use https:// protocol."
            )
        
        # Check rate limits are reasonable for production
        if settings.rate_limit_per_minute > 500:
            warnings.append(
                f"Rate limit per minute ({settings.rate_limit_per_minute}) is very high. "
                "Consider lower limits to prevent abuse."
            )
    
    # Validate rate limit ratios
    if settings.rate_limit_per_hour < settings.rate_limit_per_minute:
        errors.append(
            f"Rate limit per hour ({settings.rate_limit_per_hour}) is less than per minute "
            f"({settings.rate_limit_per_minute}). This is invalid."
        )
    
    # Log warnings
    if warnings:
        for warning in warnings:
            logger.warning(f"Security warning: {warning}")
    
    # Raise exception for critical errors (prevents app from starting with insecure config)
    if errors:
        error_message = "CRITICAL: Security validation failed. The application cannot start with insecure settings.\n\n"
        error_message += "Issues found:\n"
        for error in errors:
            error_message += f"  ❌ {error}\n"
        
        if warnings:
            error_message += "\nWarnings:\n"
            for warning in warnings:
                error_message += f"  ⚠️  {warning}\n"
        
        error_message += "\n" + "=" * 70 + "\n"
        error_message += "HOW TO FIX:\n"
        error_message += "=" * 70 + "\n"
        error_message += "1. Generate secure keys:\n"
        error_message += "   python generate_keys.py\n\n"
        error_message += "2. Copy the generated keys to your .env file:\n"
        error_message += "   JWT_SECRET_KEY=<generated-value>\n"
        error_message += "   ENCRYPTION_KEY=<generated-value>\n\n"
        error_message += "3. For production, also set:\n"
        error_message += "   REQUIRE_AUTH=true\n"
        error_message += "   CORS_ORIGINS=https://your-domain.com\n"
        error_message += "   ENVIRONMENT=production\n"
        error_message += "   DEBUG=false\n\n"
        error_message += "4. Or set them as environment variables before starting the application\n\n"
        error_message += "5. For more help, see: python setup_database.py (creates .env with secure keys)\n"
        error_message += "=" * 70 + "\n"
        
        logger.error(error_message)
        raise AppError(
            "Security validation failed. Application cannot start with insecure settings.",
            status_code=500,
            details={"errors": errors, "warnings": warnings}
        )


def validate_production_security() -> None:
    """
    Validate security settings in production environment.
    
    This function performs comprehensive security validation for production environments,
    checking for insecure configurations that could compromise the application.
    
    **Validation Checks:**
    - Default secrets (JWT_SECRET_KEY, ENCRYPTION_KEY) are not allowed
    - Secret key lengths meet minimum requirements (32 characters)
    - Secret key strength (entropy, weak patterns)
    - JWT algorithm is in allowed list
    - Token expiration times are reasonable
    - DEBUG mode is disabled in production
    - Authentication is required in production
    - CORS origins do not use wildcards in production
    - CORS origins use HTTPS in production
    - Rate limits are reasonable
    
    **Raises:**
    - `AppError`: If critical security issues are detected, preventing application startup
    
    **Note:**
    This is a legacy function kept for backward compatibility.
    It now calls `validate_security_settings()` which validates in all environments.
    For new code, use `validate_security_settings()` directly.
    """
    validate_security_settings()


def get_cors_origins() -> List[str]:
    """
    Get CORS origins from environment as a list.
    
    **IMPORTANT SECURITY:** Wildcards (`*`) are NEVER allowed in any environment.
    Always specify exact origins for security. The application validates this at startup.
    
    **Development vs Production Behavior:**
    - **Development:** 
      - Defaults to `http://localhost:3000` if not set
      - Allows localhost origins (http://localhost:*, http://127.0.0.1:*)
      - Allows HTTP (non-HTTPS) origins for local development
      - Wildcards generate a warning but do not prevent startup
    - **Production:** 
      - MUST be explicitly set to specific trusted domains (no defaults)
      - Wildcards (`*`) are NOT allowed and will cause startup failure
      - Localhost/127.0.0.1 origins are NOT allowed and will cause startup failure
      - HTTP (non-HTTPS) origins are NOT allowed - all must use HTTPS
      - Validation occurs at startup - application will fail to start with insecure settings
    
    **Examples:**
    - Development: `CORS_ORIGINS=http://localhost:3000,http://localhost:8000`
    - Production: `CORS_ORIGINS=https://app.example.com,https://admin.example.com`
    
    **Security Notes:**
    - Wildcard validation is enforced in `validate_security_settings()` for all environments
    - Production validation is enforced in `validate_security_settings()` and `deploy_app.sh`
    - The application will refuse to start in production with insecure CORS configuration
    - See `SECURITY.md` for detailed CORS configuration documentation
    
    Returns:
        List of allowed CORS origins (trimmed and validated)
    """
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]


def get_cors_methods() -> List[str]:
    """
    Get allowed CORS HTTP methods.
    
    In production, only essential methods are allowed for security.
    In development, more permissive settings are allowed.
    
    Returns:
        List of allowed HTTP methods
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_production = environment == "production"
    
    if is_production:
        # Production: Only essential methods
        return ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    else:
        # Development: Allow common methods
        return ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


def get_cors_headers() -> List[str]:
    """
    Get allowed CORS headers.
    
    In production, only essential headers are allowed for security.
    In development, more permissive settings are allowed.
    
    Returns:
        List of allowed headers
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_production = environment == "production"
    
    if is_production:
        # Production: Only essential headers
        return [
            "Content-Type",
            "Authorization",
            "Accept",
            "X-Requested-With",
            "X-API-Key",
        ]
    else:
        # Development: Allow common headers
        return [
            "Content-Type",
            "Authorization",
            "Accept",
            "Accept-Language",
            "Content-Language",
            "X-Requested-With",
            "X-API-Key",
            "X-CSRF-Token",
        ]


def get_jwt_secret() -> str:
    """Get JWT secret key."""
    return settings.jwt_secret_key


def get_encryption_key() -> str:
    """Get encryption key."""
    return settings.encryption_key


def get_jwt_algorithm() -> str:
    """Get JWT algorithm."""
    return settings.jwt_algorithm


def get_jwt_access_token_expire_minutes() -> int:
    """Get JWT access token expiration time in minutes."""
    return settings.jwt_access_token_expire_minutes


def get_jwt_refresh_token_expire_days() -> int:
    """Get JWT refresh token expiration time in days."""
    return settings.jwt_refresh_token_expire_days


def get_bcrypt_rounds() -> int:
    """Get bcrypt rounds."""
    return settings.bcrypt_rounds


def get_rate_limit_per_minute() -> int:
    """Get rate limit per minute."""
    return settings.rate_limit_per_minute


def get_rate_limit_per_hour() -> int:
    """Get rate limit per hour."""
    return settings.rate_limit_per_hour


def is_auth_required() -> bool:
    """Check if authentication is required."""
    return settings.require_auth


def get_auth_exempt_paths() -> List[str]:
    """Get list of paths exempt from authentication."""
    return [path.strip() for path in settings.auth_exempt_paths.split(",") if path.strip()]


def get_security_headers_config() -> dict:
    """
    Get security headers configuration.
    
    Returns:
        Dictionary with security header settings
    """
    return {
        "enable_security_headers": settings.enable_security_headers,
        "hsts_max_age": settings.hsts_max_age,
    }


def get_password_policy() -> dict:
    """
    Get password policy configuration.
    
    Returns:
        Dictionary with password policy requirements
    """
    return {
        "min_length": settings.password_min_length,
        "require_uppercase": settings.password_require_uppercase,
        "require_lowercase": settings.password_require_lowercase,
        "require_numbers": settings.password_require_numbers,
        "require_special": settings.password_require_special,
    }


# Validate security settings on module import (all environments)
# This prevents the application from starting with insecure default values
validate_security_settings()
