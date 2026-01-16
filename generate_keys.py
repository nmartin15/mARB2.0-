#!/usr/bin/env python3
"""Generate secure keys for environment variables."""
import secrets


def generate_jwt_secret() -> str:
    """
    Generate a secure JWT secret key (32+ characters).

    Uses secrets.token_urlsafe() to generate a cryptographically secure random token.
    The token is URL-safe base64 encoded and suitable for use as a JWT signing key.

    Returns:
        A secure random string of at least 32 characters (typically 43 characters)
    """
    return secrets.token_urlsafe(32)


def generate_encryption_key() -> str:
    """
    Generate a secure encryption key (exactly 32 characters).

    Generates a cryptographically secure random key suitable for encryption operations.
    The key is exactly 32 characters long, encoded as URL-safe base64.

    Returns:
        A secure random string of exactly 32 characters
    """
    # Generate 24 random bytes and encode as URL-safe base64
    # 24 bytes * 4/3 = 32 characters in base64 encoding
    # This will always produce exactly 32 characters
    return secrets.token_urlsafe(24)[:32]


def main() -> None:
    """
    Generate and display secure keys for environment variables.

    This function generates JWT_SECRET_KEY and ENCRYPTION_KEY values
    that can be copied into a .env file for application configuration.
    """
    print("=" * 60)
    print("mARB 2.0 - Secure Key Generator")
    print("=" * 60)
    print()
    print("Generated secure keys for your .env file:")
    print()
    print(f"JWT_SECRET_KEY={generate_jwt_secret()}")
    print()
    print(f"ENCRYPTION_KEY={generate_encryption_key()}")
    print()
    print("=" * 60)
    print("Copy these values into your .env file")
    print("=" * 60)


if __name__ == "__main__":
    main()

