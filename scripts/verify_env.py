#!/usr/bin/env python3
"""Verify environment variables are set correctly."""
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse, parse_qs


class EnvVarChecker:
    """
    Check environment variables for correctness and completeness.
    
    This class validates environment variables from a .env file, checking:
    - Required variables are set
    - Secret keys meet length requirements
    - URLs are properly formatted
    - Database and Redis connections are valid
    - Security settings are appropriate for production
    
    Attributes:
        env_file: Path to the .env file to check
        env_vars: Dictionary of loaded environment variables
        errors: List of error messages
        warnings: List of warning messages
        info: List of informational messages
    """
    
    def __init__(self, env_file: Optional[Path] = None):
        """
        Initialize checker with environment file.
        
        Args:
            env_file: Optional path to .env file. Defaults to ".env" in current directory.
        """
        self.env_file = env_file or Path(".env")
        self.env_vars: Dict[str, str] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        
    def load_env_file(self) -> bool:
        """
        Load environment variables from .env file.
        
        Parses KEY=VALUE pairs from the .env file, handling quoted values
        and skipping comments and empty lines.
        
        Returns:
            True if file was loaded successfully, False otherwise
            
        Note:
            Errors are added to self.errors list if loading fails
        """
        if not self.env_file.exists():
            self.errors.append(f".env file not found at {self.env_file.absolute()}")
            return False
        
        try:
            with open(self.env_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        line = line.strip()
                        # Skip comments and empty lines
                        if not line or line.startswith("#"):
                            continue
                        
                        # Parse KEY=VALUE
                        if "=" not in line:
                            self.warnings.append(f"Line {line_num}: Invalid format (no '=' found)")
                            continue
                        
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        # Validate key format (alphanumeric and underscores only)
                        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                            self.warnings.append(
                                f"Line {line_num}: Invalid key format '{key}' "
                                "(should be alphanumeric with underscores)"
                            )
                            continue
                        
                        # Handle empty values
                        if not value:
                            value = ""
                        
                        self.env_vars[key] = value
                    except UnicodeDecodeError as e:
                        self.errors.append(
                            f"Line {line_num}: Invalid encoding - {e}. "
                            "File should be UTF-8 encoded."
                        )
                        return False
                    except Exception as e:
                        self.warnings.append(
                            f"Line {line_num}: Error parsing line - {type(e).__name__}: {e}"
                        )
                        continue
            
            return True
        except FileNotFoundError:
            self.errors.append(f"File not found: {self.env_file.absolute()}")
            return False
        except PermissionError:
            self.errors.append(
                f"Permission denied reading {self.env_file.absolute()}. "
                "Check file permissions."
            )
            return False
        except OSError as e:
            self.errors.append(
                f"OS error reading .env file: {e}. "
                "File may be locked or inaccessible."
            )
            return False
        except ValueError as e:
            self.errors.append(
                f"ValueError reading .env file: {e}. "
                "File may contain invalid data."
            )
            return False
        except Exception as e:
            self.errors.append(
                f"Failed to read .env file due to an unexpected error: {type(e).__name__}: {e}"
            )
            return False
    
    def check_required(self, var_name: str, description: str = "") -> bool:
        """
        Check if required variable is set.
        
        Args:
            var_name: Name of the environment variable to check
            description: Optional description of the variable's purpose
            
        Returns:
            True if variable is set and non-empty, False otherwise
            
        Note:
            Errors are added to self.errors if variable is missing
        """
        if var_name not in self.env_vars or not self.env_vars[var_name]:
            self.errors.append(
                f"Required variable {var_name} is not set" + 
                (f" ({description})" if description else "")
            )
            return False
        return True
    
    def check_optional(self, var_name: str, default: str = "", description: str = "") -> bool:
        """
        Check if optional variable is set, warn if missing.
        
        Args:
            var_name: Name of the environment variable to check
            default: Default value if variable is not set
            description: Optional description of the variable's purpose
            
        Returns:
            True if variable is set, False if missing (uses default)
            
        Note:
            Info messages are added if default is used, warnings if no default provided
        """
        if var_name not in self.env_vars or not self.env_vars[var_name]:
            if default:
                self.info.append(
                    f"Optional variable {var_name} not set, using default: {default}" +
                    (f" ({description})" if description else "")
                )
            else:
                self.warnings.append(
                    f"Optional variable {var_name} is not set" +
                    (f" ({description})" if description else "")
                )
            return False
        return True
    
    def check_secret_length(self, var_name: str, min_length: int = 32) -> bool:
        """
        Check if secret meets minimum length requirement.
        
        Args:
            var_name: Name of the secret environment variable to check
            min_length: Minimum required length in characters (default: 32)
            
        Returns:
            True if secret meets length requirement, False otherwise
            
        Note:
            Errors are added if secret is too short
        """
        value = self.env_vars.get(var_name, "")
        if len(value) < min_length:
            self.errors.append(
                f"{var_name} is too short ({len(value)} chars, minimum {min_length})"
            )
            return False
        return True
    
    def check_secret_not_default(self, var_name: str, default_patterns: List[str]) -> bool:
        """
        Check if secret is not using default/placeholder value.
        
        Args:
            var_name: Name of the secret environment variable to check
            default_patterns: List of strings that indicate default/placeholder values
            
        Returns:
            True if secret does not contain any default patterns, False otherwise
            
        Note:
            Errors are added if default patterns are found in the secret
        """
        value = self.env_vars.get(var_name, "")
        value_lower = value.lower()
        
        for pattern in default_patterns:
            if pattern.lower() in value_lower:
                self.errors.append(
                    f"{var_name} appears to have default/placeholder value (contains '{pattern}')"
                )
                return False
        return True
    
    def check_url_format(self, var_name: str, schemes: List[str] = None) -> bool:
        """
        Check if variable is a valid URL with required scheme.
        
        Args:
            var_name: Name of the environment variable containing the URL
            schemes: Optional list of allowed URL schemes (e.g., ["https", "http"])
            
        Returns:
            True if URL is valid and uses allowed scheme, False otherwise
            
        Note:
            Errors are added if URL format is invalid or scheme is not allowed
        """
        value = self.env_vars.get(var_name, "")
        if not value:
            return False
        
        try:
            parsed = urlparse(value)
            if not parsed.scheme:
                self.errors.append(f"{var_name} is not a valid URL (missing scheme)")
                return False
            
            if schemes and parsed.scheme not in schemes:
                self.errors.append(
                    f"{var_name} must use one of these schemes: {', '.join(schemes)}"
                )
                return False
            
            return True
        except Exception as e:
            self.errors.append(f"{var_name} is not a valid URL: {e}")
            return False
    
    def check_database_url(self, var_name: str = "DATABASE_URL") -> bool:
        """
        Check database URL format and SSL requirement.
        
        Validates PostgreSQL connection string format and ensures SSL is configured
        for production environments.
        
        Args:
            var_name: Name of the environment variable containing the database URL (default: "DATABASE_URL")
            
        Returns:
            True if database URL is valid, False otherwise
            
        Note:
            Warnings are added if SSL is not configured in production or password is missing
        """
        if not self.check_required(var_name, "PostgreSQL connection string"):
            return False
        
        value = self.env_vars[var_name]
        
        # Check URL format
        if not self.check_url_format(var_name, ["postgresql", "postgresql+psycopg2"]):
            return False
        
        # Check for SSL in production
        environment = self.env_vars.get("ENVIRONMENT", "development").lower()
        if environment == "production":
            if "sslmode=require" not in value and "sslmode=prefer" not in value:
                self.warnings.append(
                    f"{var_name} should include ?sslmode=require for production security"
                )
        
        # Check for password
        parsed = urlparse(value)
        if not parsed.password:
            self.warnings.append(f"{var_name} does not appear to include a password")
        
        return True
    
    def check_redis_url(self, var_name: str) -> bool:
        """
        Check Redis URL format.
        
        Validates Redis connection URL format and ensures password is configured
        for production environments.
        
        Args:
            var_name: Name of the environment variable containing the Redis URL
            
        Returns:
            True if Redis URL is valid, False otherwise
            
        Note:
            Warnings are added if password is missing in production
        """
        if not self.check_required(var_name, "Redis connection URL"):
            return False
        
        value = self.env_vars[var_name]
        
        # Check URL format
        if not self.check_url_format(var_name, ["redis"]):
            return False
        
        # Check for password in production
        environment = self.env_vars.get("ENVIRONMENT", "development").lower()
        if environment == "production":
            parsed = urlparse(value)
            if not parsed.password:
                self.warnings.append(
                    f"{var_name} should include password for production: redis://:password@host:port/db"
                )
        
        return True
    
    def check_boolean(self, var_name: str, required: bool = False, 
                     expected_value: Optional[bool] = None) -> bool:
        """Check boolean variable."""
        if required and not self.check_required(var_name):
            return False
        
        value = self.env_vars.get(var_name, "").lower()
        if value not in ["true", "false", "1", "0", "yes", "no", ""]:
            self.errors.append(
                f"{var_name} must be a boolean (true/false), got: {value}"
            )
            return False
        
        if expected_value is not None and value:
            bool_value = value in ["true", "1", "yes"]
            if bool_value != expected_value:
                expected_str = "true" if expected_value else "false"
                self.warnings.append(
                    f"{var_name} is '{value}', expected '{expected_str}'"
                )
        
        return True
    
    def check_integer(self, var_name: str, min_value: Optional[int] = None,
                     max_value: Optional[int] = None) -> bool:
        """Check integer variable."""
        value = self.env_vars.get(var_name, "")
        if not value:
            return False
        
        try:
            int_value = int(value)
            if min_value is not None and int_value < min_value:
                self.errors.append(
                    f"{var_name} must be >= {min_value}, got: {int_value}"
                )
                return False
            if max_value is not None and int_value > max_value:
                self.errors.append(
                    f"{var_name} must be <= {max_value}, got: {int_value}"
                )
                return False
            return True
        except ValueError:
            self.errors.append(f"{var_name} must be an integer, got: {value}")
            return False
    
    def check_float(self, var_name: str, min_value: Optional[float] = None,
                   max_value: Optional[float] = None) -> bool:
        """Check float variable."""
        value = self.env_vars.get(var_name, "")
        if not value:
            return False
        
        try:
            float_value = float(value)
            if min_value is not None and float_value < min_value:
                self.errors.append(
                    f"{var_name} must be >= {min_value}, got: {float_value}"
                )
                return False
            if max_value is not None and float_value > max_value:
                self.errors.append(
                    f"{var_name} must be <= {max_value}, got: {float_value}"
                )
                return False
            return True
        except ValueError:
            self.errors.append(f"{var_name} must be a number, got: {value}")
            return False
    
    def check_cors_origins(self, var_name: str = "CORS_ORIGINS") -> bool:
        """Check CORS origins configuration."""
        if not self.check_required(var_name, "Comma-separated list of allowed origins"):
            return False
        
        value = self.env_vars[var_name]
        environment = self.env_vars.get("ENVIRONMENT", "development").lower()
        
        # Sanitize input to prevent injection attacks
        # Remove control characters and normalize whitespace
        sanitized_value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
        sanitized_value = re.sub(r'\s+', ' ', sanitized_value).strip()
        
        # Check for wildcards in production
        if environment == "production" and "*" in sanitized_value:
            self.errors.append(
                f"{var_name} contains '*' - NEVER use wildcards in production"
            )
            return False
        
        # Check for localhost in production
        if environment == "production" and "localhost" in sanitized_value.lower():
            self.warnings.append(
                f"{var_name} contains localhost - should use production domains only"
            )
        
        # Validate URL format of each origin
        origins = [origin.strip() for origin in sanitized_value.split(",")]
        for origin in origins:
            if origin:
                # Additional sanitization: remove any characters that aren't valid in URLs
                # Allow: alphanumeric, dots, colons, slashes, hyphens, underscores, and query/fragment chars
                sanitized_origin = re.sub(r'[^a-zA-Z0-9.:/?#\[\]@!$&\'()*+,;=_-]', '', origin)
                
                # Validate URL format
                if not (sanitized_origin.startswith("http://") or sanitized_origin.startswith("https://")):
                    self.warnings.append(
                        f"{var_name} origin '{sanitized_origin}' should start with http:// or https://"
                    )
                    continue
                
                # Validate URL structure using urlparse
                try:
                    parsed = urlparse(sanitized_origin)
                    if not parsed.netloc:
                        self.warnings.append(
                            f"{var_name} origin '{sanitized_origin}' appears to be malformed "
                            "(missing host/domain)"
                        )
                except Exception as e:
                    self.warnings.append(
                        f"{var_name} origin '{sanitized_origin}' could not be validated: {e}"
                    )
        
        return True
    
    def check_sentry_dsn(self, var_name: str = "SENTRY_DSN") -> bool:
        """Check Sentry DSN format."""
        value = self.env_vars.get(var_name, "")
        if not value:
            self.info.append(f"{var_name} not set (error tracking disabled)")
            return True  # Optional
        
        # Sentry DSN format: https://key@host/project-id
        if not value.startswith("https://"):
            self.errors.append(
                f"{var_name} must start with 'https://' (format: https://key@sentry.io/project-id)"
            )
            return False
        
        if "@" not in value:
            self.errors.append(
                f"{var_name} is missing key (format: https://key@sentry.io/project-id)"
            )
            return False
        
        return True
    
    def verify_all(self) -> Tuple[bool, List[str], List[str], List[str]]:
        """
        Verify all environment variables.
        
        Performs comprehensive validation of all environment variables including:
        - Required variables (DATABASE_URL, JWT_SECRET_KEY, ENCRYPTION_KEY)
        - Security settings (secret length, default values, SSL)
        - Service URLs (database, Redis, Celery)
        - Configuration options (CORS, logging, rate limiting)
        - Optional services (Sentry)
        
        Returns:
            Tuple of (is_valid, errors, warnings, info):
            - is_valid: True if no errors found, False otherwise
            - errors: List of error messages (must be fixed)
            - warnings: List of warning messages (should be addressed)
            - info: List of informational messages
            
        Note:
            This is the main public API method for validating environment configuration
        """
        if not self.load_env_file():
            return False, self.errors, self.warnings, self.info
        
        # Required variables
        self.check_required("DATABASE_URL", "PostgreSQL connection string")
        self.check_database_url("DATABASE_URL")
        
        # Security secrets
        self.check_required("JWT_SECRET_KEY", "JWT signing key")
        self.check_secret_length("JWT_SECRET_KEY", min_length=32)
        self.check_secret_not_default(
            "JWT_SECRET_KEY",
            ["change-me", "CHANGE_ME", "default", "placeholder"]
        )
        
        self.check_required("ENCRYPTION_KEY", "Data encryption key")
        self.check_secret_length("ENCRYPTION_KEY", min_length=32)
        self.check_secret_not_default(
            "ENCRYPTION_KEY",
            ["change-me", "CHANGE_ME", "default", "placeholder"]
        )
        
        # Environment
        environment = self.env_vars.get("ENVIRONMENT", "development").lower()
        if environment not in ["development", "staging", "production", "test"]:
            self.warnings.append(
                f"ENVIRONMENT should be one of: development, staging, production, test (got: {environment})"
            )
        
        # Debug mode
        self.check_boolean("DEBUG", required=False)
        if environment == "production":
            self.check_boolean("DEBUG", expected_value=False)
        
        # Redis configuration
        redis_host = self.env_vars.get("REDIS_HOST", "localhost")
        redis_port = self.env_vars.get("REDIS_PORT", "6379")
        self.check_integer("REDIS_PORT", min_value=1, max_value=65535)
        
        if environment == "production":
            self.check_required("REDIS_PASSWORD", "Redis password for production")
        
        # Celery configuration
        self.check_optional("CELERY_BROKER_URL", "redis://localhost:6379/0", "Celery broker URL")
        if "CELERY_BROKER_URL" in self.env_vars:
            self.check_redis_url("CELERY_BROKER_URL")
        
        self.check_optional("CELERY_RESULT_BACKEND", "redis://localhost:6379/0", "Celery result backend")
        if "CELERY_RESULT_BACKEND" in self.env_vars:
            self.check_redis_url("CELERY_RESULT_BACKEND")
        
        # CORS
        self.check_cors_origins("CORS_ORIGINS")
        
        # Authentication
        self.check_boolean("REQUIRE_AUTH", required=False)
        if environment == "production":
            self.check_boolean("REQUIRE_AUTH", expected_value=True)
        
        # Sentry (optional)
        self.check_sentry_dsn("SENTRY_DSN")
        if "SENTRY_DSN" in self.env_vars and self.env_vars["SENTRY_DSN"]:
            self.check_optional("SENTRY_ENVIRONMENT", environment, "Sentry environment name")
        
        # Logging
        self.check_optional("LOG_LEVEL", "INFO", "Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
        if "LOG_LEVEL" in self.env_vars:
            log_level = self.env_vars["LOG_LEVEL"].upper()
            if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                self.warnings.append(
                    f"LOG_LEVEL should be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL (got: {log_level})"
                )
        
        self.check_optional("LOG_FORMAT", "json", "Log format (json or console)")
        if "LOG_FORMAT" in self.env_vars:
            log_format = self.env_vars["LOG_FORMAT"].lower()
            if log_format not in ["json", "console"]:
                self.warnings.append(
                    f"LOG_FORMAT should be 'json' or 'console' (got: {log_format})"
                )
        
        # Rate limiting
        self.check_optional("RATE_LIMIT_PER_MINUTE", "60", "Rate limit per minute")
        if "RATE_LIMIT_PER_MINUTE" in self.env_vars:
            self.check_integer("RATE_LIMIT_PER_MINUTE", min_value=1)
        
        self.check_optional("RATE_LIMIT_PER_HOUR", "1000", "Rate limit per hour")
        if "RATE_LIMIT_PER_HOUR" in self.env_vars:
            self.check_integer("RATE_LIMIT_PER_HOUR", min_value=1)
        
        # Sentry configuration (if DSN is set)
        if "SENTRY_DSN" in self.env_vars and self.env_vars["SENTRY_DSN"]:
            self.check_optional("SENTRY_TRACES_SAMPLE_RATE", "0.1", "Sentry transaction sampling rate")
            if "SENTRY_TRACES_SAMPLE_RATE" in self.env_vars:
                self.check_float("SENTRY_TRACES_SAMPLE_RATE", min_value=0.0, max_value=1.0)
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings, self.info


def main():
    """
    Main entry point for environment variable verification.
    
    Loads and validates environment variables from .env file, then prints
    a summary of errors, warnings, and informational messages.
    
    Command-line arguments:
        --env-file: Path to .env file (default: .env)
        --quiet: Only show errors and warnings, suppress info messages
        
    Returns:
        Exit code: 0 if valid, 1 if errors found
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify environment variables")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file (default: .env)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors and warnings"
    )
    
    args = parser.parse_args()
    
    checker = EnvVarChecker(args.env_file)
    is_valid, errors, warnings, info = checker.verify_all()
    
    print("=" * 70)
    print("mARB 2.0 - Environment Variable Verification")
    print("=" * 70)
    print()
    
    if errors:
        print("✗ ERRORS (must be fixed):")
        print()
        for error in errors:
            print(f"  ❌ {error}")
        print()
    
    if warnings:
        print("⚠ WARNINGS (should be addressed):")
        print()
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print()
    
    if info and not args.quiet:
        print("ℹ INFO:")
        print()
        for msg in info:
            print(f"  ℹ️  {msg}")
        print()
    
    if is_valid and not errors:
        print("✓ All environment variables are valid!")
        if warnings:
            print("  (Some warnings present, but no critical issues)")
        return 0
    else:
        print("✗ Environment variable verification failed.")
        print("  Please fix the errors above before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

